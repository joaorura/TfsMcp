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


REAL_DIR = Path(r"D:\TFVC_ROOT\SPF\develop\Historico")
MCP_URL = "http://localhost:39393/mcp"
SERVER_PATH = "$/SPF/develop/Historico"


@pytest.mark.skipif(
    os.environ.get("TFSMCP_RUN_REAL_WORKTREE_TESTS") != "1",
    reason="Real MCP/TFS isolation test is disabled unless TFSMCP_RUN_REAL_WORKTREE_TESTS=1",
)
def test_real_worktree_isolation_with_backup_and_restore(tmp_path):
    txt_files = sorted([p for p in REAL_DIR.glob("*.txt") if p.is_file()])
    if len(txt_files) < 2:
        pytest.skip("Need at least two .txt files in D:/TFVC_ROOT/SPF/develop/Historico")

    source_file = txt_files[0]
    untouched_file = txt_files[1]

    source_backup = tmp_path / source_file.name
    untouched_backup = tmp_path / untouched_file.name
    shutil.copy2(source_file, source_backup)
    shutil.copy2(untouched_file, untouched_backup)

    suffix = uuid.uuid4().hex[:8]
    session_a = f"mcp-iso-a-{suffix}"
    session_b = f"mcp-iso-b-{suffix}"
    session_path_a = Path(r"D:\TFS\.tfs-sessions") / session_a
    session_path_b = Path(r"D:\TFS\.tfs-sessions") / session_b

    relative_name_1 = source_file.name
    relative_name_2 = untouched_file.name

    async def run_flow():
        await _wait_for_port("127.0.0.1", 39393, timeout_seconds=30.0)
        async with streamablehttp_client(MCP_URL) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                created_a = False
                created_b = False
                try:
                    create_a = await _call_tool_json(session, "tfs_session_create", {
                        "name": session_a,
                        "source_path": SERVER_PATH,
                        "session_path": str(session_path_a),
                    })
                    created_a = True
                    create_b = await _call_tool_json(session, "tfs_session_create", {
                        "name": session_b,
                        "source_path": SERVER_PATH,
                        "session_path": str(session_path_b),
                    })
                    created_b = True

                    assert create_a["status"] == "active"
                    assert create_b["status"] == "active"

                    session_a_file_1 = _find_file_by_name(session_path_a, relative_name_1)
                    session_b_file_1 = _find_file_by_name(session_path_b, relative_name_1)
                    session_b_file_2 = _find_file_by_name(session_path_b, relative_name_2)

                    assert session_a_file_1 is not None
                    assert session_b_file_1 is not None
                    assert session_b_file_2 is not None

                    await _call_tool_json(session, "tfs_checkout", {"filepath": str(session_a_file_1)})

                    marker = "\n[MCP-ISOLATION-TEST]\n"
                    with session_a_file_1.open("a", encoding="utf-8") as handle:
                        handle.write(marker)

                    # Worktree isolation assertion:
                    # change in session A must not modify source worktree or session B.
                    source_current = source_file.read_text(encoding="utf-8")
                    source_original = source_backup.read_text(encoding="utf-8")
                    session_b_current = session_b_file_1.read_text(encoding="utf-8")

                    assert source_current == source_original
                    assert session_b_current == source_original
                finally:
                    if created_a:
                        await _call_tool_json(session, "tfs_session_discard", {"name": session_a})
                    if created_b:
                        await _call_tool_json(session, "tfs_session_discard", {"name": session_b})

    try:
        anyio.run(run_flow)
    finally:
        _restore_if_needed(source_backup, source_file)
        _restore_if_needed(untouched_backup, untouched_file)


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


def _find_file_by_name(root: Path, filename: str) -> Path | None:
    if not root.exists():
        return None
    matches = list(root.rglob(filename))
    return matches[0] if matches else None


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
