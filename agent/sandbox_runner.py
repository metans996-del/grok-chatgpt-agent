import os
from github import GithubException

class SandboxRunner:
    # ...

    def run_issue_command(self, action, new_branch_name, file_path):
        # ...
        elif action == 'delete':
            try:
                file = self.repo.get_contents(file_path, ref=new_branch_name)
            except GithubException as e:
                if e.status == 404:
                    print(f"Файл {file_path} не найден в ветке {new_branch_name}")
                    return
                else:
                    raise
            # ...
