from fastapi.testclient import TestClient

from tfsmcp.http_app import build_http_app
from tfsmcp.runtime import Runtime


class FakeDetector:
    def detect(self, path: str):
        return {"kind": "tfs_mapped", "localPath": path}


class FakeOnboarding:
    def build(self, path: str):
        return {"projectKind": "tfs_mapped", "path": path}


class FakeExecutor:
    def run(self, args):
        return {"command": args}


class FakeSessions:
    def create(self, name: str, source_path: str, session_path: str):
        return {"name": name, "source_path": source_path, "session_path": session_path}

    def list_records(self):
        return []

    def suspend(self, name: str):
        return {"name": name, "status": "suspended"}

    def discard(self, name: str):
        return {"name": name, "status": "discarded"}

    def resume(self, name: str):
        return {"name": name, "status": "active"}

    def promote(self, name: str, comment: str | None):
        return {"name": name, "status": "promoted", "last_shelveset": comment}


def build_client() -> TestClient:
    runtime = Runtime(config=None, detector=FakeDetector(), onboarding=FakeOnboarding(), executor=FakeExecutor(), sessions=FakeSessions())
    return TestClient(build_http_app(runtime))


def test_http_app_mounts_mcp_streamable_transport():
    app = build_http_app(
        Runtime(config=None, detector=FakeDetector(), onboarding=FakeOnboarding(), executor=FakeExecutor(), sessions=FakeSessions())
    )

    mounts = [route for route in app.routes if type(route).__name__ == "Mount"]

    assert mounts
    assert getattr(mounts[0], "path", None) == ""
    child_paths = [getattr(route, "path", None) for route in mounts[0].app.routes]
    assert "/mcp" in child_paths


def test_http_app_no_longer_exposes_legacy_rest_routes():
    client = build_client()

    assert client.get("/health").status_code == 404
    assert client.get("/projects/detect", params={"path": "D:/TFS/SPF"}).status_code == 404
    assert client.post("/checkout", json={"path": "D:/TFS/SPF/file.cs"}).status_code == 404
    assert client.get("/sessions").status_code == 404
