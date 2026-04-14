from pathlib import Path

from tfsmcp.contracts import CommandResult
from tfsmcp.mcp_server import build_tool_handlers
from tfsmcp.runtime import Runtime, RuntimeSessionActions
from tfsmcp.sessions.manager import SessionManager
from tfsmcp.sessions.store import SessionStore
from tfsmcp.tfs.classifier import TfOutputClassifier
from tfsmcp.tfs.executor import RetryingTfsExecutor
from tfsmcp.tfs.recovery import UnauthorizedRecoveryManager


class FakeDetector:
    def detect(self, path: str):
        return {
            "kind": "tfs_mapped",
            "confidence": "high",
            "workspace_name": "SIM_WORKSPACE",
            "server_path": "$/SPF/Main",
            "local_path": path,
            "is_agent_ready": True,
        }


class FakeOnboarding:
    def build(self, path: str):
        return {
            "project_kind": "tfs_mapped",
            "confidence": "high",
            "workspace": {
                "name": "SIM_WORKSPACE",
                "serverPath": "$/SPF/Main",
                "localPath": path,
            },
            "recommended_workflow": {
                "beforeEdit": "checkout",
                "forParallelTask": "session_create",
                "forCheckpoint": "shelve",
                "forDiscard": "undo_or_session_discard",
            },
            "supports": {
                "basicTools": True,
                "hybridSessions": True,
                "unauthorizedRecovery": True,
            },
            "notes": [],
        }


class SequencedTfRunner:
    def __init__(self) -> None:
        self.commands = []
        self.checkout_calls = 0

    def run(self, args):
        self.commands.append(list(args))

        if args and args[0] == "checkout":
            self.checkout_calls += 1
            if self.checkout_calls == 1:
                return CommandResult(
                    command=["tf", *args],
                    exit_code=1,
                    stdout="",
                    stderr="TF30063: You are not authorized",
                    category="raw",
                )
            return CommandResult(
                command=["tf", *args],
                exit_code=0,
                stdout="checked out",
                stderr="",
                category="raw",
            )

        return CommandResult(
            command=["tf", *args],
            exit_code=0,
            stdout="ok",
            stderr="",
            category="raw",
        )


def build_runtime_with_simulated_tfs(tmp_path: Path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "01-auth.ps1").write_text("Write-Host auth", encoding="utf-8")
    (scripts_dir / "02-context.ps1").write_text("Write-Host context", encoding="utf-8")

    executed_scripts = []
    runner = SequencedTfRunner()
    recovery = UnauthorizedRecoveryManager(scripts_dir, lambda script: executed_scripts.append(script.name) or 0)
    executor = RetryingTfsExecutor(runner, TfOutputClassifier(), recovery, max_retries=1)

    session_store = SessionStore(tmp_path / "sessions.json")
    sessions = SessionManager(session_store, actions=RuntimeSessionActions(executor))
    runtime = Runtime(
        config=None,
        detector=FakeDetector(),
        onboarding=FakeOnboarding(),
        executor=executor,
        sessions=sessions,
    )
    handlers = build_tool_handlers(runtime)
    return handlers, runner, executed_scripts


def test_checkout_tool_triggers_recovery_and_retry_once(tmp_path):
    handlers, runner, executed_scripts = build_runtime_with_simulated_tfs(tmp_path)

    payload = handlers["tfs_checkout"]("D:/TFS/SPF/develop/Historico/Changelog.txt")

    assert payload.exit_code == 0
    assert payload.category == "success"
    assert payload.recovery_triggered is True
    assert payload.retried is True
    assert payload.recovery_scripts == ["01-auth.ps1", "02-context.ps1"]
    assert executed_scripts == ["01-auth.ps1", "02-context.ps1"]
    assert runner.checkout_calls == 2


def test_simulated_tfs_worktree_lifecycle_roundtrip(tmp_path):
    handlers, runner, _ = build_runtime_with_simulated_tfs(tmp_path)
    session_path = tmp_path / "agent-auth"

    created = handlers["tfs_session_create"]("agent-auth", "$/SPF/Main", str(session_path))
    suspended = handlers["tfs_session_suspend"]("agent-auth")
    resumed = handlers["tfs_session_resume"]("agent-auth")
    promoted = handlers["tfs_session_promote"]("agent-auth", "ship it")
    discarded = handlers["tfs_session_discard"]("agent-auth")
    listed = handlers["tfs_session_list"]()

    assert created.status == "active"
    assert suspended.status == "suspended"
    assert resumed.status == "active"
    assert promoted.status == "promoted"
    assert promoted.last_shelveset == "ship it"
    assert discarded.status == "discarded"
    assert listed[0].status == "discarded"

    assert runner.commands == [
        ["workspace", "/new", "agent-auth", "/location:server", "/noprompt"],
        ["workfold", "/map", "$/SPF/Main", str(session_path), "/workspace:agent-auth", "/noprompt"],
        ["get", str(session_path), "/recursive", "/noprompt"],
        ["shelve", "agent-auth", "/noprompt"],
        ["get", str(session_path), "/recursive", "/noprompt"],
        ["checkin", "/comment:ship it", "/workspace:agent-auth", "/noprompt"],
        ["workspace", "/delete", "agent-auth", "/noprompt"],
    ]
