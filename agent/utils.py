import requests
import json


def get_repo_files(repo_owner, repo_name):
    url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/git/trees/main'
    headers = {'Authorization': 'Bearer YOUR_GITHUB_TOKEN'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        tree = json.loads(response.content)
        files = []
        for item in tree['tree']:
            files.append(item['path'])
        return files
    else:
        return []


def find_file(repo_owner, repo_name, file_name):
    files = get_repo_files(repo_owner, repo_name)
    for file in files:
        if file == file_name:
            return file
    return None