from collections.abc import Sequence

from tfsmcp.contracts import CommandResult
from tfsmcp.tfs.auth import is_pat_valid, request_auth_credentials


class RetryingTfsExecutor:
    def __init__(self, runner, classifier, recovery_manager, max_retries: int, disable_pat_dialog: bool = False) -> None:
        self._runner = runner
        self._classifier = classifier
        self._recovery_manager = recovery_manager
        self._max_retries = max(0, max_retries)
        self._disable_pat_dialog = disable_pat_dialog

    def run(self, args: Sequence[str]) -> CommandResult:
        result = self._runner.run(args)
        result.category = self._classifier.classify(result)

        # 1. Tentar recuperação via PAT se houver erro de autorização
        # Apenas se o runner tiver suporte a autenticação (verificamos método set_auth)
        if result.category != "success" and hasattr(self._runner, "set_auth") and not self._disable_pat_dialog:
            # Verificar se o PAT atual é inválido ou se não temos um PAT (força solicitação se não houver PAT)
            if not is_pat_valid(self._runner):
                current_user = getattr(self._runner, "_tfs_user", None)
                current_pat = getattr(self._runner, "_tfs_pat", None)
                reason = result.stderr or result.stdout
                new_user, new_pat = request_auth_credentials(
                    current_user=current_user, 
                    current_pat=current_pat, 
                    reason=reason
                )
                
                if new_user == "SKIP":
                    # Usuário marcou para não usar PAT. Salvar preferência em memória.
                    self._disable_pat_dialog = True
                    # Tentar rodar o comando original uma vez sem o login (pode ser que scripts resolvam)
                    # mas se o comando falhou antes sem login, ele vai falhar de novo.
                    # Retornamos o resultado original para seguir para os scripts legados.
                    return result

                if new_pat:
                    # Atualizar runner e tentar novamente
                    self._runner.set_auth(new_user, new_pat)
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
