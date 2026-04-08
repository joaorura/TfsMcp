from tfsmcp.mcp_server import build_mcp_server, build_tool_handlers
from tfsmcp.runtime import Runtime


class FakeDetector:
    def __init__(self):
        self.paths = []

    def detect(self, path: str):
        self.paths.append(path)
        return {"kind": "tfs_mapped", "localPath": path}


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

    def create(self, name: str, source_path: str, session_path: str):
        self.calls.append(("create", name, source_path, session_path))
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
    assert handlers["tfs_undo"]("D:/TFS/SPF/file.cs")["command"] == ["undo", "D:/TFS/SPF/file.cs"]
    assert executor.commands == [["checkout", "D:/TFS/SPF/file.cs"], ["undo", "D:/TFS/SPF/file.cs"]]

    assert handlers["tfs_session_create"]("agent-auth", "D:/TFS/SPF", "D:/TFS/agents/auth") == {
        "name": "agent-auth",
        "sourcePath": "D:/TFS/SPF",
        "sessionPath": "D:/TFS/agents/auth",
    }
    sessions.records = [{"name": "agent-auth", "sessionPath": "D:/TFS/agents/auth"}]
    assert handlers["tfs_session_list"]() == [{"name": "agent-auth", "sessionPath": "D:/TFS/agents/auth"}]
    assert sessions.calls == [
        ("create", "agent-auth", "D:/TFS/SPF", "D:/TFS/agents/auth"),
        ("list_records",),
    ]


def test_session_handlers_delegate_create_suspend_discard(monkeypatch):
    runtime = Runtime(config=None, detector=None, onboarding=None, executor=None, sessions=FakeSessions())
    handlers = build_tool_handlers(runtime)

    assert handlers["tfs_session_create"]("agent-auth", "$/SPF/Main", "D:/TFS/agent-auth")["name"] == "agent-auth"
    assert handlers["tfs_session_suspend"]("agent-auth")["status"] == "suspended"
    assert handlers["tfs_session_discard"]("agent-auth")["status"] == "discarded"


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
        "tfs_undo",
        "tfs_session_create",
        "tfs_session_list",
        "tfs_session_suspend",
        "tfs_session_discard",
        "tfs_session_resume",
        "tfs_session_promote",
    ]
    assert callable(dict(registrations)["tfs_detect_project"])
    assert callable(dict(registrations)["tfs_undo"])
    assert callable(dict(registrations)["tfs_onboard_project"])
    assert callable(dict(registrations)["tfs_session_create"])
    assert callable(dict(registrations)["tfs_session_list"])
    assert callable(dict(registrations)["tfs_session_suspend"])
    assert callable(dict(registrations)["tfs_session_discard"])
    assert callable(dict(registrations)["tfs_session_resume"])
    assert callable(dict(registrations)["tfs_session_promote"])
    assert callable(dict(registrations)["tfs_checkout"])
