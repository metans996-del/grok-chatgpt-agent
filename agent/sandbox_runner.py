import subprocess


def run_in_sandbox(code: str) -> str:
    """Run the provided code in a sandboxed environment."""
    # TODO: Implement actual sandboxing logic
    # For now, just execute the code directly
    try:
        output = subprocess.check_output(code, shell=True, text=True)
        return output
    except subprocess.CalledProcessError as e:
        return f"Error: {e}"
