import os
import re
import subprocess
from typing import List

from agent.utils import get_repo_name, get_repo_owner, get_root_dir


def get_changed_files() -> List[str]:
    """Get list of changed files in the current pull request."""
    repo_name = get_repo_name()
    repo_owner = get_repo_owner()
    pr_number = os.environ["PR_NUMBER"]

    cmd = f"gh pr view {pr_number} --repo {repo_owner}/{repo_name} --json files"
    output = subprocess.check_output(cmd, shell=True, text=True)

    # Parse the output to extract changed file paths
    pattern = r'"path": "(.*?)"'
    changed_files = re.findall(pattern, output)

    return changed_files


def propose_changes():
    """Propose changes for the pull request."""
    changed_files = get_changed_files()

    print("Changed files:")
    for file in changed_files:
        print(file)

    # TODO: Analyze changed files and generate suggestions
    # Placeholder suggestion
    suggestion = "Here's a suggestion for your pull request:\n\n"
    suggestion += "- Consider adding more tests to improve coverage.\n"
    suggestion += "- Update the documentation to reflect the changes."

    # Create a comment on the pull request with the suggestion
    repo_name = get_repo_name()
    repo_owner = get_repo_owner()
    pr_number = os.environ["PR_NUMBER"]

    cmd = f'gh pr comment {pr_number} --repo {repo_owner}/{repo_name} --body "{suggestion}"'
    subprocess.run(cmd, shell=True, check=True)


if __name__ == "__main__":
    propose_changes()
