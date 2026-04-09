from contextlib import asynccontextmanager

from fastapi import FastAPI

from tfsmcp.mcp_server import build_mcp_server
from tfsmcp.runtime import Runtime


def build_http_app(runtime: Runtime) -> FastAPI:
    mcp_server = build_mcp_server(runtime)
    mcp_app = mcp_server.streamable_http_app()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        async with mcp_app.router.lifespan_context(mcp_app):
            yield

    app = FastAPI(lifespan=lifespan)

    # Serve MCP streamable HTTP transport only.
    app.mount("/", mcp_app)

    return app
