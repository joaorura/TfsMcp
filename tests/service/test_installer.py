import types

from tfsmcp.service.installer import ServiceInstaller, default_runner


class FakeRunner:
    def __init__(self) -> None:
        self.commands = []

    def __call__(self, command):
        self.commands.append(command)
        return 0


def test_installer_builds_sc_commands_for_supported_actions():
    runner = FakeRunner()
    installer = ServiceInstaller(runner, service_name="TfsMcpService", display_name="TFS MCP Service")

    installer.install("python", "-m tfsmcp.service run")
    installer.start()
    installer.uninstall()
    installer.stop()
    installer.restart()
    installer.status()

    assert runner.commands == [
        [
            "sc",
            "create",
            "TfsMcpService",
            "binPath=",
            "python -m tfsmcp.service run",
            "DisplayName=",
            "TFS MCP Service",
            "start=",
            "auto",
        ],
        ["sc", "start", "TfsMcpService"],
        ["sc", "delete", "TfsMcpService"],
        ["sc", "stop", "TfsMcpService"],
        ["sc", "stop", "TfsMcpService"],
        ["sc", "start", "TfsMcpService"],
        ["sc", "query", "TfsMcpService"],
    ]


def test_default_runner_returns_subprocess_return_code(monkeypatch):
    recorded = {}

    def fake_run(command, check):
        recorded["command"] = command
        recorded["check"] = check
        return types.SimpleNamespace(returncode=17)

    monkeypatch.setattr("tfsmcp.service.installer.subprocess.run", fake_run)

    code = default_runner(["sc", "query", "TfsMcpService"])

    assert code == 17
    assert recorded == {
        "command": ["sc", "query", "TfsMcpService"],
        "check": False,
    }
