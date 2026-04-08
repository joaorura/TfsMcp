import uvicorn

from tfsmcp.http_app import build_http_app
from tfsmcp.mcp_server import build_mcp_server
from tfsmcp.runtime import build_runtime


def start_http_server(runtime):
    config = uvicorn.Config(build_http_app(runtime), host=runtime.config.http_host, port=runtime.config.http_port)
    return uvicorn.Server(config)


def run_console() -> None:
    runtime = build_runtime()
    mcp_server = build_mcp_server(runtime)
    http_server = start_http_server(runtime)
    _ = mcp_server
    http_server.run()
