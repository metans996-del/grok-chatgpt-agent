import logging
import os
from typing import Dict, List

import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


def propose_pr(owner: str, repo: str, head: str, base: str, token: str) -> Dict[str, str]:
    url = f'https://api.github.com/repos/{owner}/{repo}/pulls'
    headers = {'Authorization': f'token {token}', 'Content-Type': 'application/json'}
    data = {'head': head, 'base': base, 'title': 'Automated PR'}
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return {'status': 'success', 'message': 'PR created successfully'}
    except RequestException as e:
        logger.error(f'Error proposing PR: {e}')
        return {'status': 'failure', 'message': 'Error proposing PR'}
