from collections.abc import Sequence
from pathlib import Path

from tfsmcp.contracts import CommandResult
from tfsmcp.tfs.classifier import TfOutputClassifier
from tfsmcp.tfs.executor import RetryingTfsExecutor
from tfsmcp.tfs.recovery import UnauthorizedRecoveryManager


class SequenceRunner:
    def __init__(self, results: Sequence[CommandResult]) -> None:
        self._results = list(results)
        self.calls = 0

    def run(self, args):
        self.calls += 1
        return self._results[self.calls - 1]


class FakeRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, args):
        self.calls += 1
        if self.calls == 1:
            return CommandResult(
                command=["tf", *args],
                exit_code=1,
                stdout="",
                stderr="TF30063: You are not authorized to access https://tfs.example.com/tfs.",
                category="raw",
            )
        return CommandResult(command=["tf", *args], exit_code=0, stdout="checked out", stderr="", category="raw")


def test_classifier_marks_unauthorized_result():
    classifier = TfOutputClassifier()
    result = CommandResult(
        command=["tf"],
        exit_code=1,
        stdout="",
        stderr="You are not authorized to access https://tfs.example.com/tfs.",
        category="raw",
    )

    assert classifier.classify(result) == "unauthorized"


def test_classifier_marks_tf30063_as_unauthorized():
    classifier = TfOutputClassifier()
    result = CommandResult(command=["tf"], exit_code=1, stdout="", stderr="TF30063: You are not authorized", category="raw")

    assert classifier.classify(result) == "unauthorized"


def test_classifier_marks_permission_denied_as_unauthorized():
    classifier = TfOutputClassifier()
    result = CommandResult(
        command=["tf"],
        exit_code=1,
        stdout="",
        stderr="The item $/SPF/SLN could not be found in your workspace, or you do not have permission to access it.",
        category="raw",
    )

    assert classifier.classify(result) == "unauthorized"


def test_classifier_does_not_mark_access_denied_as_unauthorized():
    classifier = TfOutputClassifier()
    result = CommandResult(command=["tf"], exit_code=1, stdout="", stderr="Access is denied", category="raw")

    assert classifier.classify(result) != "unauthorized"


def test_executor_does_not_retry_non_unauthorized_failures(tmp_path):
    runner = SequenceRunner(
        [
            CommandResult(command=["tf", "workfold"], exit_code=1, stdout="", stderr="workspace not found", category="raw"),
        ]
    )
    executed = []
    recovery = UnauthorizedRecoveryManager(tmp_path, lambda script: executed.append(script.name) or 0)
    executor = RetryingTfsExecutor(runner, TfOutputClassifier(), recovery, max_retries=3)

    result = executor.run(["workfold"])

    assert result.exit_code == 1
    assert result.category == "workspace_error"
    assert result.recovery_triggered is False
    assert result.retried is False
    assert result.recovery_scripts == []
    assert executed == []
    assert runner.calls == 1


def test_executor_does_not_retry_when_max_retries_is_zero(tmp_path):
    runner = SequenceRunner(
        [
            CommandResult(
                command=["tf", "checkout"],
                exit_code=1,
                stdout="",
                stderr="TF30063: You are not authorized to access https://tfs.example.com/tfs.",
                category="raw",
            ),
        ]
    )
    executed = []
    recovery = UnauthorizedRecoveryManager(tmp_path, lambda script: executed.append(script.name) or 0)
    executor = RetryingTfsExecutor(runner, TfOutputClassifier(), recovery, max_retries=0)

    result = executor.run(["checkout", "D:/TFS/SPF/file.cs"])

    assert result.exit_code == 1
    assert result.category == "unauthorized"
    assert result.recovery_triggered is False
    assert result.retried is False
    assert result.recovery_scripts == []
    assert executed == []
    assert runner.calls == 1


def test_executor_runs_all_scripts_and_retries_once(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "01-login.ps1").write_text("Write-Host one", encoding="utf-8")
    (scripts_dir / "02-context.ps1").write_text("Write-Host two", encoding="utf-8")

    executed = []
    recovery = UnauthorizedRecoveryManager(scripts_dir, lambda script: executed.append(script.name) or 0)
    executor = RetryingTfsExecutor(FakeRunner(), TfOutputClassifier(), recovery, max_retries=1)

    result = executor.run(["checkout", "D:/TFS/SPF/file.cs"])

    assert result.exit_code == 0
    assert result.recovery_triggered is True
    assert result.retried is True
    assert result.recovery_scripts == ["01-login.ps1", "02-context.ps1"]
    assert executed == ["01-login.ps1", "02-context.ps1"]


def test_executor_does_not_retry_when_recovery_script_fails(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "01-login.ps1").write_text("exit 1", encoding="utf-8")

    executed = []
    recovery = UnauthorizedRecoveryManager(scripts_dir, lambda script: executed.append(script.name) or 1)
    runner = SequenceRunner(
        [
            CommandResult(
                command=["tf", "checkout"],
                exit_code=1,
                stdout="",
                stderr="TF30063: You are not authorized to access https://tfs.example.com/tfs.",
                category="raw",
            ),
        ]
    )
    executor = RetryingTfsExecutor(runner, TfOutputClassifier(), recovery, max_retries=1)

    result = executor.run(["checkout", "D:/TFS/SPF/file.cs"])

    assert result.exit_code == 1
    assert result.category == "unauthorized"
    assert result.recovery_triggered is True
    assert result.retried is False
    assert result.recovery_scripts == ["01-login.ps1"]
    assert executed == ["01-login.ps1"]
    assert runner.calls == 1


def test_executor_retries_only_once_even_with_higher_budget(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "01-login.ps1").write_text("Write-Host one", encoding="utf-8")

    executed = []
    recovery = UnauthorizedRecoveryManager(scripts_dir, lambda script: executed.append(script.name) or 0)
    runner = SequenceRunner(
        [
            CommandResult(
                command=["tf", "checkout"],
                exit_code=1,
                stdout="",
                stderr="TF30063: You are not authorized to access https://tfs.example.com/tfs.",
                category="raw",
            ),
            CommandResult(
                command=["tf", "checkout"],
                exit_code=1,
                stdout="",
                stderr="TF30063: You are not authorized to access https://tfs.example.com/tfs.",
                category="raw",
            ),
            CommandResult(command=["tf", "checkout"], exit_code=0, stdout="checked out", stderr="", category="raw"),
        ]
    )
    executor = RetryingTfsExecutor(runner, TfOutputClassifier(), recovery, max_retries=2)

    result = executor.run(["checkout", "D:/TFS/SPF/file.cs"])

    assert result.exit_code == 1
    assert result.category == "unauthorized"
    assert result.recovery_triggered is True
    assert result.retried is True
    assert result.recovery_scripts == ["01-login.ps1"]
    assert executed == ["01-login.ps1"]
    assert runner.calls == 2


def test_executor_retries_unknown_failure_exit_100(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "01-login.ps1").write_text("Write-Host auth", encoding="utf-8")

    executed = []
    recovery = UnauthorizedRecoveryManager(scripts_dir, lambda script: executed.append(script.name) or 0)
    runner = SequenceRunner(
        [
            CommandResult(command=["tf", "checkout"], exit_code=100, stdout="", stderr="", category="raw"),
            CommandResult(command=["tf", "checkout"], exit_code=0, stdout="ok", stderr="", category="raw"),
        ]
    )
    executor = RetryingTfsExecutor(runner, TfOutputClassifier(), recovery, max_retries=1)

    result = executor.run(["checkout", "D:/TFS/SPF/file.cs"])

    assert result.exit_code == 100
    assert result.category == "unknown_failure"
    assert result.recovery_triggered is False
    assert result.retried is False
    assert result.recovery_scripts == []
    assert executed == []


def test_executor_does_not_recover_unknown_100_for_workfold_detection(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "01-login.ps1").write_text("Write-Host auth", encoding="utf-8")

    executed = []
    recovery = UnauthorizedRecoveryManager(scripts_dir, lambda script: executed.append(script.name) or 0)
    runner = SequenceRunner(
        [
            CommandResult(command=["tf", "workfold"], exit_code=100, stdout="", stderr="", category="raw"),
        ]
    )
    executor = RetryingTfsExecutor(runner, TfOutputClassifier(), recovery, max_retries=1)

    result = executor.run(["workfold", "D:/TFS/SPF/develop"])

    assert result.exit_code == 100
    assert result.category == "unknown_failure"
    assert result.recovery_triggered is False
    assert result.retried is False
    assert result.recovery_scripts == []
    assert executed == []
    assert runner.calls == 1


def test_executor_handles_pat_recovery_with_user_and_token(tmp_path):
    from unittest.mock import MagicMock, patch

    mock_runner = MagicMock()
    mock_runner._tfs_pat = "old-pat"
    mock_runner._tfs_user = "old-user"

    # First call fails with unauthorized, second succeeds
    mock_runner.run.side_effect = [
        CommandResult(command=["tf"], exit_code=1, stdout="", stderr="TF30063", category="raw"),
        CommandResult(command=["tf"], exit_code=0, stdout="ok", stderr="", category="raw"),
    ]

    classifier = TfOutputClassifier()

    with patch("tfsmcp.tfs.executor.request_auth_credentials") as mock_auth, \
         patch("tfsmcp.tfs.executor.is_pat_valid", return_value=False):

        mock_auth.return_value = ("new-user", "new-pat")

        executor = RetryingTfsExecutor(mock_runner, classifier, None, max_retries=1)
        result = executor.run(["checkout"])

        assert result.exit_code == 0
        assert mock_runner.set_auth.called
        mock_runner.set_auth.assert_called_with("new-user", "new-pat")
        assert result.recovery_triggered is True


def test_executor_skips_pat_dialog_if_configured_but_still_runs_recovery(tmp_path):
    """disable_pat_dialog=True (via config) deve pular o diálogo PAT mas ainda rodar recovery scripts."""
    from unittest.mock import MagicMock, patch

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "01-login.ps1").write_text("Write-Host one", encoding="utf-8")

    executed = []

    class SequenceRunnerAuth:
        def __init__(self):
            self.calls = 0
        def run(self, args):
            self.calls += 1
            if self.calls == 1:
                return CommandResult(command=["tf", *args], exit_code=1, stdout="", stderr="TF30063: You are not authorized", category="raw")
            return CommandResult(command=["tf", *args], exit_code=0, stdout="ok", stderr="", category="raw")

    runner = SequenceRunnerAuth()
    recovery = UnauthorizedRecoveryManager(scripts_dir, lambda script: executed.append(script.name) or 0)
    classifier = TfOutputClassifier()

    with patch("tfsmcp.tfs.executor.request_auth_credentials") as mock_auth:
        executor = RetryingTfsExecutor(runner, classifier, recovery, max_retries=1, disable_pat_dialog=True)
        result = executor.run(["checkout"])

        assert result.exit_code == 0
        assert not mock_auth.called, "Diálogo PAT não deve aparecer quando disable_pat_dialog=True"
        assert executed == ["01-login.ps1"], "Recovery scripts devem rodar mesmo com disable_pat_dialog=True"


def test_executor_disables_dialog_and_skips_recovery_on_cancel(tmp_path):
    """Cancelling the PAT dialog (None, None) must disable auth permanently and skip recovery scripts."""
    from unittest.mock import MagicMock, patch

    mock_runner = MagicMock()
    mock_runner._tfs_pat = None
    mock_runner.run.return_value = CommandResult(
        command=["tf"], exit_code=1, stdout="", stderr="TF30063: You are not authorized", category="raw"
    )

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "01-login.ps1").write_text("Write-Host one", encoding="utf-8")

    executed = []
    recovery = UnauthorizedRecoveryManager(scripts_dir, lambda script: executed.append(script.name) or 0)
    classifier = TfOutputClassifier()

    with patch("tfsmcp.tfs.executor.request_auth_credentials") as mock_auth, \
         patch("tfsmcp.tfs.executor.is_pat_valid", return_value=False):

        # Simular cancelamento: retorna (None, None)
        mock_auth.return_value = (None, None)

        executor = RetryingTfsExecutor(mock_runner, classifier, recovery, max_retries=1)

        # Primeira chamada: mostra dialog, usuário cancela
        result1 = executor.run(["checkout"])
        assert result1.category == "unauthorized"
        assert mock_auth.call_count == 1
        assert executed == [], "Recovery scripts não devem rodar após cancelamento"

        # Segunda chamada: não deve mostrar dialog nem rodar scripts
        result2 = executor.run(["checkout"])
        assert result2.category == "unauthorized"
        assert mock_auth.call_count == 1, "Dialog não deve aparecer novamente após cancelamento"
        assert executed == []


def test_executor_disables_dialog_but_runs_recovery_on_skip(tmp_path):
    """SKIP no dialog deve desabilitar apenas o diálogo PAT; scripts de recuperação PS1 devem rodar."""
    from unittest.mock import MagicMock, patch

    mock_runner = MagicMock()
    mock_runner._tfs_pat = None
    mock_runner.run.return_value = CommandResult(
        command=["tf"], exit_code=1, stdout="", stderr="TF30063: You are not authorized", category="raw"
    )

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "01-login.ps1").write_text("Write-Host one", encoding="utf-8")

    executed = []
    recovery = UnauthorizedRecoveryManager(scripts_dir, lambda script: executed.append(script.name) or 0)
    classifier = TfOutputClassifier()

    with patch("tfsmcp.tfs.executor.request_auth_credentials") as mock_auth, \
         patch("tfsmcp.tfs.executor.is_pat_valid", return_value=False):

        mock_auth.return_value = ("SKIP", "SKIP")

        executor = RetryingTfsExecutor(mock_runner, classifier, recovery, max_retries=1)

        result1 = executor.run(["checkout"])
        assert result1.category == "unauthorized"
        assert mock_auth.call_count == 1
        assert executed == ["01-login.ps1"], "Recovery scripts devem rodar após SKIP (usuário quer PS1)"

        result2 = executor.run(["checkout"])
        assert result2.category == "unauthorized"
        assert mock_auth.call_count == 1, "Dialog não deve aparecer novamente após SKIP"
        # Cooldown ativo — scripts não reexecutam imediatamente
        assert executed == ["01-login.ps1"]


def test_executor_forces_dialog_if_pat_missing_and_command_fails(tmp_path):
    from unittest.mock import MagicMock, patch

    mock_runner = MagicMock()
    mock_runner._tfs_pat = None
    mock_runner.run.return_value = CommandResult(command=["tf"], exit_code=1, stdout="", stderr="Any error", category="raw")

    classifier = TfOutputClassifier()

    with patch("tfsmcp.tfs.executor.request_auth_credentials") as mock_auth, \
         patch("tfsmcp.tfs.executor.is_pat_valid", return_value=False):

        mock_auth.return_value = ("new-user", "new-pat")

        executor = RetryingTfsExecutor(mock_runner, classifier, None, max_retries=1)
        executor.run(["checkout"])

        assert mock_auth.called
