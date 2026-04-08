from tfsmcp.console import run_console, start_http_server
from tfsmcp.runtime import Runtime


class FakeConfig:
    http_host = "127.0.0.1"
    http_port = 39393


class FakeServer:
    def __init__(self):
        self.ran = False

    def run(self):
        self.ran = True


def test_start_http_server_uses_runtime_config(monkeypatch):
    captured = {}

    class FakeConfigObject:
        def __init__(self, app, host: str, port: int):
            captured["host"] = host
            captured["port"] = port
            self.app = app

    monkeypatch.setattr("tfsmcp.console.uvicorn.Config", FakeConfigObject)
    monkeypatch.setattr("tfsmcp.console.uvicorn.Server", lambda config: {"config": config})

    runtime = Runtime(config=FakeConfig(), detector=None, onboarding=None, executor=None, sessions=None)
    server = start_http_server(runtime)

    assert captured == {"host": "127.0.0.1", "port": 39393}
    assert "config" in server


def test_run_console_builds_runtime_constructs_mcp_server_and_runs_http_server(monkeypatch):
    fake_server = FakeServer()
    captured = {}
    runtime = Runtime(config=FakeConfig(), detector=None, onboarding=None, executor=None, sessions=None)

    def fake_build_mcp_server(built_runtime):
        captured["mcp_runtime"] = built_runtime
        return object()

    def fake_start_http_server(built_runtime):
        captured["http_runtime"] = built_runtime
        return fake_server

    monkeypatch.setattr("tfsmcp.console.build_runtime", lambda: runtime)
    monkeypatch.setattr("tfsmcp.console.build_mcp_server", fake_build_mcp_server)
    monkeypatch.setattr("tfsmcp.console.start_http_server", fake_start_http_server)

    run_console()

    assert captured == {"mcp_runtime": runtime, "http_runtime": runtime}
    assert fake_server.ran is True
