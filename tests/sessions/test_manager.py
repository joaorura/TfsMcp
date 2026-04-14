import pytest

from tfsmcp.contracts import SessionRecord
from tfsmcp.sessions.manager import SessionManager
from tfsmcp.sessions.store import SessionStore


class FakeWorkspaceActions:
    def __init__(self) -> None:
        self.created = []
        self.shelvesets = []
        self.removed = []
        self.resumed = []
        self.promoted = []

    def create_workspace(self, name: str, source_path: str, session_path: str) -> str:
        self.created.append((name, source_path, session_path))
        return source_path

    def create_shelveset(self, workspace_name: str) -> str:
        self.shelvesets.append(workspace_name)
        return workspace_name

    def remove_workspace(self, workspace_name: str) -> None:
        self.removed.append(workspace_name)

    def resume_workspace(self, workspace_name: str, session_path: str) -> None:
        self.resumed.append((workspace_name, session_path))

    def promote_workspace(self, workspace_name: str, comment: str | None) -> str:
        self.promoted.append((workspace_name, comment))
        return comment or workspace_name


def test_session_create_persists_workspace_session(tmp_path):
    store = SessionStore(tmp_path / "sessions.json")
    actions = FakeWorkspaceActions()
    manager = SessionManager(store, actions)

    record = manager.create("agent-auth", "$/SPF/Main", tmp_path / "agent-auth")

    assert record.name == "agent-auth"
    assert record.server_path == "$/SPF/Main"
    assert store.load_all()[0].workspace_name == "agent-auth"


def test_session_create_rejects_duplicate_name(tmp_path):
    store = SessionStore(tmp_path / "sessions.json")
    actions = FakeWorkspaceActions()
    manager = SessionManager(store, actions)
    manager.create("agent-auth", "$/SPF/Main", tmp_path / "agent-auth")

    with pytest.raises(ValueError, match="agent-auth"):
        manager.create("agent-auth", "$/SPF/Main", tmp_path / "agent-auth-2")

    assert len(store.load_all()) == 1
    assert actions.created == [("agent-auth", "$/SPF/Main", str(tmp_path / "agent-auth"))]


def test_session_suspend_and_discard_use_persisted_record_identity(tmp_path):
    store = SessionStore(tmp_path / "sessions.json")
    actions = FakeWorkspaceActions()
    manager = SessionManager(store, actions)
    store.save_all(
        [
            SessionRecord(
                name="agent-auth",
                project_path="D:/TFS/SPF",
                session_path=str(tmp_path / "agent-auth"),
                server_path="$/SPF/Main",
                workspace_name="persisted-workspace",
                mode="hybrid",
                status="active",
            )
        ]
    )

    suspended = manager.suspend("agent-auth")
    discarded = manager.discard("agent-auth")

    assert suspended.status == "suspended"
    assert suspended.last_shelveset == "persisted-workspace"
    assert actions.shelvesets == ["persisted-workspace"]
    assert discarded.status == "discarded"
    assert actions.removed == ["persisted-workspace"]


def test_session_lifecycle_list_suspend_discard_roundtrip(tmp_path):
    store = SessionStore(tmp_path / "sessions.json")
    actions = FakeWorkspaceActions()
    manager = SessionManager(store, actions)

    created = manager.create("agent-auth", "$/SPF/Main", tmp_path / "agent-auth")
    suspended = manager.suspend("agent-auth")
    discarded = manager.discard("agent-auth")

    assert manager.list_records()[0].status == "discarded"
    assert created.status == "active"
    assert suspended.last_shelveset == "agent-auth"
    assert discarded.status == "discarded"


def test_session_resume_and_promote_roundtrip(tmp_path):
    store = SessionStore(tmp_path / "sessions.json")
    actions = FakeWorkspaceActions()
    manager = SessionManager(store, actions)

    manager.create("agent-auth", "$/SPF/Main", tmp_path / "agent-auth")
    manager.suspend("agent-auth")
    resumed = manager.resume("agent-auth")
    promoted = manager.promote("agent-auth", "ship it")

    assert resumed.status == "active"
    assert promoted.status == "promoted"
    assert promoted.last_shelveset == "ship it"


def test_session_resume_uses_persisted_record_identity(tmp_path):
    store = SessionStore(tmp_path / "sessions.json")
    actions = FakeWorkspaceActions()
    manager = SessionManager(store, actions)
    store.save_all(
        [
            SessionRecord(
                name="agent-auth",
                project_path="D:/TFS/SPF",
                session_path=str(tmp_path / "persisted-session"),
                server_path="$/SPF/Main",
                workspace_name="persisted-workspace",
                mode="hybrid",
                status="suspended",
            )
        ]
    )

    resumed = manager.resume("agent-auth")

    assert resumed.status == "active"
    assert actions.resumed == [("persisted-workspace", str(tmp_path / "persisted-session"))]



def test_session_resume_rejects_invalid_state(tmp_path):
    store = SessionStore(tmp_path / "sessions.json")
    actions = FakeWorkspaceActions()
    manager = SessionManager(store, actions)
    store.save_all(
        [
            SessionRecord(
                name="agent-auth",
                project_path="D:/TFS/SPF",
                session_path=str(tmp_path / "agent-auth"),
                server_path="$/SPF/Main",
                workspace_name="persisted-workspace",
                mode="hybrid",
                status="active",
            )
        ]
    )

    with pytest.raises(ValueError, match="active"):
        manager.resume("agent-auth")

    assert actions.resumed == []



def test_session_promote_uses_persisted_record_identity(tmp_path):
    store = SessionStore(tmp_path / "sessions.json")
    actions = FakeWorkspaceActions()
    manager = SessionManager(store, actions)
    store.save_all(
        [
            SessionRecord(
                name="agent-auth",
                project_path="D:/TFS/SPF",
                session_path=str(tmp_path / "agent-auth"),
                server_path="$/SPF/Main",
                workspace_name="persisted-workspace",
                mode="hybrid",
                status="active",
            )
        ]
    )

    promoted = manager.promote("agent-auth", "ship it")

    assert promoted.status == "promoted"
    assert promoted.last_shelveset == "ship it"
    assert actions.promoted == [("persisted-workspace", "ship it")]



def test_session_promote_rejects_invalid_state(tmp_path):
    store = SessionStore(tmp_path / "sessions.json")
    actions = FakeWorkspaceActions()
    manager = SessionManager(store, actions)
    store.save_all(
        [
            SessionRecord(
                name="agent-auth",
                project_path="D:/TFS/SPF",
                session_path=str(tmp_path / "agent-auth"),
                server_path="$/SPF/Main",
                workspace_name="persisted-workspace",
                mode="hybrid",
                status="discarded",
            )
        ]
    )

    with pytest.raises(ValueError, match="discarded"):
        manager.promote("agent-auth", "ship it")

    assert actions.promoted == []


def test_session_missing_record_raises_key_error(tmp_path):
    store = SessionStore(tmp_path / "sessions.json")
    actions = FakeWorkspaceActions()
    manager = SessionManager(store, actions)

    with pytest.raises(KeyError, match="missing-session"):
        manager.suspend("missing-session")

    with pytest.raises(KeyError, match="missing-session"):
        manager.discard("missing-session")

    with pytest.raises(KeyError, match="missing-session"):
        manager.resume("missing-session")

    with pytest.raises(KeyError, match="missing-session"):
        manager.promote("missing-session", "ship it")


def test_discard_missing_session_raises_key_error(tmp_path):
    store = SessionStore(tmp_path / "sessions.json")
    manager = SessionManager(store, FakeWorkspaceActions())

    with pytest.raises(KeyError, match="missing"):
        manager.discard("missing")
