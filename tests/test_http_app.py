from fastapi.testclient import TestClient

from tfsmcp.http_app import build_http_app
from tfsmcp.runtime import Runtime


class FakeDetector:
    def detect(self, path: str):
        return {
            "kind": "tfs_mapped",
            "confidence": "high",
            "workspaceName": "SPF_Joao",
            "serverPath": "$/SPF/Main",
            "localPath": path,
            "isAgentReady": True,
        }


class FakeOnboarding:
    def build(self, path: str):
        return {"projectKind": "tfs_mapped", "path": path, "supports": {"unauthorizedRecovery": True}}


class FakeExecutor:
    def run(self, args):
        return {"ok": True, "command": args, "meta": {"recoveryTriggered": False, "retried": False}}


class FakeSessions:
    def __init__(self):
        self.calls = []

    def create(self, name: str, source_path: str, session_path: str):
        self.calls.append(("create", name, source_path, session_path))
        return {
            "name": name,
            "project_path": source_path,
            "session_path": session_path,
            "server_path": "$/SPF/Main",
            "workspace_name": name,
            "mode": "hybrid",
            "status": "active",
            "last_shelveset": None,
        }

    def list_records(self):
        return [{"name": "agent-auth", "status": "active"}]

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


def build_client() -> TestClient:
    runtime = Runtime(config=None, detector=FakeDetector(), onboarding=FakeOnboarding(), executor=FakeExecutor(), sessions=FakeSessions())
    return TestClient(build_http_app(runtime))


def test_health_endpoint_reports_ok():
    client = build_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_detect_endpoint_returns_detector_payload():
    client = build_client()

    response = client.get("/projects/detect", params={"path": "D:/TFS/SPF"})

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "data": {
            "kind": "tfs_mapped",
            "confidence": "high",
            "workspaceName": "SPF_Joao",
            "serverPath": "$/SPF/Main",
            "localPath": "D:/TFS/SPF",
            "isAgentReady": True,
        },
        "error": None,
        "meta": {},
    }


def test_onboard_endpoint_returns_onboarding_payload():
    client = build_client()

    response = client.get("/projects/onboard", params={"path": "D:/TFS/SPF"})

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "data": {
            "projectKind": "tfs_mapped",
            "path": "D:/TFS/SPF",
            "supports": {"unauthorizedRecovery": True},
        },
        "error": None,
        "meta": {},
    }


def test_checkout_endpoint_returns_executor_payload():
    client = build_client()

    response = client.post("/checkout", json={"path": "D:/TFS/SPF/file.cs"})

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "data": {
            "ok": True,
            "command": ["checkout", "D:/TFS/SPF/file.cs"],
            "meta": {"recoveryTriggered": False, "retried": False},
        },
        "error": None,
        "meta": {"recoveryTriggered": False, "retried": False},
    }


def test_create_session_endpoint_returns_created_record():
    client = build_client()

    response = client.post(
        "/sessions",
        json={
            "name": "agent-auth",
            "source_path": "D:/TFS/SPF",
            "session_path": "D:/TFS/agents/auth",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "data": {
            "name": "agent-auth",
            "project_path": "D:/TFS/SPF",
            "session_path": "D:/TFS/agents/auth",
            "server_path": "$/SPF/Main",
            "workspace_name": "agent-auth",
            "mode": "hybrid",
            "status": "active",
            "last_shelveset": None,
        },
        "error": None,
        "meta": {},
    }



def test_sessions_endpoint_returns_records():
    client = build_client()

    response = client.get("/sessions")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "data": [{"name": "agent-auth", "status": "active"}],
        "error": None,
        "meta": {},
    }


def test_http_session_lifecycle_endpoints():
    runtime = Runtime(config=None, detector=None, onboarding=None, executor=None, sessions=FakeSessions())
    client = TestClient(build_http_app(runtime))

    created = client.post(
        "/sessions",
        json={
            "name": "agent-auth",
            "source_path": "$/SPF/Main",
            "session_path": "D:/TFS/agent-auth",
        },
    )
    suspended = client.post("/sessions/agent-auth/suspend")
    discarded = client.delete("/sessions/agent-auth")

    assert created.status_code == 200
    assert created.json()["data"]["status"] == "active"
    assert suspended.json()["data"]["status"] == "suspended"
    assert discarded.json()["data"]["status"] == "discarded"


def test_http_resume_and_promote_endpoints():
    runtime = Runtime(config=None, detector=None, onboarding=None, executor=None, sessions=FakeSessions())
    client = TestClient(build_http_app(runtime))

    resumed = client.post("/sessions/agent-auth/resume")
    promoted = client.post("/sessions/agent-auth/promote", json={"comment": "ship it"})

    assert resumed.json()["data"]["status"] == "active"
    assert promoted.json()["data"]["status"] == "promoted"
    assert promoted.json()["data"]["last_shelveset"] == "ship it"
