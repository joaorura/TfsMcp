import builtins
import importlib
import sys
import types

import pytest

MODULE_NAME = "tfsmcp.service.windows_service"


class FakeServer:
    def __init__(self):
        self.should_exit = False
        self.ran = False

    def run(self):
        self.ran = True


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

    modules = {
        "servicemanager": servicemanager,
        "win32event": win32event,
        "win32service": win32service,
        "win32serviceutil": win32serviceutil,
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    return modules


def load_windows_service_module(monkeypatch):
    install_pywin32_stubs(monkeypatch)
    sys.modules.pop(MODULE_NAME, None)
    return importlib.import_module(MODULE_NAME)


def test_windows_service_import_requires_pywin32_modules(monkeypatch):
    sys.modules.pop(MODULE_NAME, None)
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "win32serviceutil":
            raise ModuleNotFoundError(name)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(MODULE_NAME)


def test_windows_service_runs_http_server(monkeypatch):
    windows_service = load_windows_service_module(monkeypatch)
    service = object.__new__(windows_service.TfsMcpWindowsService)
    service.server = None
    service.ReportServiceStatus = lambda status: None
    service.stop_event = object()
    fake_server = FakeServer()

    monkeypatch.setattr(windows_service.servicemanager, "LogInfoMsg", lambda msg: None)
    monkeypatch.setattr(windows_service, "build_runtime", lambda: object())
    monkeypatch.setattr(windows_service, "start_http_server", lambda runtime: fake_server)

    service.SvcDoRun()

    assert service.server is fake_server
    assert fake_server.ran is True


def test_windows_service_stop_sets_should_exit(monkeypatch):
    windows_service = load_windows_service_module(monkeypatch)
    service = object.__new__(windows_service.TfsMcpWindowsService)
    service.server = FakeServer()
    reported = []
    service.ReportServiceStatus = lambda status: reported.append(status)
    service.stop_event = object()

    monkeypatch.setattr(windows_service.win32event, "SetEvent", lambda event: None)
    monkeypatch.setattr(windows_service.win32service, "SERVICE_STOP_PENDING", 3)

    service.SvcStop()

    assert reported == [3]
    assert service.server.should_exit is True
