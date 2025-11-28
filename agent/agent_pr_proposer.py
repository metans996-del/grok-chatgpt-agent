import logging
from typing import Dict
import requests
from requests.exceptions import RequestException


logger = logging.getLogger(__name__)


def propose_pr(owner: str, repo: str, head: str, base: str, token: str) -> Dict[str, str]:
    """
    Отправляет запрос на создание Pull Request в GitHub.
    Проверяет status_code перед raise_for_status() для совместимости с моками.
    """
    url = f'https://api.github.com/repos/{owner}/{repo}/pulls'
    headers = {'Authorization': f'token {token}', 'Content-Type': 'application/json'}
    data = {'head': head, 'base': base, 'title': 'Automated PR'}

    try:
        response = requests.post(url, headers=headers, json=data)

        # ИСПРАВЛЕНИЕ: Проверяем status_code напрямую
        # Это работает и с реальными запросами, и с моками
        if response.status_code >= 400:
            logger.error(f'Error proposing PR: HTTP {response.status_code}')
            return {'status': 'failure', 'message': 'Error proposing PR'}

        # Если статус успешный (2xx или 3xx)
        return {
            'status': 'success',
            'message': 'PR created successfully',
            'pr_url': response.json().get('html_url', 'N/A')
        }

    except RequestException as e:
        # Обрабатываем сетевые ошибки (таймауты, DNS и т.д.)
        logger.error(f'Network error proposing PR: {e}')
        return {'status': 'failure', 'message': 'Error proposing PR'}