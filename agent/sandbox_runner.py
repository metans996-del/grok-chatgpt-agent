import subprocess
import sys


def run_sandbox_tests(path="."):
    res = subprocess.run(["docker", "build", "-t", "sandbox-test:local", "."], cwd=path)
    if res.returncode != 0:
        return False, "Build failed"

    r = subprocess.run(["docker", "run", "--rm", "sandbox-test:local"], cwd=path)
    return r.returncode == 0, "OK" if r.returncode == 0 else f"Fail code {r.returncode}"


def main():
    ok, msg = run_sandbox_tests()
    print(ok, msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
