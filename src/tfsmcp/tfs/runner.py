import subprocess
from collections.abc import Sequence

from tfsmcp.contracts import CommandResult


class TfCommandRunner:
    def __init__(self, tf_path: str, timeout_seconds: int, working_directory: str | None = None) -> None:
        self._tf_path = tf_path
        self._timeout_seconds = timeout_seconds
        self._working_directory = working_directory

    def run(self, args: Sequence[str]) -> CommandResult:
        command = [self._tf_path, *args]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=False,
                timeout=self._timeout_seconds,
                check=False,
                cwd=self._working_directory,
            )
            return CommandResult(
                command=command,
                exit_code=result.returncode,
                stdout=self._decode_output(result.stdout),
                stderr=self._decode_output(result.stderr),
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

    @staticmethod
    def _decode_output(raw: str | bytes | None) -> str:
        if raw is None:
            return ""
        if isinstance(raw, str):
            return raw

        for encoding in ("utf-8", "mbcs", "cp1252", "cp850"):
            try:
                return raw.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue

        return raw.decode("utf-8", errors="replace")
