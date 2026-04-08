import sys

import win32serviceutil

from tfsmcp.service.installer import ServiceInstaller, default_runner
from tfsmcp.service.windows_service import TfsMcpWindowsService


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    installer = ServiceInstaller(default_runner, "TfsMcpService", "TFS MCP Service")
    if argv == ["install"]:
        return installer.install(sys.executable, "-m tfsmcp.service run")
    if argv == ["uninstall"]:
        return installer.uninstall()
    if argv == ["start"]:
        return installer.start()
    if argv == ["stop"]:
        return installer.stop()
    if argv == ["restart"]:
        return installer.restart()
    if argv == ["status"]:
        return installer.status()
    if argv == ["run"]:
        win32serviceutil.HandleCommandLine(TfsMcpWindowsService)
        return 0
    raise SystemExit("usage: python -m tfsmcp.service [install|uninstall|start|stop|restart|status|run]")


if __name__ == "__main__":
    raise SystemExit(main())
