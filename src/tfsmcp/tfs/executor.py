from collections.abc import Sequence

from tfsmcp.contracts import CommandResult


class RetryingTfsExecutor:
    def __init__(self, runner, classifier, recovery_manager, max_retries: int) -> None:
        self._runner = runner
        self._classifier = classifier
        self._recovery_manager = recovery_manager
        self._max_retries = max(0, max_retries)

    def run(self, args: Sequence[str]) -> CommandResult:
        result = self._runner.run(args)
        result.category = self._classifier.classify(result)

        # Fallback policy: at most one recovery cycle per operation.
        retries_remaining = 1 if self._max_retries > 0 else 0
        while self._should_try_recovery(args, result) and retries_remaining > 0:
            recovery = self._recovery_manager.run_scripts()
            result.recovery_triggered = True
            result.recovery_scripts = recovery.scripts
            if not recovery.succeeded:
                return result

            result = self._runner.run(args)
            result.category = self._classifier.classify(result)
            result.recovery_triggered = True
            result.retried = True
            result.recovery_scripts = recovery.scripts
            retries_remaining -= 1

        return result

    @staticmethod
    def _should_try_recovery(args: Sequence[str], result: CommandResult) -> bool:
        _ = args
        return result.category == "unauthorized"
