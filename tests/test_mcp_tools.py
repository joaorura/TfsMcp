import json

from tfsmcp.mcp_server import build_mcp_server, build_tool_handlers
from tfsmcp.runtime import Runtime


class FakeDetector:
    def __init__(self):
        self.paths = []

    def detect(self, path: str):
        self.paths.append(path)
        return {
            "kind": "tfs_mapped",
            "local_path": path,
            "server_path": "$/SPF/Main",
            "workspace_name": "agent-auth",
        }


class FakeOnboarding:
    def __init__(self):
        self.paths = []

    def build(self, path: str):
        self.paths.append(path)
        return {"projectKind": "tfs_mapped", "localPath": path}


class FakeExecutor:
    def __init__(self):
        self.commands = []

    def run(self, args):
        self.commands.append(args)
        return {"command": args, "meta": {"recoveryTriggered": False, "retried": False}}


class FakeSessions:
    def __init__(self):
        self.calls = []
        self.records = []

    def create(self, name: str, source_path: str, session_path: str, perform_get: bool | None = None):
        self.calls.append(("create", name, source_path, session_path, perform_get))
        return {"name": name, "sourcePath": source_path, "sessionPath": session_path}

    def list_records(self):
        self.calls.append(("list_records",))
        return self.records

    def suspend(self, name: str):
        self.calls.append(("suspend", name))
        return {"name": name, "status": "suspended"}

    def discard(self, name: str):
        self.calls.append(("discard", name))
        return {"name": name, "status": "discarded"}

    def resume(self, name: str):
        self.calls.append(("resume", name))
        return {"name": name, "status": "active"}

    def promote(self, name: str, comment: str | None):
        self.calls.append(("promote", name, comment))
        return {"name": name, "status": "promoted", "last_shelveset": comment}


def test_handlers_delegate_to_runtime_dependencies():
    detector = FakeDetector()
    onboarding = FakeOnboarding()
    executor = FakeExecutor()
    sessions = FakeSessions()
    runtime = Runtime(config=None, detector=detector, onboarding=onboarding, executor=executor, sessions=sessions)
    handlers = build_tool_handlers(runtime)

    assert handlers["tfs_detect_project"]("D:/TFS/SPF")["kind"] == "tfs_mapped"
    assert detector.paths == ["D:/TFS/SPF"]

    assert handlers["tfs_onboard_project"]("D:/TFS/SPF")["projectKind"] == "tfs_mapped"
    assert onboarding.paths == ["D:/TFS/SPF"]

    assert handlers["tfs_checkout"]("D:/TFS/SPF/file.cs")["command"] == ["checkout", "D:/TFS/SPF/file.cs"]
    assert handlers["tfs_add"]("D:/TFS/SPF/new-file.cs")["command"] == ["add", "D:/TFS/SPF/new-file.cs"]
    assert handlers["tfs_add"]("D:/TFS/SPF/new-folder", recursive=True)["command"] == [
        "add",
        "D:/TFS/SPF/new-folder",
        "/recursive",
    ]
    assert handlers["tfs_undo"]("D:/TFS/SPF/file.cs")["command"] == ["undo", "D:/TFS/SPF/file.cs"]
    assert executor.commands == [
        ["checkout", "D:/TFS/SPF/file.cs"],
        ["add", "D:/TFS/SPF/new-file.cs"],
        ["add", "D:/TFS/SPF/new-folder", "/recursive"],
        ["undo", "D:/TFS/SPF/file.cs"],
    ]
    assert handlers["tfs_status"]("D:/TFS/SPF")["command"] == ["status", "D:/TFS/SPF", "/recursive"]
    assert handlers["tfs_get_latest"]("D:/TFS/SPF")["command"] == ["get", "D:/TFS/SPF", "/recursive", "/noprompt"]
    assert handlers["tfs_shelveset_list"]("joao", "rqf-*")["command"] == [
        "shelvesets",
        "rqf-*",
        "/owner:joao",
    ]
    assert handlers["tfs_unshelve"]("rqf-29", workspace="agent-auth")["command"] == [
        "unshelve",
        "rqf-29",
        "/workspace:agent-auth",
        "/noprompt",
    ]

    assert handlers["tfs_session_create"]("agent-auth", "D:/TFS/SPF", "D:/TFS/agents/auth") == {
        "name": "agent-auth",
        "sourcePath": "D:/TFS/SPF",
        "sessionPath": "D:/TFS/agents/auth",
    }
    assert handlers["tfs_session_create_from_path"](
        "agent-auth-2",
        "D:/TFS/SPF",
        "D:/TFS/agents/auth-2",
    ) == {
        "name": "agent-auth-2",
        "sourcePath": "$/SPF/Main",
        "sessionPath": "D:/TFS/agents/auth-2",
    }
    sessions.records = [{"name": "agent-auth", "sessionPath": "D:/TFS/agents/auth"}]
    assert json.loads(handlers["tfs_session_list"]()) == {
        "sessions": [{"name": "agent-auth", "sessionPath": "D:/TFS/agents/auth"}]
    }
    assert sessions.calls == [
        ("create", "agent-auth", "D:/TFS/SPF", "D:/TFS/agents/auth", False),
        ("create", "agent-auth-2", "$/SPF/Main", "D:/TFS/agents/auth-2", False),
        ("list_records",),
    ]

    assert handlers["tfs_checkin_preview"]("D:/TFS/SPF")["command"] == [
        "status",
        "D:/TFS/SPF",
        "/recursive",
    ]
    assert handlers["tfs_history"]("D:/TFS/SPF", stop_after=5)["command"] == [
        "history",
        "D:/TFS/SPF",
        "/stopafter:5",
    ]
    assert handlers["tfs_diff"]("D:/TFS/SPF", recursive=True)["command"] == [
        "diff",
        "D:/TFS/SPF",
        "/recursive",
    ]


def test_session_create_from_path_requires_mapped_path():
    class NotMappedDetector:
        def detect(self, path: str):
            return {"kind": "not_tfs", "server_path": None}

    runtime = Runtime(
        config=None,
        detector=NotMappedDetector(),
        onboarding=FakeOnboarding(),
        executor=FakeExecutor(),
        sessions=FakeSessions(),
    )
    handlers = build_tool_handlers(runtime)

    try:
        handlers["tfs_session_create_from_path"]("x", "D:/nope", "D:/sess")
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert "not TFS mapped" in str(exc)


def test_session_validate_uses_named_record_path_and_workspace():
    sessions = FakeSessions()
    sessions.records = [
        {
            "name": "agent-auth",
            "session_path": "D:/TFS/agents/auth",
            "workspace_name": "agent-auth",
        }
    ]
    executor = FakeExecutor()
    runtime = Runtime(config=None, detector=FakeDetector(), onboarding=FakeOnboarding(), executor=executor, sessions=sessions)
    handlers = build_tool_handlers(runtime)

    result = handlers["tfs_session_validate"](name="agent-auth")

    assert result["target_path"] == "D:/TFS/agents/auth"
    assert result["session"]["name"] == "agent-auth"
    assert executor.commands[-2] == ["workfold", "D:/TFS/agents/auth", "/workspace:agent-auth"]
    assert executor.commands[-1] == ["status", "D:/TFS/agents/auth", "/recursive", "/workspace:agent-auth"]


def test_session_validate_requires_name_or_path():
    runtime = Runtime(config=None, detector=FakeDetector(), onboarding=FakeOnboarding(), executor=FakeExecutor(), sessions=FakeSessions())
    handlers = build_tool_handlers(runtime)

    try:
        handlers["tfs_session_validate"]()
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "name' or 'path" in str(exc)


def test_checkin_preview_requires_path_or_workspace():
    runtime = Runtime(config=None, detector=FakeDetector(), onboarding=FakeOnboarding(), executor=FakeExecutor(), sessions=FakeSessions())
    handlers = build_tool_handlers(runtime)

    try:
        handlers["tfs_checkin_preview"]()
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "path' or 'workspace" in str(exc)


def test_session_handlers_delegate_create_suspend_discard(monkeypatch):
    runtime = Runtime(config=None, detector=None, onboarding=None, executor=None, sessions=FakeSessions())
    handlers = build_tool_handlers(runtime)

    assert handlers["tfs_session_create"]("agent-auth", "$/SPF/Main", "D:/TFS/agent-auth")["name"] == "agent-auth"
    assert handlers["tfs_session_suspend"]("agent-auth")["status"] == "suspended"
    assert handlers["tfs_session_discard"]("agent-auth")["status"] == "discarded"


def test_session_create_can_force_get_during_create():
    sessions = FakeSessions()
    runtime = Runtime(config=None, detector=FakeDetector(), onboarding=FakeOnboarding(), executor=FakeExecutor(), sessions=sessions)
    handlers = build_tool_handlers(runtime)

    handlers["tfs_session_create"]("agent-auth", "$/SPF/Main", "D:/TFS/agents/auth", perform_get=True)

    assert sessions.calls == [("create", "agent-auth", "$/SPF/Main", "D:/TFS/agents/auth", True)]


def test_session_create_async_and_status_completed():
    sessions = FakeSessions()
    runtime = Runtime(config=None, detector=FakeDetector(), onboarding=FakeOnboarding(), executor=FakeExecutor(), sessions=sessions)
    handlers = build_tool_handlers(runtime)

    queued = handlers["tfs_session_create_async"]("agent-auth", "$/SPF/Main", "D:/TFS/agents/auth")
    result = handlers["tfs_session_create_job_status"](queued["job_id"])
    if result["status"] == "running":
        result = handlers["tfs_session_create_job_status"](queued["job_id"])

    assert queued["status"] == "queued"
    assert result["status"] == "completed"
    assert result["result"]["name"] == "agent-auth"


def test_session_materialize_uses_record_workspace_and_path():
    sessions = FakeSessions()
    sessions.records = [
        {
            "name": "agent-auth",
            "session_path": "D:/TFS/agents/auth",
            "workspace_name": "agent-auth",
        }
    ]
    executor = FakeExecutor()
    runtime = Runtime(config=None, detector=FakeDetector(), onboarding=FakeOnboarding(), executor=executor, sessions=sessions)
    handlers = build_tool_handlers(runtime)

    payload = handlers["tfs_session_materialize"](name="agent-auth")

    assert payload["session_path"] == "D:/TFS/agents/auth"
    assert executor.commands[-1] == ["get", "D:/TFS/agents/auth", "/recursive", "/workspace:agent-auth", "/noprompt"]


def test_session_handlers_delegate_resume_and_promote():
    sessions = FakeSessions()
    runtime = Runtime(config=None, detector=None, onboarding=None, executor=None, sessions=sessions)
    handlers = build_tool_handlers(runtime)

    assert handlers["tfs_session_resume"]("agent-auth")["status"] == "active"
    assert handlers["tfs_session_promote"]("agent-auth", "ship it")["status"] == "promoted"
    assert sessions.calls == [("resume", "agent-auth"), ("promote", "agent-auth", "ship it")]


def test_build_mcp_server_registers_session_lifecycle_tools(monkeypatch):
    names = []

    class FakeMCP:
        def __init__(self, name: str):
            self.name = name

        def tool(self, name: str):
            def register(handler):
                names.append(name)
                return handler

            return register

    monkeypatch.setattr("tfsmcp.mcp_server.FastMCP", FakeMCP)
    runtime = Runtime(config=None, detector=None, onboarding=None, executor=None, sessions=FakeSessions())

    build_mcp_server(runtime)

    assert "tfs_session_create" in names
    assert "tfs_session_suspend" in names
    assert "tfs_session_discard" in names
    assert "tfs_session_resume" in names
    assert "tfs_session_promote" in names


def test_build_mcp_server_uses_tfs_tools_name_and_registers_handlers(monkeypatch):
    registrations = []

    class FakeMCP:
        def __init__(self, name: str):
            self.name = name

        def tool(self, name: str):
            def register(handler):
                registrations.append((name, handler))
                return handler

            return register

    monkeypatch.setattr("tfsmcp.mcp_server.FastMCP", FakeMCP)

    runtime = Runtime(config=None, detector=FakeDetector(), onboarding=FakeOnboarding(), executor=FakeExecutor(), sessions=FakeSessions())
    server = build_mcp_server(runtime)

    assert server.name == "TFS_Tools"
    assert [name for name, _ in registrations] == [
        "tfs_detect_project",
        "tfs_onboard_project",
        "tfs_checkout",
        "tfs_add",
        "tfs_status",
        "tfs_get_latest",
        "tfs_shelveset_list",
        "tfs_unshelve",
        "tfs_undo",
        "tfs_session_create",
        "tfs_session_create_from_path",
        "tfs_session_create_async",
        "tfs_session_create_from_path_async",
        "tfs_session_create_job_status",
        "tfs_session_list",
        "tfs_session_materialize",
        "tfs_session_validate",
        "tfs_session_suspend",
        "tfs_session_discard",
        "tfs_session_resume",
        "tfs_session_promote",
        "tfs_checkin_preview",
        "tfs_history",
        "tfs_diff",
    ]
    assert callable(dict(registrations)["tfs_detect_project"])
    assert callable(dict(registrations)["tfs_undo"])
    assert callable(dict(registrations)["tfs_onboard_project"])
    assert callable(dict(registrations)["tfs_add"])
    assert callable(dict(registrations)["tfs_status"])
    assert callable(dict(registrations)["tfs_get_latest"])
    assert callable(dict(registrations)["tfs_shelveset_list"])
    assert callable(dict(registrations)["tfs_unshelve"])
    assert callable(dict(registrations)["tfs_session_create"])
    assert callable(dict(registrations)["tfs_session_create_from_path"])
    assert callable(dict(registrations)["tfs_session_create_async"])
    assert callable(dict(registrations)["tfs_session_create_from_path_async"])
    assert callable(dict(registrations)["tfs_session_create_job_status"])
    assert callable(dict(registrations)["tfs_session_list"])
    assert callable(dict(registrations)["tfs_session_materialize"])
    assert callable(dict(registrations)["tfs_session_validate"])
    assert callable(dict(registrations)["tfs_session_suspend"])
    assert callable(dict(registrations)["tfs_session_discard"])
    assert callable(dict(registrations)["tfs_session_resume"])
    assert callable(dict(registrations)["tfs_session_promote"])
    assert callable(dict(registrations)["tfs_checkin_preview"])
    assert callable(dict(registrations)["tfs_history"])
    assert callable(dict(registrations)["tfs_diff"])
    assert callable(dict(registrations)["tfs_checkout"])
