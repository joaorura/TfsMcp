import runpy


def test_package_main_calls_run_console(monkeypatch):
    called = []
    monkeypatch.setattr("tfsmcp.console.run_console", lambda: called.append("ran"))

    runpy.run_module("tfsmcp", run_name="__main__")

    assert called == ["ran"]


def test_package_main_uses_console_startup_path(monkeypatch):
    called = []
    monkeypatch.setattr("tfsmcp.console.run_console", lambda: called.append("console"))

    runpy.run_module("tfsmcp", run_name="__main__")

    assert called == ["console"]
