from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import time


@dataclass(slots=True)
class RecoveryRunResult:
    scripts: list[str]
    succeeded: bool


class UnauthorizedRecoveryManager:
    def __init__(
        self,
        scripts_dir: Path,
        run_script: Callable[[Path], int],
        cooldown_seconds: int = 120,
        now_fn: Callable[[], float] | None = None,
    ) -> None:
        self._scripts_dir = scripts_dir
        self._run_script = run_script
        self._cooldown_seconds = max(0, cooldown_seconds)
        self._now_fn = now_fn or time.monotonic
        self._last_run_at: float | None = None

    def run_scripts(self) -> RecoveryRunResult:
        now = self._now_fn()
        if self._last_run_at is not None and (now - self._last_run_at) < self._cooldown_seconds:
            # Cooldown active: avoid reopening interactive auth scripts repeatedly.
            return RecoveryRunResult(scripts=[], succeeded=True)

        self._last_run_at = now
        executed: list[str] = []
        for script in sorted(self._scripts_dir.glob("*.ps1")):
            exit_code = self._run_script(script)
            executed.append(script.name)
            if exit_code != 0:
                return RecoveryRunResult(scripts=executed, succeeded=False)
        return RecoveryRunResult(scripts=executed, succeeded=True)
