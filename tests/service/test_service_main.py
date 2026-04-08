import importlib
import sys
import types


def install_pywin32_stubs(monkeypatch):
    servicemanager = types.ModuleType("servicemanager")
    servicemanager.LogInfoMsg = lambda message: None

    win32event = types.ModuleType("win32event")
    win32event.CreateEvent = lambda *args, **kwargs: object()
    win32event.SetEvent = lambda event: None

    win32service = types.ModuleType("win32service")
    win32service.SERVICE_STOP_PENDING = 3

    class ServiceFramework:
        def __init__(self, args):
            self.args = args

        def ReportServiceStatus(self, status):
            self.status = status

        @classmethod
        def HandleCommandLine(cls):
            return None

    win32serviceutil = types.ModuleType("win32serviceutil")
    win32serviceutil.ServiceFramework = ServiceFramework
    win32serviceutil.HandleCommandLine = lambda service_cls: None

    for name, module in {
        "servicemanager": servicemanager,
        "win32event": win32event,
        "win32service": win32service,
        "win32serviceutil": win32serviceutil,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)


def load_service_main_module(monkeypatch):
    install_pywin32_stubs(monkeypatch)
    sys.modules.pop("tfsmcp.service.windows_service", None)
    sys.modules.pop("tfsmcp.service.__main__", None)
    return importlib.import_module("tfsmcp.service.__main__")


class FakeInstaller:
    def __init__(self):
        self.calls = []

    def install(self, executable: str, arguments: str) -> int:
        self.calls.append(("install", executable, arguments))
        return 0

    def uninstall(self) -> int:
        self.calls.append(("uninstall",))
        return 0

    def start(self) -> int:
        self.calls.append(("start",))
        return 0

    def stop(self) -> int:
        self.calls.append(("stop",))
        return 0

    def restart(self) -> int:
        self.calls.append(("restart",))
        return 0

    def status(self) -> int:
        self.calls.append(("status",))
        return 0


def test_service_main_dispatches_install(monkeypatch):
    service_main = load_service_main_module(monkeypatch)
    fake = FakeInstaller()
    monkeypatch.setattr(service_main, "ServiceInstaller", lambda *args: fake)

    code = service_main.main(["install"])

    assert code == 0
    assert fake.calls == [("install", sys.executable, "-m tfsmcp.service run")]


def test_service_main_dispatches_run_via_win32serviceutil(monkeypatch):
    service_main = load_service_main_module(monkeypatch)
    calls = []

    def fake_handle_command_line(service_cls):
        calls.append(service_cls)

    monkeypatch.setattr(service_main.win32serviceutil, "HandleCommandLine", fake_handle_command_line)

    code = service_main.main(["run"])

    assert code == 0
    assert calls == [service_main.TfsMcpWindowsService]
