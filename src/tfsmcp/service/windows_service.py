import servicemanager
import win32event
import win32service
import win32serviceutil

from tfsmcp.console import build_runtime, start_http_server_for_service


class TfsMcpWindowsService(win32serviceutil.ServiceFramework):
    _svc_name_ = "TfsMcpService"
    _svc_display_name_ = "TFS MCP Service"

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.server = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.server is not None:
            self.server.should_exit = True
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("Starting TfsMcpService")
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING, waitHint=120000)
        runtime = build_runtime()
        self.server = start_http_server_for_service(runtime)
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        self.server.run()
