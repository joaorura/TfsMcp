import threading
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
        # Separar "diálogo PAT desabilitado por config" de "usuário optou por sair de toda auth na sessão".
        # _user_opted_out_auth bloqueia tanto o diálogo PAT quanto os scripts de recuperação.
        self._user_opted_out_auth = False
        self._auth_lock = threading.Lock()

    def run(self, args: Sequence[str]) -> CommandResult:
        result = self._runner.run(args)
        result.category = self._classifier.classify(result)

        # 1. Tentar recuperação via PAT se houver erro de autorização
        # Apenas se o runner tiver suporte a autenticação e o usuário não tiver optado por sair.
        if result.category != "success" and hasattr(self._runner, "set_auth") and not self._disable_pat_dialog and not self._user_opted_out_auth:
            # Usar lock para garantir que somente um diálogo de autenticação apareça por vez.
            # Se outra thread já está tratando auth, pula este bloco sem tentar novamente.
            acquired = self._auth_lock.acquire(blocking=False)
            if acquired:
                try:
                    # Re-verificar os flags após adquirir o lock (outra thread pode ter alterado)
                    if not self._disable_pat_dialog and not self._user_opted_out_auth and not is_pat_valid(self._runner):
                        current_user = getattr(self._runner, "_tfs_user", None)
                        current_pat = getattr(self._runner, "_tfs_pat", None)
                        reason = result.stderr or result.stdout
                        new_user, new_pat = request_auth_credentials(
                            current_user=current_user,
                            current_pat=current_pat,
                            reason=reason
                        )

                        if new_user is None:
                            # Usuário cancelou o diálogo — bloquear diálogo E scripts nesta sessão.
                            self._disable_pat_dialog = True
                            self._user_opted_out_auth = True
                            return result

                        if new_user == "SKIP":
                            # Usuário marcou "Não usar PAT" — desabilitar apenas o diálogo PAT.
                            # Os scripts de recuperação PS1 devem continuar sendo executados.
                            self._disable_pat_dialog = True
                            # Não retorna: deixa o fluxo cair para os scripts de recovery abaixo.

                        if new_pat and new_user != "SKIP":
                            # Atualizar runner e tentar novamente
                            self._runner.set_auth(new_user, new_pat)
                            result = self._runner.run(args)
                            result.category = self._classifier.classify(result)
                            result.recovery_triggered = True
                            result.retried = True

                            if result.category != "unauthorized":
                                return result
                finally:
                    self._auth_lock.release()

        # 2. Se o usuário optou por sair de toda auth na sessão, não executar scripts de recuperação.
        # Nota: _disable_pat_dialog vindo do config NÃO bloqueia os scripts — apenas o diálogo PAT.
        if self._user_opted_out_auth:
            return result

        # 3. Fallback para scripts de recuperação legados
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
        if result.category != "unauthorized":
            return False
        # Comandos puramente de leitura de metadados de workspace não ativam scripts de recovery
        # pois não são operações explícitas do usuário e não valem consumir o cooldown.
        # workfold e info são exceção: são chamados por tfs_detect_project / tfs_onboard_project
        # e precisam funcionar para que a autenticação seja resolvida.
        _PASSIVE_COMMANDS = {"workspaces", "properties"}
        first_arg = args[0].lower() if args else ""
        return first_arg not in _PASSIVE_COMMANDS
