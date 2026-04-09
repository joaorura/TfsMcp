from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder

from tfsmcp.mcp_server import build_mcp_server
from tfsmcp.runtime import Runtime


def build_http_app(runtime: Runtime) -> FastAPI:
    app = FastAPI()
    mcp_server = build_mcp_server(runtime)
    mcp_app = mcp_server.streamable_http_app()

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/projects/detect")
    def detect(path: str):
        return {"ok": True, "data": jsonable_encoder(runtime.detector.detect(path)), "error": None, "meta": {}}

    @app.get("/projects/onboard")
    def onboard(path: str):
        return {"ok": True, "data": jsonable_encoder(runtime.onboarding.build(path)), "error": None, "meta": {}}

    @app.post("/checkout")
    def checkout(payload: dict[str, str]):
        result = runtime.executor.run(["checkout", payload["path"]])
        encoded = jsonable_encoder(result)
        return {"ok": True, "data": encoded, "error": None, "meta": encoded.get("meta", {})}

    @app.post("/sessions")
    def create_session(payload: dict[str, str]):
        record = runtime.sessions.create(payload["name"], payload["source_path"], payload["session_path"])
        return {"ok": True, "data": jsonable_encoder(record), "error": None, "meta": {}}

    @app.get("/sessions")
    def sessions():
        return {"ok": True, "data": jsonable_encoder(runtime.sessions.list_records()), "error": None, "meta": {}}

    @app.post("/sessions/{name}/suspend")
    def suspend_session(name: str):
        record = runtime.sessions.suspend(name)
        return {"ok": True, "data": jsonable_encoder(record), "error": None, "meta": {}}

    @app.post("/sessions/{name}/resume")
    def resume_session(name: str):
        record = runtime.sessions.resume(name)
        return {"ok": True, "data": jsonable_encoder(record), "error": None, "meta": {}}

    @app.post("/sessions/{name}/promote")
    def promote_session(name: str, payload: dict[str, str | None] | None = None):
        payload = payload or {}
        record = runtime.sessions.promote(name, payload.get("comment"))
        return {"ok": True, "data": jsonable_encoder(record), "error": None, "meta": {}}

    @app.delete("/sessions/{name}")
    def discard_session(name: str):
        record = runtime.sessions.discard(name)
        return {"ok": True, "data": jsonable_encoder(record), "error": None, "meta": {}}

    # Mount after REST routes so /health and other API paths remain first-class, while exposing MCP at /mcp.
    app.mount("/", mcp_app)

    return app
