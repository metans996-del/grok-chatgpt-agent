import os
import tempfile
import time
import subprocess
from typing import Tuple
from github import Github


def require_env(name: str) -> str:
    """Гарантирует, что переменная окружения существует."""
    value = os.getenv(name)
    if value is None:
        raise RuntimeError(f"Environment variable '{name}' is missing")
    return value


GITHUB_TOKEN: str = require_env("ZXC")
REPO_NAME: str = require_env("REPO_NAME")
SANDBOX_IMAGE: str = os.getenv("SANDBOX_IMAGE", "sandbox-test:latest")


def safe_run(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    """Безопасный запуск git/docker."""
    allowed = {"git", "docker"}
    if cmd[0] not in allowed:
        raise RuntimeError(f"Blocked unsafe command: {cmd[0]}")
    return subprocess.run(cmd, cwd=cwd, check=True)


def clone_repo(tmpdir: str) -> None:
    repo_url = f"https://{GITHUB_TOKEN}:x-oauth-basic@github.com/{REPO_NAME}.git"
    safe_run(["git", "clone", repo_url, tmpdir])


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


def create_branch_and_pr(
    file_path: str,
    new_content: str,
    title: str,
    body: str
) -> str:
    """Создаёт ветку и Pull Request в GitHub."""
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)

    base = repo.get_branch(repo.default_branch)
    branch_name = f"agent-proposal/{int(time.time())}"

    repo.create_git_ref(
        ref=f"refs/heads/{branch_name}",
        sha=base.commit.sha
    )

    contents = repo.get_contents(file_path, ref=repo.default_branch)
    assert not isinstance(contents, list)

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
    """Пример автоматического предложения изменений."""
    with tempfile.TemporaryDirectory() as d:
        clone_repo(d)

        target = os.path.join(d, "agent", "sample_module.py")
        if not os.path.exists(target):
            print("Target file not found:", target)
            return

        with open(target, "r", encoding="utf-8") as f:
            src = f.read()

        new_src = src.replace("TODO_FIX_ME", "fixed_by_agent()")

        ok, msg = run_tests_in_docker(d)

        pr_url = create_branch_and_pr(
            "agent/sample_module.py",
            new_src,
            "Agent: автопредложение фикса",
            f"Результат тестов: {msg}"
        )

        print("PR создан:", pr_url)


if __name__ == "__main__":
    propose_change_example()
