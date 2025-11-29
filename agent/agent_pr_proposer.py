import logging
from typing import Dict, Any, Union
import requests
from requests.exceptions import RequestException, HTTPError

# Заглушки типов для 'requests' установлены отдельно: pip install types-requests

logger = logging.getLogger(__name__)

# Определяем точный тип возвращаемого словаря для лучшей типизации
ResultDict = Dict[str, Union[str, Any]]


def propose_pr(
    owner: str,
    repo: str,
    head: str,
    base: str,
    token: str,
    title: str = "Automated PR by Agent"
) -> ResultDict:
    """
    Отправляет запрос на создание Pull Request в GitHub.

    Args:
        owner (str): Владелец репозитория.
        repo (str): Название репозитория.
        head (str): Название ветки, которую сливаем (source branch).
        base (str): Название ветки, в которую сливаем (target branch).
        token (str): Токен доступа GitHub.
        title (str): Заголовок Pull Request.

    Returns:
        Dict: Словарь с ключами 'status' ('success'/'failure') и 'message',
              а также 'pr_url' при успехе.
    """
    url = f'https://api.github.com/repos/{owner}/{repo}/pulls'
    headers = {
        'Authorization': f'token {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/vnd.github.v3+json'  # Рекомендуется для явного указания версии API
    }
    data = {
        'head': head,
        'base': base,
        'title': title
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)

        # Проверяем статус. Если 4xx или 5xx, переходим к обработке ошибки.
        # response.raise_for_status() - не используется для обработки кастомных сообщений.

        if response.status_code >= 400:
            # Пытаемся получить сообщение об ошибке из тела ответа
            error_details = response.json().get('message', 'Нет деталей ошибки')
            logger.error(f'❌ Ошибка при создании PR: HTTP {response.status_code}. Детали: {error_details}')

            # В случае ошибки GitHub часто возвращает 422 Unprocessable Entity
            # с деталями (например, "No commits between...")
            return {
                'status': 'failure',
                'message': f'Ошибка при создании PR: {response.status_code}. {error_details}'
            }

        # Если статус успешный (201 Created)
        response_json = response.json()
        return {
            'status': 'success',
            'message': 'PR создан успешно',
            'pr_url': response_json.get('html_url', 'N/A'),
            'pr_number': response_json.get('number', 'N/A')
        }

    except HTTPError as e:
        # Хотя мы проверяем status_code выше, эта ветка может быть нужна,
        # если мы решим использовать raise_for_status() в будущем.
        logger.error(f'❌ HTTP-ошибка при создании PR: {e}')
        return {'status': 'failure', 'message': f'HTTP Error: {e}'}

    except RequestException as e:
        # Обрабатываем сетевые ошибки (таймауты, DNS и т.д.)
        logger.error(f'❌ Сетевая ошибка при создании PR: {e}')
        return {'status': 'failure', 'message': f'Сетевая ошибка: {e}'}
    except Exception as e:
        # На всякий случай обрабатываем непредвиденные ошибки
        logger.error(f'❌ Неизвестная ошибка: {e}')
        return {'status': 'failure', 'message': f'Неизвестная ошибка: {e}'}
