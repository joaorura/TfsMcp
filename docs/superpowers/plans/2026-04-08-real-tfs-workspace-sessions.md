# Real TFS Workspace Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the placeholder session adapter with real TFS workspace and mapping operations, and complete the session lifecycle with resume/promote so the TFS session model behaves much closer to a real worktree flow.

**Architecture:** Keep `SessionManager` as the state/persistence layer and upgrade `RuntimeSessionActions` into a real TFS-backed adapter that drives `tf workspace`, `tf workfold`, and `tf get`/`tf shelve` style operations through the existing executor. Then expose the remaining lifecycle operations through MCP and HTTP, and document the resulting contract precisely.

**Tech Stack:** Python 3.12, FastAPI, FastMCP, pytest

---

## Scope check

This is still one cohesive subsystem: moving the current minimal public session lifecycle from placeholder behavior to real TFS-backed workspace behavior. The real workspace adapter, resume/promote lifecycle, and public MCP/HTTP surface belong together because they all define the same user-visible session model.

## File structure

### Modify
- `src/tfsmcp/contracts.py` — extend `SessionRecord` with the minimum metadata required for resume/promote (for example workspace state, optional last action, or persisted local path fields if needed)
- `src/tfsmcp/sessions/manager.py` — add `resume`, `promote`, and any persisted lifecycle updates needed to coordinate the real adapter
- `src/tfsmcp/runtime.py` — replace placeholder session actions with real TFS command orchestration using the existing executor
- `src/tfsmcp/mcp_server.py` — expose `tfs_session_resume` and `tfs_session_promote`
- `src/tfsmcp/http_app.py` — expose `POST /sessions/{name}/resume` and `POST /sessions/{name}/promote`
- `README.md` — document real workspace-backed behavior and the remaining limitations

### Create
- `tests/sessions/test_runtime_real_session_actions.py` — targeted tests for real TFS workspace/mapping/get/shelve command orchestration

### Test
- `tests/sessions/test_manager.py` — resume/promote lifecycle coverage
- `tests/test_mcp_tools.py` — MCP lifecycle registration/delegation for resume/promote
- `tests/test_http_app.py` — HTTP resume/promote endpoint coverage
- `tests/test_readme.py` — README assertions aligned to the upgraded surface

## Task 1: Upgrade runtime session actions to real TFS workspace orchestration

**Files:**
- Modify: `src/tfsmcp/runtime.py`
- Create: `tests/sessions/test_runtime_real_session_actions.py`

- [ ] **Step 1: Write the failing test**

```python
from tfsmcp.runtime import RuntimeSessionActions


class FakeExecutor:
    def __init__(self):
        self.commands = []

    def run(self, args):
        self.commands.append(args)
        return {"command": args, "stdout": "ok", "stderr": "", "exit_code": 0}


def test_runtime_session_actions_creates_real_workspace_mapping_and_get(tmp_path):
    executor = FakeExecutor()
    actions = RuntimeSessionActions(executor)

    server_path = actions.create_workspace("agent-auth", "$/SPF/Main", str(tmp_path / "agent-auth"))

    assert server_path == "$/SPF/Main"
    assert executor.commands == [
        ["workspace", "/new", "agent-auth"],
        ["workfold", "/map", "$/SPF/Main", str(tmp_path / "agent-auth"), "/workspace:agent-auth"],
        ["get", str(tmp_path / "agent-auth"), "/recursive"],
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/sessions/test_runtime_real_session_actions.py -q`
Expected: FAIL because the runtime adapter still emits placeholder commands.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tfsmcp/runtime.py
class RuntimeSessionActions:
    def __init__(self, executor) -> None:
        self._executor = executor

    def create_workspace(self, name: str, source_path: str, session_path: str) -> str:
        normalized_source = source_path.replace("\\", "/")
        server_path = normalized_source if normalized_source.startswith("$/") else "$/" + "/".join(part.strip("/\\") for part in PureWindowsPath(source_path).parts if part and not part.endswith(":\\"))
        self._executor.run(["workspace", "/new", name])
        self._executor.run(["workfold", "/map", server_path, session_path, f"/workspace:{name}"])
        self._executor.run(["get", session_path, "/recursive"])
        return server_path

    def create_shelveset(self, workspace_name: str) -> str:
        self._executor.run(["shelve", workspace_name])
        return workspace_name

    def remove_workspace(self, workspace_name: str) -> None:
        self._executor.run(["workspace", "/delete", workspace_name])
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/sessions/test_runtime_real_session_actions.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tfsmcp/runtime.py tests/sessions/test_runtime_real_session_actions.py
git commit -m "feat: add real tfs workspace session adapter"
```

### Task 2: Extend persisted session lifecycle with resume and promote

**Files:**
- Modify: `src/tfsmcp/contracts.py`
- Modify: `src/tfsmcp/sessions/manager.py`
- Test: `tests/sessions/test_manager.py`

- [ ] **Step 1: Write the failing test**

```python
from tfsmcp.sessions.manager import SessionManager
from tfsmcp.sessions.store import SessionStore


class FakeWorkspaceActions:
    def __init__(self) -> None:
        self.shelvesets = []
        self.resumed = []
        self.promoted = []

    def create_workspace(self, name: str, source_path: str, session_path: str) -> str:
        return source_path

    def create_shelveset(self, workspace_name: str) -> str:
        self.shelvesets.append(workspace_name)
        return workspace_name

    def remove_workspace(self, workspace_name: str) -> None:
        return None

    def resume_workspace(self, workspace_name: str, session_path: str) -> None:
        self.resumed.append((workspace_name, session_path))

    def promote_workspace(self, workspace_name: str, comment: str | None) -> str:
        self.promoted.append((workspace_name, comment))
        return comment or workspace_name


def test_session_resume_and_promote_roundtrip(tmp_path):
    store = SessionStore(tmp_path / "sessions.json")
    actions = FakeWorkspaceActions()
    manager = SessionManager(store, actions)

    manager.create("agent-auth", "$/SPF/Main", tmp_path / "agent-auth")
    manager.suspend("agent-auth")
    resumed = manager.resume("agent-auth")
    promoted = manager.promote("agent-auth", "ship it")

    assert resumed.status == "active"
    assert promoted.status == "promoted"
    assert promoted.last_shelveset == "ship it"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/sessions/test_manager.py -q`
Expected: FAIL because resume/promote do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tfsmcp/sessions/manager.py
class SessionManager:
    ...

    def resume(self, name: str) -> SessionRecord:
        records = self._store.load_all()
        for record in records:
            if record.name == name:
                self._actions.resume_workspace(record.workspace_name, record.session_path)
                record.status = "active"
                self._store.save_all(records)
                return record
        raise KeyError(name)

    def promote(self, name: str, comment: str | None) -> SessionRecord:
        records = self._store.load_all()
        for record in records:
            if record.name == name:
                record.last_shelveset = self._actions.promote_workspace(record.workspace_name, comment)
                record.status = "promoted"
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
git add src/tfsmcp/contracts.py src/tfsmcp/sessions/manager.py tests/sessions/test_manager.py
git commit -m "feat: add session resume and promote lifecycle"
```

### Task 3: Expose resume and promote in MCP

**Files:**
- Modify: `src/tfsmcp/mcp_server.py`
- Test: `tests/test_mcp_tools.py`

- [ ] **Step 1: Write the failing test**

```python
from tfsmcp.mcp_server import build_tool_handlers
from tfsmcp.runtime import Runtime


class FakeSessions:
    def __init__(self):
        self.calls = []

    def create(self, name: str, source_path: str, session_path: str):
        return {"name": name}

    def list_records(self):
        return []

    def suspend(self, name: str):
        return {"name": name, "status": "suspended"}

    def discard(self, name: str):
        return {"name": name, "status": "discarded"}

    def resume(self, name: str):
        self.calls.append(("resume", name))
        return {"name": name, "status": "active"}

    def promote(self, name: str, comment: str | None):
        self.calls.append(("promote", name, comment))
        return {"name": name, "status": "promoted", "last_shelveset": comment}


def test_session_handlers_delegate_resume_and_promote():
    sessions = FakeSessions()
    runtime = Runtime(config=None, detector=None, onboarding=None, executor=None, sessions=sessions)
    handlers = build_tool_handlers(runtime)

    assert handlers["tfs_session_resume"]("agent-auth")["status"] == "active"
    assert handlers["tfs_session_promote"]("agent-auth", "ship it")["status"] == "promoted"
    assert sessions.calls == [("resume", "agent-auth"), ("promote", "agent-auth", "ship it")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_mcp_tools.py -q`
Expected: FAIL because resume/promote tools are missing.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tfsmcp/mcp_server.py
def build_tool_handlers(runtime: Runtime) -> dict[str, object]:
    return {
        ...
        "tfs_session_resume": lambda name: runtime.sessions.resume(name),
        "tfs_session_promote": lambda name, comment=None: runtime.sessions.promote(name, comment),
    }
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_mcp_tools.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tfsmcp/mcp_server.py tests/test_mcp_tools.py
git commit -m "feat: expose session resume and promote tools"
```

### Task 4: Expose resume and promote in HTTP

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
        return {"name": name, "status": "active"}

    def list_records(self):
        return []

    def suspend(self, name: str):
        return {"name": name, "status": "suspended"}

    def discard(self, name: str):
        return {"name": name, "status": "discarded"}

    def resume(self, name: str):
        self.calls.append(("resume", name))
        return {"name": name, "status": "active"}

    def promote(self, name: str, comment: str | None):
        self.calls.append(("promote", name, comment))
        return {"name": name, "status": "promoted", "last_shelveset": comment}


def test_http_resume_and_promote_endpoints():
    runtime = Runtime(config=None, detector=None, onboarding=None, executor=None, sessions=FakeSessions())
    client = TestClient(build_http_app(runtime))

    resumed = client.post("/sessions/agent-auth/resume")
    promoted = client.post("/sessions/agent-auth/promote", json={"comment": "ship it"})

    assert resumed.json()["data"]["status"] == "active"
    assert promoted.json()["data"]["status"] == "promoted"
    assert promoted.json()["data"]["last_shelveset"] == "ship it"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_http_app.py -q`
Expected: FAIL because resume/promote routes are missing.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tfsmcp/http_app.py
@app.post("/sessions/{name}/resume")
def resume_session(name: str):
    record = runtime.sessions.resume(name)
    return {"ok": True, "data": jsonable_encoder(record), "error": None, "meta": {}}

@app.post("/sessions/{name}/promote")
def promote_session(name: str, payload: dict[str, str | None] | None = None):
    payload = payload or {}
    record = runtime.sessions.promote(name, payload.get("comment"))
    return {"ok": True, "data": jsonable_encoder(record), "error": None, "meta": {}}
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_http_app.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tfsmcp/http_app.py tests/test_http_app.py
git commit -m "feat: add http resume and promote endpoints"
```

### Task 5: Align docs to the upgraded real-workspace surface

**Files:**
- Modify: `README.md`
- Modify: `tests/test_readme.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

README_PATH = Path(__file__).resolve().parents[1] / "README.md"


def test_readme_mentions_real_workspace_session_surface():
    readme = README_PATH.read_text(encoding="utf-8")

    assert "tfs_session_resume" in readme
    assert "tfs_session_promote" in readme
    assert "POST /sessions/{name}/resume" in readme
    assert "POST /sessions/{name}/promote" in readme
    assert "tf workspace /new" in readme
    assert "tf workfold /map" in readme
    assert "tf get" in readme
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_readme.py -q`
Expected: FAIL because README does not yet describe the upgraded workspace-backed lifecycle.

- [ ] **Step 3: Write minimal documentation**

```md
## Session APIs

MCP tools:
- `tfs_session_create(name, source_path, session_path)` creates a TFS-backed session workspace and stores an active session record.
- `tfs_session_list()` returns the stored session records.
- `tfs_session_suspend(name)` stores a suspended state and checkpoint name.
- `tfs_session_discard(name)` discards a session and deletes its workspace.
- `tfs_session_resume(name)` restores an existing session to active state.
- `tfs_session_promote(name, comment)` records a promoted state and stores the promote/checkpoint result.

HTTP endpoints:
- `POST /sessions`
- `GET /sessions`
- `POST /sessions/{name}/suspend`
- `DELETE /sessions/{name}`
- `POST /sessions/{name}/resume`
- `POST /sessions/{name}/promote`

Current real-workspace behavior:
- session creation runs `tf workspace /new`
- maps with `tf workfold /map`
- populates files with `tf get`

Still not implemented:
- full resume via real unshelve
- formal checkin-based promote flow
- advanced mapping validation and conflict recovery
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_readme.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_readme.py
git commit -m "docs: describe real workspace session lifecycle"
```

### Task 6: Run focused verification for the real-workspace lifecycle slice

**Files:**
- Modify: `src/tfsmcp/runtime.py:16-61`
- Modify: `src/tfsmcp/sessions/manager.py:14-52`
- Modify: `src/tfsmcp/mcp_server.py:6-24`
- Modify: `src/tfsmcp/http_app.py:28-47`
- Modify: `README.md:44-70`
- Test: `tests/sessions/test_runtime_real_session_actions.py`
- Test: `tests/sessions/test_manager.py`
- Test: `tests/test_mcp_tools.py`
- Test: `tests/test_http_app.py`
- Test: `tests/test_readme.py`

- [ ] **Step 1: Run focused verification suite**

Run: `python -m pytest tests/sessions/test_runtime_real_session_actions.py tests/sessions/test_manager.py tests/test_mcp_tools.py tests/test_http_app.py tests/test_readme.py -q`
Expected: PASS with all focused real-workspace lifecycle tests green.

- [ ] **Step 2: Run MCP resume/promote checks**

Run: `python -m pytest tests/test_mcp_tools.py -q -k "resume or promote"`
Expected: PASS

- [ ] **Step 3: Run HTTP resume/promote checks**

Run: `python -m pytest tests/test_http_app.py -q -k "resume or promote"`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/tfsmcp/runtime.py src/tfsmcp/contracts.py src/tfsmcp/sessions/manager.py src/tfsmcp/mcp_server.py src/tfsmcp/http_app.py README.md tests/sessions/test_runtime_real_session_actions.py tests/sessions/test_manager.py tests/test_mcp_tools.py tests/test_http_app.py tests/test_readme.py
git commit -m "feat: add real workspace-backed session lifecycle"
```

## Self-review

### Spec coverage
- Task 1 replaces the placeholder adapter with real workspace/map/get orchestration.
- Task 2 adds resume/promote to the persisted lifecycle.
- Task 3 exposes resume/promote in MCP.
- Task 4 exposes resume/promote in HTTP.
- Task 5 aligns docs with the upgraded real-workspace-backed surface.
- Task 6 verifies the focused slice end to end.

No intentional spec gaps remain for this phase. This plan still stops short of advanced TFS conflict recovery and a true unshelve/checkin promote implementation.

### Placeholder scan
- No TODO/TBD placeholders remain.
- Each task includes concrete files, code snippets, and commands.

### Type consistency
- Session lifecycle names are consistent across manager, MCP, HTTP, tests, and README: `create`, `list`, `suspend`, `discard`, `resume`, `promote`.
- HTTP route names and MCP tool names are consistent with the code snippets.
- Resume/promote signatures stay consistent across layers.
