import os
import subprocess
import tempfile

from github import Github


def get_repo(repo_name, github_token):
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    return repo


def create_pr(repo, title, description, head_branch, base_branch="main"):
    try:
        pr = repo.create_pull(title=title, body=description, head=head_branch, base=base_branch)
        print(f"Created pull request #{pr.number}")
    except Exception as e:
        print(f"Error creating pull request: {e}")


def propose_changes(repo_name, github_token):
    repo = get_repo(repo_name, github_token)
    head_branch = "agent-pr-proposal"
    base_branch = "main"

    with tempfile.TemporaryDirectory() as tmpdir:
        # Clone the repository
        repo_url = f"https://{github_token}@github.com/{repo_name}.git"
        subprocess.check_call(["git", "clone", repo_url, tmpdir])

        # Create a new branch
        subprocess.check_call(["git", "-C", tmpdir, "checkout", "-b", head_branch])

        # Make changes to files
        with open(os.path.join(tmpdir, "README.md"), "a") as f:
            f.write("\n\nChanges proposed by the agent.")

        # Commit the changes
        subprocess.check_call(["git", "-C", tmpdir, "add", "."])
        subprocess.check_call(["git", "-C", tmpdir, "commit", "-m", "Agent PR proposal"])

        # Push the changes
        subprocess.check_call(["git", "-C", tmpdir, "push", "-u", "origin", head_branch])

    # Create a pull request
    title = "Agent PR Proposal"
    description = "This PR contains changes proposed by the agent."
    create_pr(repo, title, description, head_branch, base_branch)


if __name__ == "__main__":
    github_token = os.environ["GITHUB_TOKEN"]
    repo_name = "metans996-del/grok-chatgpt-agent"
    propose_changes(repo_name, github_token)
