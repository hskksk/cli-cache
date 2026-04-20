import subprocess
import sys


def run_command(cmd_parts: list[str]) -> str:
    result = subprocess.run(cmd_parts, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(result.returncode)
    return result.stdout
