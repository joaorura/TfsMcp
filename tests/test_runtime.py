from pathlib import Path
import types

from tfsmcp.runtime import build_runtime


class FakeRuntimeConfig:
    def __init__(self, tmp_path: Path, tf_path: str | None = "tf"):
        self.http_host = "127.0.0.1"
        self.http_port = 39393
        self.tf_path = tf_path
        self.command_timeout_seconds = 5
        self.max_unauthorized_retries = 1
        self.recovery_cooldown_seconds = 120
        self.session_create_auto_get = False
        self.tfs_scripts_path = tmp_path / "scripts"
        self.state_dir = tmp_path / "state"
        self.tfs_scripts_path.mkdir()


class FakeLocator:
    def __init__(self, resolved_path: str = "tf") -> None:
        self.resolved_path = resolved_path

    def locate(self) -> str:
        return self.resolved_path


class FakeRunnerForRuntime:
    def __init__(self, tf_path: str, timeout_seconds: int, working_directory: str | None = None) -> None:
        self.tf_path = tf_path
        self.timeout_seconds = timeout_seconds
        self.working_directory = working_directory

    def run(self, args):
        raise AssertionError("runtime wiring test should not execute tf commands")


class FakeOnboardingAdvisor:
    def __init__(self, detector) -> None:
        self.detector = detector

    def build(self, path: str):
        return {"projectKind": "tfs_mapped", "path": path}


def test_build_runtime_wires_dependencies(tmp_path, monkeypatch):
    captured = {}

    def fake_recovery_manager(scripts_dir, run_script, cooldown_seconds=0):
        captured["scripts_dir"] = scripts_dir
        captured["run_script"] = run_script
        captured["cooldown_seconds"] = cooldown_seconds
        return object()

    monkeypatch.setattr("tfsmcp.runtime.load_config", lambda: FakeRuntimeConfig(tmp_path))
    monkeypatch.setattr("tfsmcp.runtime.TfExeLocator", lambda: FakeLocator())
    monkeypatch.setattr("tfsmcp.runtime.TfCommandRunner", FakeRunnerForRuntime)
    monkeypatch.setattr("tfsmcp.runtime.UnauthorizedRecoveryManager", fake_recovery_manager)
    monkeypatch.setattr("tfsmcp.runtime.SessionManager", lambda store, actions: {"store": store, "actions": actions})
    monkeypatch.setattr("tfsmcp.runtime.TfsProjectOnboardingAdvisor", FakeOnboardingAdvisor)

    runtime = build_runtime()

    assert runtime.config.http_host == "127.0.0.1"
    assert runtime.executor._runner.tf_path == "tf"
    assert runtime.executor._runner.working_directory is None
    assert runtime.onboarding.detector is runtime.detector
    assert runtime.sessions["store"]._path.name == "sessions.json"
    assert runtime.sessions["actions"] is not None
    assert callable(runtime.sessions["actions"].create_workspace)
    assert captured["scripts_dir"] == tmp_path / "scripts"
    assert captured["cooldown_seconds"] == 120
    assert callable(captured["run_script"])
    monkeypatch.setattr("tfsmcp.runtime.subprocess.run", lambda command, check: types.SimpleNamespace(returncode=0))
    assert captured["run_script"](tmp_path / "scripts" / "recover.ps1") == 0
    assert captured["run_script"].__name__ == "run_recovery_script"


def test_build_runtime_uses_locator_when_tf_path_is_unset(tmp_path, monkeypatch):
    locator = FakeLocator("C:/Program Files/Microsoft Visual Studio/tf.exe")

    monkeypatch.setattr("tfsmcp.runtime.load_config", lambda: FakeRuntimeConfig(tmp_path, tf_path=None))
    monkeypatch.setattr("tfsmcp.runtime.TfExeLocator", lambda: locator)
    monkeypatch.setattr("tfsmcp.runtime.TfCommandRunner", FakeRunnerForRuntime)
    monkeypatch.setattr("tfsmcp.runtime.UnauthorizedRecoveryManager", lambda scripts_dir, run_script, cooldown_seconds=0: object())
    monkeypatch.setattr("tfsmcp.runtime.SessionManager", lambda store, actions: {"store": store, "actions": actions})
    monkeypatch.setattr("tfsmcp.runtime.TfsProjectOnboardingAdvisor", FakeOnboardingAdvisor)

    runtime = build_runtime()

    assert runtime.executor._runner.tf_path == "C:/Program Files/Microsoft Visual Studio/tf.exe"
    assert runtime.executor._runner.timeout_seconds == 5
    assert runtime.sessions["store"]._path.name == "sessions.json"
