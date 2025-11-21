# Простая версия: клонирует, вносит изменения в указанный файл, запускает тесты в docker и создаёт PR

import os
import tempfile
import time
import shutil
import subprocess
from github import Github
from typing import Tuple

# Переменные окружения
GITHUB_TOKEN = os.getenv("ZXC")
REPO_NAME = os.getenv("metans996-del/grok-chatgpt-agent")
SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "sandbox-test:latest")

# Проверка токена и репозитория
if not GITHUB_TOKEN or not REPO_NAME:
    raise RuntimeError("Не заданы GITHUB_TOKEN или REPO_NAME")

# Полные пути к git и docker
git_path = shutil.which("git")
docker_path = shutil.which("docker")
if not git_path or not docker_path:
    raise RuntimeError("Git или Docker не найдены в PATH")


def clone_repo(tmpdir: str) -> None:
    """Клонирует репозиторий в указанный каталог"""
    repo_url = f"https://{GITHUB_TOKEN}:x-oauth-basic@github.com/{REPO_NAME}.git"
    subprocess.run([git_path, "clone", repo_url, tmpdir], check=True)


def run_tests_in_docker(repo_dir: str) -> Tuple[bool, str]:
    """Собирает Docker образ и запускает контейнер с тестами"""
    build = subprocess.run([docker_path, "build", "-t", SANDBOX_IMAGE, "."], cwd=repo_dir)
    if build.returncode != 0:
        return False, "Docker build failed"

    run = subprocess.run([docker_path, "run", "--rm", SANDBOX_IMAGE], cwd=repo_dir)
    if run.returncode == 0:
        return True, "Tests OK"
    return False, f"Tests failed (code {run.returncode})"


def create_branch_and_pr(file_path: str, new_content: str, title: str, body: str) -> str:
    """Создаёт ветку, обновляет файл и создаёт Pull Request"""
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    base = repo.get_branch(repo.default_branch)

    branch_name = f"agent-proposal/{int(time.time())}"
    repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base.commit.sha)

    contents = repo.get_contents(file_path, ref=repo.default_branch)
    repo.update_file(
        path=file_path,
        message=f"[agent] {title}",
        content=new_content,
        sha=contents.sha,
        branch=branch_name,
    )

    pr = repo.create_pull(title=title, body=body, head=branch_name, base=repo.default_branch)
    return pr.html_url


def propose_change_example() -> None:
    """Пример функции, которая клонирует репозиторий, меняет файл и создаёт PR"""
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
            f"Результат тестов: {msg}",
        )

        print("PR создан:", pr_url)


if __name__ == "__main__":
    propose_change_example()
