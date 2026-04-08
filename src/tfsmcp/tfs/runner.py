import subprocess
from collections.abc import Sequence

from tfsmcp.contracts import CommandResult


class TfCommandRunner:
    def __init__(self, tf_path: str, timeout_seconds: int) -> None:
        self._tf_path = tf_path
        self._timeout_seconds = timeout_seconds

    def run(self, args: Sequence[str]) -> CommandResult:
        command = [self._tf_path, *args]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                check=False,
            )
            return CommandResult(
                command=command,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                category="raw",
            )
        except FileNotFoundError as exc:
            return CommandResult(
                command=command,
                exit_code=1,
                stdout="",
                stderr=str(exc),
                category="raw",
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                command=command,
                exit_code=1,
                stdout="",
                stderr=f"Command '{' '.join(command)}' timed out after {exc.timeout} seconds",
                category="raw",
            )
