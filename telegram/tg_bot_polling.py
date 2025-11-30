import os
import json
from agent.utils import get_repo_files, find_file


def get_ci_file(repo_owner, repo_name):
    files = get_repo_files(repo_owner, repo_name)
    ci_file = find_file(repo_owner, repo_name, '.github/workflows/ci.yml')
    return ci_file


def add_pythonpath(ci_file):
    with open(ci_file, 'r') as f:
        data = json.load(f)
    data['env']['PYTHONPATH'] = '/app/src'
    with open(ci_file, 'w') as f:
        json.dump(data, f, indent=4)


def main():
    repo_owner = 'metans996-del'
    repo_name = 'grok-chatgpt-agent'
    ci_file = get_ci_file(repo_owner, repo_name)
    if ci_file:
        add_pythonpath(ci_file)
    else:
        print('ci.yml file not found')


if __name__ == '__main__':
    main()