# Простая версия: клонирует, вносит изменения в указанный файл, запускает тесты в docker и создаёт PR

import os
import tempfile
import time
import subprocess
from github import Github


GITHUB_TOKEN = os.getenv("ZXC")
REPO_NAME = os.getenv("metans996-del/grok-chatgpt-agent")  # e.g. your-username/grok-chatgpt-agent
SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "sandbox-test:latest")


def clone_repo(tmpdir):
    repo_url = f"https://{GITHUB_TOKEN}:x-oauth-basic@github.com/{REPO_NAME}.git"
    subprocess.run(["git", "clone", repo_url, tmpdir], check=True)


def run_tests_in_docker(repo_dir):
    p = subprocess.run(["docker", "build", "-t", SANDBOX_IMAGE, "."], cwd=repo_dir)
    if p.returncode != 0:
        return False, "Docker build failed"

    r = subprocess.run(["docker", "run", "--rm", SANDBOX_IMAGE], cwd=repo_dir)
    if r.returncode == 0:
        return True, "Tests OK"

    return False, f"Tests failed (code {r.returncode})"


def create_branch_and_pr(file_path, new_content, title, body):
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


def propose_change_example():
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
