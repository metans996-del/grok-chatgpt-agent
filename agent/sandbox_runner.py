import logging
import os
from typing import Dict, List

import docker
from docker.errors import DockerException

logger = logging.getLogger(__name__)


def run_sandbox(image: str, command: str) -> Dict[str, str]:
    try:
        client = docker.from_env()
        container = client.containers.run(image, command, detach=True)
        container.wait()
        output = container.logs(stdout=True, stderr=True).decode('utf-8')
        return {'status': 'success', 'output': output}
    except DockerException as e:
        logger.error(f'Error running sandbox: {e}')
        return {'status': 'failure', 'message': 'Error running sandbox'}
