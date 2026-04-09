import uvicorn

from tfsmcp.http_app import build_http_app
from tfsmcp.runtime import build_runtime


def start_http_server(runtime):
    config = uvicorn.Config(build_http_app(runtime), host=runtime.config.http_host, port=runtime.config.http_port)
    return uvicorn.Server(config)


def start_http_server_for_service(runtime):
    # Uvicorn default logging config can fail under Windows service sessions without a regular console stream.
    config = uvicorn.Config(
        build_http_app(runtime),
        host=runtime.config.http_host,
        port=runtime.config.http_port,
        log_config=None,
    )
    return uvicorn.Server(config)


def run_console() -> None:
    runtime = build_runtime()
    http_server = start_http_server(runtime)
    http_server.run()
