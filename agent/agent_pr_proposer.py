import os
import base64
from github import Github, GithubException


class AgentPRProposer:
    def __init__(self, github_token, repo_name):
        self.github = Github(github_token)
        self.repo = self.github.get_repo(repo_name)

    def propose_pr(self, title, body):
        default_branch = self.repo.default_branch
        head_branch = f"agent-pr-{os.urandom(4).hex()}"

        try:
            base = self.repo.get_branch(default_branch)
            self.repo.create_git_ref(f"refs/heads/{head_branch}", base.commit.sha)

            self.create_or_update_file(head_branch, "agent/utils.py", self.get_utils_code())
            self.create_or_update_file(head_branch, "agent/utils.txt", self.get_utils_txt())
            self.create_or_update_file(head_branch, "agent/monetization.txt", self.get_monetization_txt())

            pr = self.repo.create_pull(title=title, body=body, head=head_branch, base=default_branch)
            print(f"Created pull request: {pr.html_url}")

        except GithubException as e:
            print(f"Error: {e}")
            raise e

    def create_or_update_file(self, branch, file_path, content):
        try:
            contents = self.repo.get_contents(file_path, ref=branch)
            self.repo.update_file(contents.path, f"Update {file_path}", content, contents.sha, branch=branch)
        except:
            self.repo.create_file(file_path, f"Add {file_path}", content, branch=branch)

    def get_utils_code(self):
        return """\
def generate_code():
    # Add your code generation logic here
    return \"\"\"\
\"\"\"\


def analyze_code(code):
    # Add your code analysis logic here
    return "Analysis results"
"""

    def get_utils_txt(self):
        return "This file contains utility functions for the agent."

    def get_monetization_txt(self):
        return "Ideas for monetizing the agent project:
1. Offer premium features for a subscription fee.
2. Provide a paid API for developers to access the agent's capabilities.
3. Sell customized agent models trained on specific domains or tasks."
