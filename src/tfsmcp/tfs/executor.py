from collections.abc import Sequence

from tfsmcp.contracts import CommandResult
from tfsmcp.tfs.auth import is_pat_valid, request_new_pat


class RetryingTfsExecutor:
    def __init__(self, runner, classifier, recovery_manager, max_retries: int) -> None:
        self._runner = runner
        self._classifier = classifier
        self._recovery_manager = recovery_manager
        self._max_retries = max(0, max_retries)

    def run(self, args: Sequence[str]) -> CommandResult:
        result = self._runner.run(args)
        result.category = self._classifier.classify(result)

        # 1. Tentar recuperação via PAT se houver erro de autorização
        # Apenas se o runner tiver suporte a PAT (verificamos atributo _tfs_pat)
        if result.category == "unauthorized" and hasattr(self._runner, "_tfs_pat"):
            # Verificar se o PAT atual é inválido (evita loop se o runner for um mock simples sem set_auth)
            if hasattr(self._runner, "set_auth") and not is_pat_valid(self._runner):
                current_pat = getattr(self._runner, "_tfs_pat", None)
                reason = result.stderr or result.stdout
                new_pat = request_new_pat(current_pat=current_pat, reason=reason)
                
                if new_pat:
                    # Atualizar runner e tentar novamente
                    self._runner.set_auth(getattr(self._runner, "_tfs_user", None), new_pat)
                    result = self._runner.run(args)
                    result.category = self._classifier.classify(result)
                    result.recovery_triggered = True
                    result.retried = True
                    
                    if result.category != "unauthorized":
                        return result

        # 2. Fallback para scripts de recuperação legados
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
