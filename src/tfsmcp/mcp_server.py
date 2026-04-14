from dataclasses import asdict, is_dataclass
import json
from threading import Lock
from concurrent.futures import Future, ThreadPoolExecutor
from uuid import uuid4

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


def _detection_field(detection, key: str):
    if isinstance(detection, dict):
        return detection.get(key)
    return getattr(detection, key, None)


def build_tool_handlers(runtime: Runtime) -> dict[str, object]:
    session_jobs: dict[str, Future] = {}
    session_jobs_lock = Lock()
    session_job_runner = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tfsmcp-session")

    def _resolve_session_record(name: str):
        records = runtime.sessions.list_records()
        for record in records:
            record_name = record.get("name") if isinstance(record, dict) else getattr(record, "name", None)
            if record_name == name:
                return record
        raise KeyError(name)

    def _materialize_session_path(session_path: str, workspace_name: str | None = None, recursive: bool = True):
        args = ["get", session_path]
        if recursive:
            args.append("/recursive")
        if workspace_name:
            args.append(f"/workspace:{workspace_name}")
        args.append("/noprompt")
        return runtime.executor.run(args)

    def tfs_add(filepath: str, recursive: bool = False):
        args = ["add", filepath]
        if recursive:
            args.append("/recursive")
        return runtime.executor.run(args)

    def tfs_status(path: str, recursive: bool = True, workspace: str | None = None):
        args = ["status", path]
        if recursive:
            args.append("/recursive")
        if workspace:
            args.append(f"/workspace:{workspace}")
        return runtime.executor.run(args)

    def tfs_get_latest(path: str, recursive: bool = True, workspace: str | None = None):
        args = ["get", path]
        if recursive:
            args.append("/recursive")
        if workspace:
            args.append(f"/workspace:{workspace}")
        args.append("/noprompt")
        return runtime.executor.run(args)

    def tfs_shelveset_list(owner: str | None = None, name_pattern: str | None = None):
        args = ["shelvesets"]
        if name_pattern:
            args.append(name_pattern)
        if owner:
            args.append(f"/owner:{owner}")
        return runtime.executor.run(args)

    def tfs_unshelve(name: str, workspace: str | None = None):
        args = ["unshelve", name]
        if workspace:
            args.append(f"/workspace:{workspace}")
        args.append("/noprompt")
        return runtime.executor.run(args)

    def tfs_session_create_from_path(name: str, source_path: str, session_path: str, perform_get: bool = False):
        detection = runtime.detector.detect(source_path)
        kind = _detection_field(detection, "kind")
        server_path = _detection_field(detection, "server_path")
        if kind != "tfs_mapped" or not server_path:
            raise RuntimeError(f"Path is not TFS mapped: {source_path}")
        return _to_json_value(runtime.sessions.create(name, server_path, session_path, perform_get=perform_get))

    def tfs_session_create(name: str, source_path: str, session_path: str, perform_get: bool = False):
        return _to_json_value(runtime.sessions.create(name, source_path, session_path, perform_get=perform_get))

    def _submit_session_create(name: str, source_path: str, session_path: str, perform_get: bool) -> dict:
        job_id = str(uuid4())

        def _job_body():
            created = runtime.sessions.create(name, source_path, session_path, perform_get=perform_get)
            return _to_json_value(created)

        future = session_job_runner.submit(_job_body)
        with session_jobs_lock:
            session_jobs[job_id] = future

        return {
            "job_id": job_id,
            "status": "queued",
            "name": name,
            "source_path": source_path,
            "session_path": session_path,
            "perform_get": perform_get,
        }

    def tfs_session_create_async(name: str, source_path: str, session_path: str, perform_get: bool = False):
        return _submit_session_create(name, source_path, session_path, perform_get)

    def tfs_session_create_from_path_async(name: str, source_path: str, session_path: str, perform_get: bool = False):
        detection = runtime.detector.detect(source_path)
        kind = _detection_field(detection, "kind")
        server_path = _detection_field(detection, "server_path")
        if kind != "tfs_mapped" or not server_path:
            raise RuntimeError(f"Path is not TFS mapped: {source_path}")
        return _submit_session_create(name, server_path, session_path, perform_get)

    def tfs_session_create_job_status(job_id: str):
        with session_jobs_lock:
            future = session_jobs.get(job_id)
        if future is None:
            raise KeyError(job_id)

        if not future.done():
            return {"job_id": job_id, "status": "running"}

        exc = future.exception()
        if exc is not None:
            return {"job_id": job_id, "status": "failed", "error": str(exc)}

        return {"job_id": job_id, "status": "completed", "result": future.result()}

    def tfs_session_materialize(name: str | None = None, session_path: str | None = None, recursive: bool = True):
        if not name and not session_path:
            raise ValueError("Provide 'name' or 'session_path' for materialization")

        resolved_session_path = session_path
        workspace_name = None
        if name:
            record = _resolve_session_record(name)
            if not resolved_session_path:
                resolved_session_path = record.get("session_path") if isinstance(record, dict) else getattr(record, "session_path", None)
            workspace_name = record.get("workspace_name") if isinstance(record, dict) else getattr(record, "workspace_name", None)

        if not resolved_session_path:
            raise ValueError("Unable to resolve session_path for materialization")

        result = _materialize_session_path(resolved_session_path, workspace_name=workspace_name, recursive=recursive)
        return {
            "name": name,
            "session_path": resolved_session_path,
            "workspace_name": workspace_name,
            "result": _to_json_value(result),
        }

    def tfs_session_validate(name: str | None = None, path: str | None = None):
        records = runtime.sessions.list_records()
        selected = None
        if name:
            for record in records:
                record_name = record.get("name") if isinstance(record, dict) else getattr(record, "name", None)
                if record_name == name:
                    selected = record
                    break
            if selected is None:
                raise KeyError(name)

        target_path = path
        if target_path is None and selected is not None:
            target_path = selected.get("session_path") if isinstance(selected, dict) else getattr(selected, "session_path", None)
        if not target_path:
            raise ValueError("Provide 'name' or 'path' for validation")

        status_args = ["status", target_path, "/recursive"]
        workfold_args = ["workfold", target_path]

        workspace_name = None
        if selected is not None:
            workspace_name = selected.get("workspace_name") if isinstance(selected, dict) else getattr(selected, "workspace_name", None)
        if workspace_name:
            status_args.append(f"/workspace:{workspace_name}")
            workfold_args.append(f"/workspace:{workspace_name}")

        return {
            "input": {"name": name, "path": path},
            "target_path": target_path,
            "session": _to_json_value(selected) if selected is not None else None,
            "detection": _to_json_value(runtime.detector.detect(target_path)),
            "workfold": _to_json_value(runtime.executor.run(workfold_args)),
            "status": _to_json_value(runtime.executor.run(status_args)),
        }

    def tfs_checkin_preview(
        path: str | None = None,
        workspace: str | None = None,
        recursive: bool = True,
    ):
        if not path and not workspace:
            raise ValueError("Provide 'path' or 'workspace' for checkin preview")

        args = ["status"]
        if path:
            args.append(path)
        if recursive:
            args.append("/recursive")
        if workspace:
            args.append(f"/workspace:{workspace}")
        return runtime.executor.run(args)

    def tfs_history(path: str, stop_after: int | None = None, recursive: bool = False):
        args = ["history", path]
        if recursive:
            args.append("/recursive")
        if stop_after is not None:
            args.append(f"/stopafter:{stop_after}")
        return runtime.executor.run(args)

    def tfs_diff(path: str, recursive: bool = False, workspace: str | None = None):
        args = ["diff", path]
        if recursive:
            args.append("/recursive")
        if workspace:
            args.append(f"/workspace:{workspace}")
        return runtime.executor.run(args)

    return {
        "tfs_detect_project": lambda path: runtime.detector.detect(path),
        "tfs_onboard_project": lambda path: runtime.onboarding.build(path),
        "tfs_checkout": lambda filepath: runtime.executor.run(["checkout", filepath]),
        "tfs_add": tfs_add,
        "tfs_status": tfs_status,
        "tfs_get_latest": tfs_get_latest,
        "tfs_shelveset_list": tfs_shelveset_list,
        "tfs_unshelve": tfs_unshelve,
        "tfs_undo": lambda filepath: runtime.executor.run(["undo", filepath]),
        "tfs_session_create": tfs_session_create,
        "tfs_session_create_from_path": tfs_session_create_from_path,
        "tfs_session_create_async": tfs_session_create_async,
        "tfs_session_create_from_path_async": tfs_session_create_from_path_async,
        "tfs_session_create_job_status": tfs_session_create_job_status,
        "tfs_session_list": lambda: json.dumps(
            {"sessions": _to_json_value(runtime.sessions.list_records())},
            ensure_ascii=False,
        ),
        "tfs_session_materialize": tfs_session_materialize,
        "tfs_session_validate": tfs_session_validate,
        "tfs_session_suspend": lambda name: _to_json_value(runtime.sessions.suspend(name)),
        "tfs_session_discard": lambda name: _to_json_value(runtime.sessions.discard(name)),
        "tfs_session_resume": lambda name: _to_json_value(runtime.sessions.resume(name)),
        "tfs_session_promote": lambda name, comment=None: _to_json_value(runtime.sessions.promote(name, comment)),
        "tfs_checkin_preview": tfs_checkin_preview,
        "tfs_history": tfs_history,
        "tfs_diff": tfs_diff,
    }


def build_mcp_server(runtime: Runtime) -> FastMCP:
    server = FastMCP("TFS_Tools")
    handlers = build_tool_handlers(runtime)
    for name, handler in handlers.items():
        server.tool(name=name)(handler)
    return server
