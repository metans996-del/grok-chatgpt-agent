import os


def get_repo_name() -> str:
    """Get the name of the current repository."""
    return os.environ["GITHUB_REPOSITORY"].split("/")[1]


def get_repo_owner() -> str:
    """Get the owner of the current repository."""
    return os.environ["GITHUB_REPOSITORY"].split("/")[0]


def get_root_dir() -> str:
    """Get the root directory of the repository."""
    return os.environ["GITHUB_WORKSPACE"]
