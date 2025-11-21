import subprocess
import shutil
import sys
from typing import Tuple

# Находим полный путь к docker
docker_path = shutil.which("docker")
if not docker_path:
    raise RuntimeError("Docker не найден в PATH")


def run_sandbox_tests(path: str = ".") -> Tuple[bool, str]:
    """Собирает Docker образ и запускает контейнер с тестами"""
    build = subprocess.run([docker_path, "build", "-t", "sandbox-test:local", "."], cwd=path)
    if build.returncode != 0:
        return False, "Build failed"

    run = subprocess.run([docker_path, "run", "--rm", "sandbox-test:local"], cwd=path)
    if run.returncode == 0:
        return True, "OK"
    return False, f"Fail code {run.returncode}"


def main() -> None:
    ok, msg = run_sandbox_tests()
    print(ok, msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
