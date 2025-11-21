import subprocess
from pathlib import Path
from typing import Tuple


def run_sandbox_tests(path: str | Path = ".") -> Tuple[bool, str]:
    repo_path = str(path)

    build = subprocess.run(
        ["docker", "build", "-t", "sandbox-test:local", "."],
        cwd=repo_path
    )
    if build.returncode != 0:
        return False, "Build failed"

    run = subprocess.run(
        ["docker", "run", "--rm", "sandbox-test:local"],
        cwd=repo_path
    )
    if run.returncode == 0:
        return True, "OK"

    return False, f"Fail code {run.returncode}"


if __name__ == "__main__":
    ok, msg = run_sandbox_tests()
    print(ok, msg)
