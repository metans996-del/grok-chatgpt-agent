import logging
import os
from typing import Dict, List

logger = logging.getLogger(__name__)


def get_env_variable(var_name: str) -> str:
    try:
        return os.environ[var_name]
    except KeyError:
        logger.error(f'Environment variable {var_name} not found')
        return ''
