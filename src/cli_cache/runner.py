import subprocess
import sys


def run_command(cmd_parts: list[str]) -> str:
    result = subprocess.run(cmd_parts, stdout=subprocess.PIPE, text=True)
    if result.returncode != 0:
        sys.exit(result.returncode)
    return result.stdout
