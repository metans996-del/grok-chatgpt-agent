import os
import tempfile
import time
import subprocess
from github import Github, ContentFile
from typing import Tuple


def require_env(name: str) -> str:
    """Гарантирует что переменная окружения существует (для mypy)."""
    value = os.getenv(name)
    if value is None:
        raise RuntimeError(f"Environment variable '{name}' is missing")
    return value


GITHUB_TOKEN: str = require_env("GH_PAT")
REPO_NAME: str = require_env("REPO_NAME")
SANDBOX_IMAGE: str = os.getenv("SANDBOX_IMAGE", "sandbox-test:latest")


def clone_repo(tmpdir: str) -> None:
    repo_url = f"https://{GITHUB_TOKEN}:x-oauth-basic@github.com/{REPO_NAME}.git"
    subprocess.run(["git", "clone", repo_url, tmpdir], check=True)


def run_tests_in_docker(repo_dir: str) -> Tuple[bool, str]:
    build = subprocess.run(
        ["docker", "build", "-t", SANDBOX_IMAGE, "."],
        cwd=repo_dir
    )
    if build.returncode != 0:
        return False, "Docker build failed"

    run = subprocess.run(
        ["docker", "run", "--rm", SANDBOX_IMAGE],
        cwd=repo_dir
    )

    if run.returncode == 0:
        return True, "Tests OK"
    return False, f"Tests failed (code {run.returncode})"


def create_branch_and_pr(file_path: str, new_content: str, title: str, body: str) -> str:
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)

    base = repo.get_branch(repo.default_branch)
    branch_name = f"agent-proposal/{int(time.time())}"

    repo.create_git_ref(
        ref=f"refs/heads/{branch_name}",
        sha=base.commit.sha
    )

    contents_raw = repo.get_contents(file_path, ref=repo.default_branch)

    # Явное приведение типов — теперь mypy НЕ ругается
    if isinstance(contents_raw, list):
        raise RuntimeError("Unexpected: get_contents returned a list")
    contents: ContentFile = contents_raw

    repo.update_file(
        path=file_path,
        message=f"[agent] {title}",
        content=new_content,
        sha=contents.sha,
        branch=branch_name
    )

    pr = repo.create_pull(
        title=title,
        body=body,
        head=branch_name,
        base=repo.default_branch
    )

    return pr.html_url


def propose_change_example() -> None:
