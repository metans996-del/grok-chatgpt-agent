import subprocess
from pathlib import Path
from typing import Tuple


def run_sandbox_tests(path: str | Path = ".") -> Tuple[bool, str]:
    """
    Запускает тесты в изолированном Docker-контейнере.

    Args:
        path: Путь к репозиторию (по умолчанию текущая директория)

    Returns:
        Tuple[bool, str]: (успех, сообщение)
    """
    repo_path = str(path)

    # Указываем путь к Dockerfile на уровень выше
    dockerfile_path = Path(repo_path).parent / "Dockerfile"

    build = subprocess.run(
        [
            "docker",
            "build",
            "-f",
            str(dockerfile_path),
            "-t",
            "sandbox-test:local",
            str(dockerfile_path.parent),
        ],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if build.returncode != 0:
        return False, f"Build failed:\n{build.stderr}"

    run = subprocess.run(
        ["docker", "run", "--rm", "sandbox-test:local"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if run.returncode == 0:
        return True, "OK"

    return False, f"Tests failed (exit code {run.returncode}):\n{run.stderr}"


if __name__ == "__main__":
    ok, msg = run_sandbox_tests()
    print(ok, msg)