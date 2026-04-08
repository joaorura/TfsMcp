import subprocess
from pathlib import Path

from tfsmcp.tfs.locator import TfExeLocator
from tfsmcp.tfs.runner import TfCommandRunner


class Completed:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_locator_uses_vswhere_output(monkeypatch):
    monkeypatch.setattr("tfsmcp.tfs.locator.Path.exists", lambda self: True)
    monkeypatch.setattr(
        "tfsmcp.tfs.locator.subprocess.run",
        lambda *args, **kwargs: Completed(stdout="C:/VS\n"),
    )

    locator = TfExeLocator()

    assert locator.locate().endswith("tf.exe")


def test_locator_falls_back_when_discovered_tf_does_not_exist(monkeypatch):
    def fake_exists(path: Path) -> bool:
        return str(path).endswith("vswhere.exe")

    monkeypatch.setattr("tfsmcp.tfs.locator.Path.exists", fake_exists)
    monkeypatch.setattr(
        "tfsmcp.tfs.locator.subprocess.run",
        lambda *args, **kwargs: Completed(stdout="C:/VS\n"),
    )

    locator = TfExeLocator()

    assert locator.locate() == "tf"


def test_runner_returns_structured_result(monkeypatch):
    monkeypatch.setattr(
        "tfsmcp.tfs.runner.subprocess.run",
        lambda *args, **kwargs: Completed(stdout="ok", stderr="", returncode=0),
    )

    runner = TfCommandRunner("tf", timeout_seconds=5)
    result = runner.run(["status", "D:/TFS/SPF"])

    assert result.command == ["tf", "status", "D:/TFS/SPF"]
    assert result.exit_code == 0
    assert result.stdout == "ok"
    assert result.stderr == ""


def test_runner_returns_structured_result_for_missing_tf(monkeypatch):
    def raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError("tf not found")

    monkeypatch.setattr("tfsmcp.tfs.runner.subprocess.run", raise_file_not_found)

    runner = TfCommandRunner("tf", timeout_seconds=5)
    result = runner.run(["workfold"])

    assert result.command == ["tf", "workfold"]
    assert result.exit_code != 0
    assert result.stdout == ""
    assert "tf not found" in result.stderr
    assert result.category == "raw"


def test_runner_returns_structured_result_for_timeout(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["tf", "status"], timeout=5)

    monkeypatch.setattr("tfsmcp.tfs.runner.subprocess.run", raise_timeout)

    runner = TfCommandRunner("tf", timeout_seconds=5)
    result = runner.run(["status"])

    assert result.command == ["tf", "status"]
    assert result.exit_code != 0
    assert result.stdout == ""
    assert "timed out" in result.stderr.lower()
    assert result.category == "raw"
    assert str(runner._timeout_seconds) in result.stderr
    assert "tf status" in result.stderr
    assert result.recovery_triggered is False
    assert result.retried is False
    assert result.recovery_scripts == []
