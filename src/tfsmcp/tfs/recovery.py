from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RecoveryRunResult:
    scripts: list[str]
    succeeded: bool


class UnauthorizedRecoveryManager:
    def __init__(self, scripts_dir: Path, run_script: Callable[[Path], int]) -> None:
        self._scripts_dir = scripts_dir
        self._run_script = run_script

    def run_scripts(self) -> RecoveryRunResult:
        executed: list[str] = []
        for script in sorted(self._scripts_dir.glob("*.ps1")):
            exit_code = self._run_script(script)
            executed.append(script.name)
            if exit_code != 0:
                return RecoveryRunResult(scripts=executed, succeeded=False)
        return RecoveryRunResult(scripts=executed, succeeded=True)
