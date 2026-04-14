from dataclasses import asdict, is_dataclass
import json

from mcp.server.fastmcp import FastMCP

from tfsmcp.runtime import Runtime


def _to_json_value(value):
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [_to_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_to_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_json_value(item) for key, item in value.items()}
    return value


def build_tool_handlers(runtime: Runtime) -> dict[str, object]:
    return {
        "tfs_detect_project": lambda path: runtime.detector.detect(path),
        "tfs_onboard_project": lambda path: runtime.onboarding.build(path),
        "tfs_checkout": lambda filepath: runtime.executor.run(["checkout", filepath]),
        "tfs_undo": lambda filepath: runtime.executor.run(["undo", filepath]),
        "tfs_session_create": lambda name, source_path, session_path: _to_json_value(
            runtime.sessions.create(name, source_path, session_path)
        ),
        "tfs_session_list": lambda: json.dumps(
            {"sessions": _to_json_value(runtime.sessions.list_records())},
            ensure_ascii=False,
        ),
        "tfs_session_suspend": lambda name: _to_json_value(runtime.sessions.suspend(name)),
        "tfs_session_discard": lambda name: _to_json_value(runtime.sessions.discard(name)),
        "tfs_session_resume": lambda name: _to_json_value(runtime.sessions.resume(name)),
        "tfs_session_promote": lambda name, comment=None: _to_json_value(runtime.sessions.promote(name, comment)),
    }


def build_mcp_server(runtime: Runtime) -> FastMCP:
    server = FastMCP("TFS_Tools")
    handlers = build_tool_handlers(runtime)
    for name, handler in handlers.items():
        server.tool(name=name)(handler)
    return server
