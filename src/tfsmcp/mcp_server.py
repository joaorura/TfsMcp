from mcp.server.fastmcp import FastMCP

from tfsmcp.runtime import Runtime


def build_tool_handlers(runtime: Runtime) -> dict[str, object]:
    return {
        "tfs_detect_project": lambda path: runtime.detector.detect(path),
        "tfs_onboard_project": lambda path: runtime.onboarding.build(path),
        "tfs_checkout": lambda filepath: runtime.executor.run(["checkout", filepath]),
        "tfs_undo": lambda filepath: runtime.executor.run(["undo", filepath]),
        "tfs_session_create": lambda name, source_path, session_path: runtime.sessions.create(name, source_path, session_path),
        "tfs_session_list": lambda: runtime.sessions.list_records(),
        "tfs_session_suspend": lambda name: runtime.sessions.suspend(name),
        "tfs_session_discard": lambda name: runtime.sessions.discard(name),
        "tfs_session_resume": lambda name: runtime.sessions.resume(name),
        "tfs_session_promote": lambda name, comment=None: runtime.sessions.promote(name, comment),
    }


def build_mcp_server(runtime: Runtime) -> FastMCP:
    server = FastMCP("TFS_Tools")
    handlers = build_tool_handlers(runtime)
    for name, handler in handlers.items():
        server.tool(name=name)(handler)
    return server
