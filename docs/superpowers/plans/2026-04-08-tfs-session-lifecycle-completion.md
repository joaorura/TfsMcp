# TFS Session Lifecycle Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the public MCP/HTTP session lifecycle so the TFS worktree-like flow supports create, list, suspend, discard, and real runtime-backed session actions instead of placeholder-only creation.

**Architecture:** Extend the existing `SessionManager` and runtime session actions so the public MCP/HTTP layer can drive the full session lifecycle, not just record creation. Keep the session abstraction honest: public APIs should manage session state and delegate real session-side effects through a dedicated runtime adapter, while docs and tests describe exactly what is implemented.

**Tech Stack:** Python 3.12, FastAPI, FastMCP, pytest

---

## Scope check

This work is cohesive enough for one plan because it completes a single subsystem: the public session lifecycle for the TFS worktree-like abstraction. The missing MCP/HTTP tools, runtime adapter behavior, and documentation all describe the same feature boundary and should be delivered together.

## File structure

### Modify
- `src/tfsmcp/contracts.py` — extend session records only if lifecycle metadata needs an explicit field for persisted transitions
- `src/tfsmcp/sessions/manager.py` — add public lifecycle methods needed by MCP/HTTP (`suspend`, `discard`) and keep create/list behavior consistent
- `src/tfsmcp/runtime.py` — replace the placeholder-only `RuntimeSessionActions` behavior with a minimal but coherent session action adapter for create/suspend/discard
- `src/tfsmcp/mcp_server.py` — expose `tfs_session_suspend` and `tfs_session_discard` alongside create/list
- `src/tfsmcp/http_app.py` — expose `POST /sessions/{name}/suspend` and `DELETE /sessions/{name}`
- `README.md` — document the actual public session lifecycle surface and current limitations

### Create
- `tests/sessions/test_runtime_session_actions.py` — targeted tests for runtime session side-effect adapter behavior

### Test
- `tests/test_mcp_tools.py` — MCP handler delegation/registration for session lifecycle
- `tests/test_http_app.py` — HTTP session lifecycle endpoint coverage
- `tests/sessions/test_manager.py` — manager lifecycle and state-transition coverage
- `tests/test_readme.py` — README assertions aligned to the completed surface

## Task 1: Add runtime-backed session side effects

**Files:**
- Modify: `src/tfsmcp/runtime.py`
- Test: `tests/sessions/test_runtime_session_actions.py`

- [ ] **Step 1: Write the failing test**

```python
from tfsmcp.runtime import RuntimeSessionActions


class FakeWorkspaceExecutor:
    def __init__(self):
        self.commands = []

    def run(self, args):
        self.commands.append(args)
        return {"command": args}


def test_runtime_session_actions_uses_executor_for_create_suspend_discard(tmp_path):
    executor = FakeWorkspaceExecutor()
    actions = RuntimeSessionActions(executor)

    server_path = actions.create_workspace("agent-auth", "$/SPF/Main", str(tmp_path / "agent-auth"))
    shelveset = actions.create_shelveset("agent-auth")
    actions.remove_workspace("agent-auth")

    assert server_path == "$/SPF/Main"
    assert shelveset == "agent-auth"
    assert executor.commands == [
        ["workspace", "agent-auth", str(tmp_path / "agent-auth")],
        ["shelve", "agent-auth"],
        ["workspace", "/delete", "agent-auth"],
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/sessions/test_runtime_session_actions.py -q`
Expected: FAIL because `RuntimeSessionActions` does not yet accept an executor or emit these commands.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tfsmcp/runtime.py
class RuntimeSessionActions:
    def __init__(self, executor) -> None:
        self._executor = executor

    def create_workspace(self, name: str, source_path: str, session_path: str) -> str:
        self._executor.run(["workspace", name, session_path])
        normalized_source = source_path.replace("\\", "/")
        return normalized_source if normalized_source.startswith("$/") else "$/" + "/".join(part.strip("/\\") for part in PureWindowsPath(source_path).parts if part and not part.endswith(":\\"))

    def create_shelveset(self, workspace_name: str) -> str:
        self._executor.run(["shelve", workspace_name])
        return workspace_name

    def remove_workspace(self, workspace_name: str) -> None:
        self._executor.run(["workspace", "/delete", workspace_name])
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/sessions/test_runtime_session_actions.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tfsmcp/runtime.py tests/sessions/test_runtime_session_actions.py
git commit -m "feat: add runtime session action adapter"
```

### Task 2: Expose full session lifecycle in the manager

**Files:**
- Modify: `src/tfsmcp/sessions/manager.py`
- Test: `tests/sessions/test_manager.py`

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from tfsmcp.sessions.manager import SessionManager
from tfsmcp.sessions.store import SessionStore


class FakeWorkspaceActions:
    def __init__(self) -> None:
        self.created = []
        self.shelvesets = []
        self.removed = []

    def create_workspace(self, name: str, source_path: str, session_path: str) -> str:
        self.created.append((name, source_path, session_path))
        return source_path

    def create_shelveset(self, workspace_name: str) -> str:
        self.shelvesets.append(workspace_name)
        return workspace_name

    def remove_workspace(self, workspace_name: str) -> None:
        self.removed.append(workspace_name)


def test_session_lifecycle_list_suspend_discard_roundtrip(tmp_path):
    store = SessionStore(tmp_path / "sessions.json")
    actions = FakeWorkspaceActions()
    manager = SessionManager(store, actions)

    created = manager.create("agent-auth", "$/SPF/Main", tmp_path / "agent-auth")
    suspended = manager.suspend("agent-auth")
    discarded = manager.discard("agent-auth")

    assert manager.list_records()[0].status == "discarded"
    assert created.status == "active"
    assert suspended.last_shelveset == "agent-auth"
    assert discarded.status == "discarded"


def test_discard_missing_session_raises_key_error(tmp_path):
    store = SessionStore(tmp_path / "sessions.json")
    manager = SessionManager(store, FakeWorkspaceActions())

    with pytest.raises(KeyError, match="missing"):
        manager.discard("missing")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/sessions/test_manager.py -q`
Expected: FAIL if lifecycle methods or stored transitions are inconsistent.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tfsmcp/sessions/manager.py
class SessionManager:
    ...

    def suspend(self, name: str) -> SessionRecord:
        records = self._store.load_all()
        for record in records:
            if record.name == name:
                record.status = "suspended"
                record.last_shelveset = self._actions.create_shelveset(record.workspace_name)
                self._store.save_all(records)
                return record
        raise KeyError(name)

    def discard(self, name: str) -> SessionRecord:
        records = self._store.load_all()
        for record in records:
            if record.name == name:
                self._actions.remove_workspace(record.workspace_name)
                record.status = "discarded"
                self._store.save_all(records)
                return record
        raise KeyError(name)
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/sessions/test_manager.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tfsmcp/sessions/manager.py tests/sessions/test_manager.py
git commit -m "feat: finalize session manager lifecycle"
```

### Task 3: Expose suspend and discard in MCP

**Files:**
- Modify: `src/tfsmcp/mcp_server.py`
- Test: `tests/test_mcp_tools.py`

- [ ] **Step 1: Write the failing test**

```python
from tfsmcp.mcp_server import build_mcp_server, build_tool_handlers
from tfsmcp.runtime import Runtime


class FakeSessions:
    def __init__(self):
        self.calls = []

    def create(self, name: str, source_path: str, session_path: str):
        self.calls.append(("create", name, source_path, session_path))
        return {"name": name}

    def list_records(self):
        return []

    def suspend(self, name: str):
        self.calls.append(("suspend", name))
        return {"name": name, "status": "suspended"}

    def discard(self, name: str):
        self.calls.append(("discard", name))
        return {"name": name, "status": "discarded"}


def test_session_handlers_delegate_create_suspend_discard(monkeypatch):
    runtime = Runtime(config=None, detector=None, onboarding=None, executor=None, sessions=FakeSessions())
    handlers = build_tool_handlers(runtime)

    assert handlers["tfs_session_create"]("agent-auth", "$/SPF/Main", "D:/TFS/agent-auth")["name"] == "agent-auth"
    assert handlers["tfs_session_suspend"]("agent-auth")["status"] == "suspended"
    assert handlers["tfs_session_discard"]("agent-auth")["status"] == "discarded"


def test_build_mcp_server_registers_session_lifecycle_tools(monkeypatch):
    names = []

    class FakeMCP:
        def __init__(self, name: str):
            self.name = name

        def tool(self, name: str):
            def register(handler):
                names.append(name)
                return handler
            return register

    monkeypatch.setattr("tfsmcp.mcp_server.FastMCP", FakeMCP)
    runtime = Runtime(config=None, detector=None, onboarding=None, executor=None, sessions=FakeSessions())

    build_mcp_server(runtime)

    assert "tfs_session_create" in names
    assert "tfs_session_suspend" in names
    assert "tfs_session_discard" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_mcp_tools.py -q`
Expected: FAIL because suspend/discard handlers are not registered yet.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tfsmcp/mcp_server.py
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
    }
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_mcp_tools.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tfsmcp/mcp_server.py tests/test_mcp_tools.py
git commit -m "feat: expose session lifecycle tools"
```

### Task 4: Expose suspend and discard in HTTP

**Files:**
- Modify: `src/tfsmcp/http_app.py`
- Test: `tests/test_http_app.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from tfsmcp.http_app import build_http_app
from tfsmcp.runtime import Runtime


class FakeSessions:
    def __init__(self):
        self.calls = []

    def create(self, name: str, source_path: str, session_path: str):
        self.calls.append(("create", name, source_path, session_path))
        return {"name": name, "status": "active"}

    def list_records(self):
        return []

    def suspend(self, name: str):
        self.calls.append(("suspend", name))
        return {"name": name, "status": "suspended"}

    def discard(self, name: str):
        self.calls.append(("discard", name))
        return {"name": name, "status": "discarded"}


def test_http_session_lifecycle_endpoints():
    runtime = Runtime(config=None, detector=None, onboarding=None, executor=None, sessions=FakeSessions())
    client = TestClient(build_http_app(runtime))

    created = client.post("/sessions", json={"name": "agent-auth", "source_path": "$/SPF/Main", "session_path": "D:/TFS/agent-auth"})
    suspended = client.post("/sessions/agent-auth/suspend")
    discarded = client.delete("/sessions/agent-auth")

    assert created.status_code == 200
    assert created.json()["data"]["status"] == "active"
    assert suspended.json()["data"]["status"] == "suspended"
    assert discarded.json()["data"]["status"] == "discarded"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_http_app.py -q`
Expected: FAIL because suspend/discard routes do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tfsmcp/http_app.py
@app.post("/sessions/{name}/suspend")
def suspend_session(name: str):
    record = runtime.sessions.suspend(name)
    return {"ok": True, "data": jsonable_encoder(record), "error": None, "meta": {}}

@app.delete("/sessions/{name}")
def discard_session(name: str):
    record = runtime.sessions.discard(name)
    return {"ok": True, "data": jsonable_encoder(record), "error": None, "meta": {}}
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_http_app.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tfsmcp/http_app.py tests/test_http_app.py
git commit -m "feat: add http session lifecycle endpoints"
```

### Task 5: Align docs and README assertions to the completed public surface

**Files:**
- Modify: `README.md`
- Modify: `tests/test_readme.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

README_PATH = Path(__file__).resolve().parents[1] / "README.md"


def test_readme_mentions_session_lifecycle_surface():
    readme = README_PATH.read_text(encoding="utf-8")

    assert "tfs_session_create" in readme
    assert "tfs_session_list" in readme
    assert "tfs_session_suspend" in readme
    assert "tfs_session_discard" in readme
    assert "POST /sessions" in readme
    assert "POST /sessions/{name}/suspend" in readme
    assert "DELETE /sessions/{name}" in readme
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_readme.py -q`
Expected: FAIL because README does not yet document suspend/discard.

- [ ] **Step 3: Write minimal documentation**

```md
## Session APIs

MCP tools:
- `tfs_session_create(name, source_path, session_path)` creates and stores an active session record.
- `tfs_session_list()` returns the stored session records.
- `tfs_session_suspend(name)` stores a suspended state and checkpoint name.
- `tfs_session_discard(name)` marks the session discarded and removes its workspace through the runtime session adapter.

HTTP endpoints:
- `POST /sessions` with JSON fields `name`, `source_path`, and `session_path` creates a session.
- `GET /sessions` returns the stored session records.
- `POST /sessions/{name}/suspend` suspends a session.
- `DELETE /sessions/{name}` discards a session.

The current lifecycle is minimally functional: it records state transitions and drives the runtime session adapter, but it still does not create real TFS workspace mappings or a full shelveset-based resume/promote flow.
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_readme.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_readme.py
git commit -m "docs: describe session lifecycle surface"
```

### Task 6: Run focused verification for completed session lifecycle

**Files:**
- Modify: `README.md:44-60`
- Modify: `src/tfsmcp/runtime.py:16-56`
- Modify: `src/tfsmcp/mcp_server.py:6-22`
- Modify: `src/tfsmcp/http_app.py:28-37`
- Modify: `src/tfsmcp/sessions/manager.py:14-52`
- Test: `tests/sessions/test_runtime_session_actions.py`
- Test: `tests/sessions/test_manager.py`
- Test: `tests/test_mcp_tools.py`
- Test: `tests/test_http_app.py`
- Test: `tests/test_readme.py`

- [ ] **Step 1: Run focused verification suite**

Run: `python -m pytest tests/sessions/test_runtime_session_actions.py tests/sessions/test_manager.py tests/test_mcp_tools.py tests/test_http_app.py tests/test_readme.py -q`
Expected: PASS with all targeted lifecycle tests green.

- [ ] **Step 2: Verify the exposed session surface in code**

Run: `python -m pytest tests/test_mcp_tools.py::test_build_mcp_server_registers_session_lifecycle_tools -q`
Expected: PASS and confirm MCP exposes create/list/suspend/discard.

- [ ] **Step 3: Verify the HTTP lifecycle endpoints**

Run: `python -m pytest tests/test_http_app.py::test_http_session_lifecycle_endpoints -q`
Expected: PASS and confirm POST/GET/DELETE lifecycle coverage.

- [ ] **Step 4: Commit**

```bash
git add src/tfsmcp/runtime.py src/tfsmcp/sessions/manager.py src/tfsmcp/mcp_server.py src/tfsmcp/http_app.py README.md tests/sessions/test_runtime_session_actions.py tests/sessions/test_manager.py tests/test_mcp_tools.py tests/test_http_app.py tests/test_readme.py
git commit -m "feat: complete public session lifecycle surface"
```

## Self-review

### Spec coverage
- Task 1 covers replacing placeholder-only runtime session actions with an executor-backed adapter.
- Task 2 covers manager lifecycle consistency for create/list/suspend/discard.
- Task 3 covers MCP lifecycle exposure.
- Task 4 covers HTTP lifecycle exposure.
- Task 5 aligns docs and tests with the real public surface.
- Task 6 verifies the completed lifecycle as a single focused slice.

No spec gaps remain for completing the current public session lifecycle surface. This plan intentionally does **not** claim to implement real TFS workspace mapping, resume, or promote; those remain future work.

### Placeholder scan
- No TODO/TBD placeholders remain.
- Every task includes concrete files, test code, commands, and implementation snippets.

### Type consistency
- Session lifecycle method names are consistent across manager, MCP, HTTP, tests, and README: `create`, `list`, `suspend`, `discard`.
- HTTP payload fields remain `name`, `source_path`, and `session_path` consistently.
- MCP tools remain `tfs_session_create`, `tfs_session_list`, `tfs_session_suspend`, `tfs_session_discard` consistently.
