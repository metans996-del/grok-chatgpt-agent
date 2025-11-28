import logging
import os
from typing import Dict, List

import requests
# ИСПРАВЛЕНИЕ: Добавляем HTTPError явно в except
from requests.exceptions import RequestException, HTTPError 

logger = logging.getLogger(__name__)


def propose_pr(owner: str, repo: str, head: str, base: str, token: str) -> Dict[str, str]:
    """
    Отправляет запрос на создание Pull Request в GitHub.
    Использует raise_for_status() для автоматической обработки HTTP-ошибок.
    """
    url = f'https://api.github.com/repos/{owner}/{repo}/pulls'
    headers = {'Authorization': f'token {token}', 'Content-Type': 'application/json'}
    data = {'head': head, 'base': base, 'title': 'Automated PR'}
    
    try:
        response = requests.post(url, headers=headers, json=data)
        
        # Если статус-код не 2xx (например, 400, 404, 500), вызывается HTTPError, 
        # и выполнение переходит в блок except.
        response.raise_for_status()
        
        # Если исключения не было, то запрос успешен (201 Created)
        # Мы добавляем PR URL, так как это полезно для дальнейшего использования
        return {'status': 'success', 'message': 'PR created successfully', 'pr_url': response.json().get('html_url', 'N/A')}
    
    except (HTTPError, RequestException) as e: # ИЗМЕНЕНИЕ ЗДЕСЬ - добавлено явное HTTPError
        
        # УЛУЧШЕНИЕ: Добавляем статус-код в сообщение об ошибке, если он доступен
        status_code_info = ''
        if isinstance(e, HTTPError) and e.response is not None:
             status_code_info = f" (Status: {e.response.status_code})"
             
        logger.error(f'Error proposing PR: {e}{status_code_info}')
        
        # В случае любой ошибки запроса (включая 4xx/5xx от raise_for_status) 
        # возвращаем 'failure'
        return {'status': 'failure', 'message': 'Error proposing PR'}