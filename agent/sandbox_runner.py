import os
import subprocess
import tempfile


def run_python_code(code):
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
        f.write(code)
        f.flush()
        output = subprocess.check_output(['python', f.name], stderr=subprocess.STDOUT, universal_newlines=True)
        os.unlink(f.name)
        return output


def run_shell_command(command):
    try:
        output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, universal_newlines=True)
    except subprocess.CalledProcessError as e:
        output = e.output
    return output
