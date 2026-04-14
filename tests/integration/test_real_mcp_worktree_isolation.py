import json
import os
import socket
import stat
import shutil
import uuid
from pathlib import Path

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def _load_local_real_test_config() -> dict:
    config_path = Path(__file__).with_name("real_test.local.json")
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


REAL_TEST_CONFIG = _load_local_real_test_config()
REAL_DIR = Path(
    os.environ.get(
        "TFSMCP_REAL_DIR",
        REAL_TEST_CONFIG.get("real_dir", r"D:\TFVC\Project\Main\Folder"),
    )
)
MCP_URL = "http://localhost:39393/mcp"
SESSION_ROOT = Path(
    os.environ.get(
        "TFSMCP_REAL_SESSION_ROOT",
        REAL_TEST_CONFIG.get("session_root", r"D:\TFVC\.tfs-sessions"),
    )
)
TEST_SESSION_PREFIXES = ("mcp-iso-", "dbg-iso-", "probe-", "peek-")


@pytest.mark.skipif(
    os.environ.get("TFSMCP_RUN_REAL_WORKTREE_TESTS") != "1",
    reason="Real MCP/TFS isolation test is disabled unless TFSMCP_RUN_REAL_WORKTREE_TESTS=1",
)
def test_real_worktree_isolation_with_backup_and_restore(tmp_path):
    _cleanup_real_test_artifacts()

    txt_files = sorted([p for p in REAL_DIR.glob("*.txt") if p.is_file()])
    if not txt_files:
        pytest.skip(f"Need at least one .txt file in configured TFSMCP_REAL_DIR: {REAL_DIR}")

    real_txt_by_name = {p.name: p for p in txt_files}
    source_path_candidates = _build_source_path_candidates()

    suffix = uuid.uuid4().hex[:8]
    session_root = SESSION_ROOT

    source_file: Path | None = None
    source_backup: Path | None = None

    async def run_flow():
        await _wait_for_port("127.0.0.1", 39393, timeout_seconds=30.0)
        async with streamablehttp_client(MCP_URL) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                created_a = False
                current_session_a_name: str | None = None
                selected_source_path: str | None = None
                session_a_file_1 = None
                try:
                    failures: list[str] = []
                    for idx, source_path in enumerate(source_path_candidates, start=1):
                        current_session_a_name = f"mcp-iso-a-{suffix}-{idx}"
                        session_path_a = session_root / current_session_a_name

                        create_a = await _call_tool_json(session, "tfs_session_create", {
                            "name": current_session_a_name,
                            "source_path": source_path,
                            "session_path": str(session_path_a),
                        })
                        created_a = True

                        if create_a.get("status") != "active":
                            failures.append(
                                f"source={source_path}: create status -> a={create_a.get('status')}"
                            )
                            await _call_tool_json(session, "tfs_session_discard", {"name": current_session_a_name})
                            created_a = False
                            continue

                        has_a = await _wait_for_any_txt(session_path_a, timeout_seconds=20.0, raise_on_timeout=False)
                        if not has_a:
                            failures.append(
                                f"source={source_path}: txt materialization timed out (a={has_a})"
                            )
                            await _call_tool_json(session, "tfs_session_discard", {"name": current_session_a_name})
                            created_a = False
                            continue

                        session_a_txt = sorted(session_path_a.rglob("*.txt"))
                        for candidate in session_a_txt:
                            if candidate.name not in real_txt_by_name:
                                continue
                            source_file = real_txt_by_name[candidate.name]
                            source_backup = tmp_path / source_file.name
                            shutil.copy2(source_file, source_backup)
                            session_a_file_1 = candidate
                            break

                        if source_file is not None and source_backup is not None and session_a_file_1 is not None:
                            selected_source_path = source_path
                            break

                        failures.append(
                            f"source={source_path}: no common txt file found between real dir and session A"
                        )
                        await _call_tool_json(session, "tfs_session_discard", {"name": current_session_a_name})
                        created_a = False

                    assert selected_source_path is not None, "Unable to materialize a compatible worktree source path. " + " | ".join(failures)
                    assert source_file is not None
                    assert source_backup is not None
                    assert session_a_file_1 is not None

                    checkout = await _call_tool_json(session, "tfs_checkout", {"filepath": str(session_a_file_1)})
                    assert checkout["exit_code"] == 0
                    assert checkout["category"] == "success"
                    assert checkout["recovery_triggered"] is False
                    assert checkout["retried"] is False
                    assert checkout["recovery_scripts"] == []

                    marker = "\n[MCP-ISOLATION-TEST]\n"
                    with session_a_file_1.open("a", encoding="utf-8") as handle:
                        handle.write(marker)

                    # Worktree isolation assertion:
                    # change in session A must not modify source worktree.
                    source_current = source_file.read_text(encoding="utf-8")
                    source_original = source_backup.read_text(encoding="utf-8")

                    assert source_current == source_original

                    # Now create session B after discarding A and ensure marker is absent.
                    await _call_tool_json(session, "tfs_session_discard", {"name": current_session_a_name})
                    created_a = False

                    current_session_b_name = f"mcp-iso-b-{suffix}-{uuid.uuid4().hex[:4]}"
                    session_path_b = session_root / current_session_b_name
                    create_b = await _call_tool_json(session, "tfs_session_create", {
                        "name": current_session_b_name,
                        "source_path": selected_source_path,
                        "session_path": str(session_path_b),
                    })
                    assert create_b.get("status") == "active"

                    has_b = await _wait_for_any_txt(session_path_b, timeout_seconds=20.0, raise_on_timeout=False)
                    assert has_b is True
                    session_b_file_1 = _find_file_by_name(session_path_b, source_file.name)
                    assert session_b_file_1 is not None
                    session_b_current = session_b_file_1.read_text(encoding="utf-8")
                    assert "[MCP-ISOLATION-TEST]" not in session_b_current

                    await _call_tool_json(session, "tfs_session_discard", {"name": current_session_b_name})
                finally:
                    if created_a and current_session_a_name:
                        await _call_tool_json(session, "tfs_session_discard", {"name": current_session_a_name})

    try:
        anyio.run(run_flow)
    finally:
        if source_backup is not None and source_file is not None:
            _restore_if_needed(source_backup, source_file)
        _cleanup_real_test_artifacts()


def _extract_json_text(tool_result) -> dict:
    if getattr(tool_result, "isError", False):
        details = [getattr(item, "text", "") for item in getattr(tool_result, "content", [])]
        raise AssertionError("Tool call failed: " + " | ".join(details))

    structured = getattr(tool_result, "structuredContent", None)
    if structured:
        return structured

    for item in getattr(tool_result, "content", []):
        text = getattr(item, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue
    raise AssertionError("Tool result did not contain JSON text content")


async def _call_tool_json(session: ClientSession, tool_name: str, args: dict):
    result = await session.call_tool(tool_name, args)
    return _extract_json_text(result)


async def _wait_for_any_txt(root: Path, timeout_seconds: float, raise_on_timeout: bool = True) -> bool:
    deadline = anyio.current_time() + timeout_seconds
    while True:
        if root.exists() and any(root.rglob("*.txt")):
            return True
        if anyio.current_time() >= deadline:
            if raise_on_timeout:
                raise AssertionError(f"No .txt files found under session path within {timeout_seconds:.0f}s: {root}")
            return False
        await anyio.sleep(0.5)


def _build_source_path_candidates() -> list[str]:
    candidates: list[str] = []
    env_source = os.environ.get("TFSMCP_REAL_SOURCE_PATH")
    if env_source:
        candidates.append(env_source)

    configured = REAL_TEST_CONFIG.get("source_path_candidates", [])
    for candidate in configured:
        if isinstance(candidate, str) and candidate:
            candidates.append(candidate)

    candidates.extend([
        "$/Project/Main/Folder",
        "$/Project/Main",
    ])

    # Preserve order while removing duplicates.
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _find_file_by_name(root: Path, filename: str) -> Path | None:
    if not root.exists():
        return None
    matches = list(root.rglob(filename))
    return matches[0] if matches else None


def _cleanup_real_test_artifacts() -> None:
    _cleanup_state_records()
    _cleanup_session_directories()


def _cleanup_state_records() -> None:
    state_file = Path(os.environ.get("LOCALAPPDATA", "C:/ProgramData")) / "TfsMcp" / "sessions.json"
    if not state_file.exists():
        return

    payload = json.loads(state_file.read_text(encoding="utf-8"))
    kept = [item for item in payload if not str(item.get("name", "")).startswith(TEST_SESSION_PREFIXES)]
    if len(kept) == len(payload):
        return
    state_file.write_text(json.dumps(kept, indent=2), encoding="utf-8")


def _cleanup_session_directories() -> None:
    session_root = SESSION_ROOT
    if not session_root.exists():
        return

    for directory in session_root.iterdir():
        if not directory.is_dir() or not directory.name.startswith(TEST_SESSION_PREFIXES):
            continue
        _force_remove_tree(directory)


def _force_remove_tree(root: Path) -> None:
    if not root.exists():
        return

    for entry in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        try:
            os.chmod(entry, stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            pass
    try:
        os.chmod(root, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass
    shutil.rmtree(root, ignore_errors=True)


def _restore_if_needed(backup: Path, target: Path) -> None:
    if not backup.exists() or not target.exists():
        return
    backup_bytes = backup.read_bytes()
    target_bytes = target.read_bytes()
    if backup_bytes == target_bytes:
        return

    os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
    shutil.copy2(backup, target)


async def _wait_for_port(host: str, port: int, timeout_seconds: float) -> None:
    deadline = anyio.current_time() + timeout_seconds
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        try:
            sock.connect((host, port))
            return
        except OSError:
            if anyio.current_time() >= deadline:
                raise AssertionError(
                    f"MCP server at {host}:{port} did not become ready within {timeout_seconds:.0f}s"
                )
            await anyio.sleep(0.5)
        finally:
            sock.close()
