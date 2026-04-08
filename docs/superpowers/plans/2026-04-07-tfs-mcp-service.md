# TFS MCP Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python Windows Service that exposes localhost HTTP and MCP interfaces for TFS workflows, including unauthorized recovery, project detection, onboarding guidance, and hybrid agent sessions.

**Architecture:** Build a `src/tfsmcp` package with a shared application core and two adapters: a localhost HTTP API and an MCP server. All TFS commands flow through a central executor that classifies output, runs every `C:\tfs_scripts\*.ps1` script on unauthorized responses, retries once, and returns structured metadata to HTTP/MCP callers.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, FastMCP, pywin32, pytest, httpx

---

## Scope check

This spec is cohesive enough for one implementation plan because the service host, TFS execution pipeline, HTTP/MCP adapters, and session model all share the same runtime and contract objects. Splitting now would create duplication in the runtime/container work.

## File structure

### Create
- `pyproject.toml` — package metadata and dependencies
- `src/tfsmcp/__init__.py` — package version export
- `src/tfsmcp/config.py` — `ServiceConfig` dataclass and environment loading
- `src/tfsmcp/logging_config.py` — rotating file logging setup
- `src/tfsmcp/contracts.py` — shared dataclasses for command, detection, onboarding, and session responses
- `src/tfsmcp/tfs/__init__.py` — TFS package marker
- `src/tfsmcp/tfs/locator.py` — `TfExeLocator`
- `src/tfsmcp/tfs/runner.py` — `TfCommandRunner`
- `src/tfsmcp/tfs/classifier.py` — `TfOutputClassifier`
- `src/tfsmcp/tfs/recovery.py` — `UnauthorizedRecoveryManager`
- `src/tfsmcp/tfs/executor.py` — `RetryingTfsExecutor`
- `src/tfsmcp/tfs/detector.py` — `TfsProjectDetector`
- `src/tfsmcp/tfs/onboarding.py` — `TfsProjectOnboardingAdvisor`
- `src/tfsmcp/sessions/__init__.py` — sessions package marker
- `src/tfsmcp/sessions/store.py` — JSON-backed `SessionStore`
- `src/tfsmcp/sessions/manager.py` — `SessionManager`
- `src/tfsmcp/runtime.py` — runtime/container assembly and `build_runtime()` for shared dependencies
- `src/tfsmcp/http_app.py` — FastAPI app factory
- `src/tfsmcp/mcp_server.py` — FastMCP server factory and tool handlers
- `src/tfsmcp/console.py` — console-mode startup for local debugging
- `src/tfsmcp/__main__.py` — `python -m tfsmcp` entrypoint
- `src/tfsmcp/service/__init__.py` — service package marker
- `src/tfsmcp/service/windows_service.py` — pywin32 service host
- `src/tfsmcp/service/installer.py` — Python installer/controller using `sc.exe`
- `src/tfsmcp/service/__main__.py` — `python -m tfsmcp.service ...` CLI entrypoint
- `tests/test_config.py` — config and logging tests
- `tests/tfs/test_locator_runner.py` — locator/runner tests
- `tests/tfs/test_executor.py` — classifier/recovery/retry tests
- `tests/tfs/test_detection.py` — project detection and onboarding tests
- `tests/sessions/test_manager.py` — session persistence and lifecycle tests
- `tests/test_runtime.py` — runtime wiring tests
- `tests/test_http_app.py` — HTTP endpoint tests
- `tests/test_mcp_tools.py` — MCP tool handler tests
- `tests/test_console.py` — console startup tests
- `tests/test_main.py` — package entrypoint tests
- `tests/service/test_installer.py` — service installer/controller tests
- `tests/service/test_windows_service.py` — Windows Service host tests
- `tests/service/test_service_main.py` — service CLI entrypoint tests
- `tests/test_readme.py` — README usage assertions

### Modify
- `README.md` — installation, service lifecycle, and developer workflow docs

## Task 1: Bootstrap the package, configuration, and logging

**Files:**
- Create: `pyproject.toml`
- Create: `src/tfsmcp/__init__.py`
- Create: `src/tfsmcp/config.py`
- Create: `src/tfsmcp/logging_config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from tfsmcp.config import load_config
from tfsmcp.logging_config import configure_logging


def test_load_config_uses_defaults(tmp_path):
    config = load_config({"TFSMCP_STATE_DIR": str(tmp_path / "state")})

    assert config.http_host == "127.0.0.1"
    assert config.http_port == 39393
    assert config.tfs_scripts_path == Path("C:/tfs_scripts")
    assert config.state_dir == tmp_path / "state"
    assert config.max_unauthorized_retries == 1


def test_configure_logging_creates_log_file(tmp_path):
    log_file = tmp_path / "service.log"

    logger = configure_logging(log_file)
    logger.info("hello")

    assert log_file.exists()
    assert "hello" in log_file.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'tfsmcp'`

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "tfsmcp"
version = "0.1.0"
description = "Local TFS MCP service"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn>=0.30",
  "fastmcp>=0.1.0",
  "pywin32>=306; platform_system == 'Windows'",
]

[project.optional-dependencies]
dev = ["pytest>=8.3", "httpx>=0.27"]

[tool.pytest.ini_options]
pythonpath = ["src"]
```

```python
# src/tfsmcp/__init__.py
__all__ = ["__version__"]

__version__ = "0.1.0"
```

```python
# src/tfsmcp/config.py
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(slots=True)
class ServiceConfig:
    http_host: str
    http_port: int
    tf_path: str | None
    tfs_scripts_path: Path
    session_base_dir: Path
    state_dir: Path
    command_timeout_seconds: int
    max_unauthorized_retries: int


def load_config(env: Mapping[str, str] | None = None) -> ServiceConfig:
    env = env or {}
    state_dir = Path(env.get("TFSMCP_STATE_DIR", "C:/ProgramData/TfsMcp"))
    return ServiceConfig(
        http_host=env.get("TFSMCP_HTTP_HOST", "127.0.0.1"),
        http_port=int(env.get("TFSMCP_HTTP_PORT", "39393")),
        tf_path=env.get("TFSMCP_TF_PATH") or None,
        tfs_scripts_path=Path(env.get("TFSMCP_SCRIPTS_DIR", "C:/tfs_scripts")),
        session_base_dir=Path(env.get("TFSMCP_SESSION_DIR", "D:/TFS/.tfs-sessions")),
        state_dir=state_dir,
        command_timeout_seconds=int(env.get("TFSMCP_TIMEOUT", "120")),
        max_unauthorized_retries=int(env.get("TFSMCP_MAX_RETRIES", "1")),
    )
```

```python
# src/tfsmcp/logging_config.py
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_file: Path) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("tfsmcp")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -q`
Expected: PASS with `2 passed`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/tfsmcp/__init__.py src/tfsmcp/config.py src/tfsmcp/logging_config.py tests/test_config.py
git commit -m "feat: bootstrap tfsmcp package"
```

### Task 2: Add `tf.exe` discovery, command execution, and shared command contracts

**Files:**
- Create: `src/tfsmcp/contracts.py`
- Create: `src/tfsmcp/tfs/__init__.py`
- Create: `src/tfsmcp/tfs/locator.py`
- Create: `src/tfsmcp/tfs/runner.py`
- Test: `tests/tfs/test_locator_runner.py`

- [ ] **Step 1: Write the failing tests**

```python
import subprocess
from pathlib import Path

from tfsmcp.tfs.locator import TfExeLocator
from tfsmcp.tfs.runner import TfCommandRunner


class Completed:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_locator_uses_vswhere_output(monkeypatch):
    monkeypatch.setattr("tfsmcp.tfs.locator.Path.exists", lambda self: True)
    monkeypatch.setattr(
        "tfsmcp.tfs.locator.subprocess.run",
        lambda *args, **kwargs: Completed(stdout="C:/VS\n"),
    )

    locator = TfExeLocator()

    assert locator.locate().endswith("tf.exe")


def test_runner_returns_structured_result(monkeypatch):
    monkeypatch.setattr(
        "tfsmcp.tfs.runner.subprocess.run",
        lambda *args, **kwargs: Completed(stdout="ok", stderr="", returncode=0),
    )

    runner = TfCommandRunner("tf", timeout_seconds=5)
    result = runner.run(["status", "D:/TFS/SPF"])

    assert result.command == ["tf", "status", "D:/TFS/SPF"]
    assert result.exit_code == 0
    assert result.stdout == "ok"
    assert result.stderr == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tfs/test_locator_runner.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'tfsmcp.tfs'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/tfsmcp/contracts.py
from dataclasses import dataclass, field


@dataclass(slots=True)
class CommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    category: str = "unknown"
    recovery_triggered: bool = False
    retried: bool = False
    recovery_scripts: list[str] = field(default_factory=list)
```

```python
# src/tfsmcp/tfs/__init__.py
__all__ = ["locator", "runner"]
```

```python
# src/tfsmcp/tfs/locator.py
import os
import subprocess
from pathlib import Path


class TfExeLocator:
    def locate(self) -> str:
        vswhere = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
        if vswhere.exists():
            result = subprocess.run(
                [str(vswhere), "-latest", "-property", "installationPath"],
                capture_output=True,
                text=True,
                check=False,
            )
            installation_path = result.stdout.strip()
            if installation_path:
                tf_path = Path(installation_path) / "Common7/IDE/CommonExtensions/Microsoft/TeamFoundation/Team Explorer/tf.exe"
                return str(tf_path)
        return "tf"
```

```python
# src/tfsmcp/tfs/runner.py
import subprocess
from collections.abc import Sequence

from tfsmcp.contracts import CommandResult


class TfCommandRunner:
    def __init__(self, tf_path: str, timeout_seconds: int) -> None:
        self._tf_path = tf_path
        self._timeout_seconds = timeout_seconds

    def run(self, args: Sequence[str]) -> CommandResult:
        command = [self._tf_path, *args]
        result = subprocess.run(command, capture_output=True, text=True, timeout=self._timeout_seconds, check=False)
        return CommandResult(
            command=command,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            category="raw",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tfs/test_locator_runner.py -q`
Expected: PASS with `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/tfsmcp/contracts.py src/tfsmcp/tfs/__init__.py src/tfsmcp/tfs/locator.py src/tfsmcp/tfs/runner.py tests/tfs/test_locator_runner.py
git commit -m "feat: add tf.exe discovery and runner"
```

### Task 3: Classify TFS output and add unauthorized recovery with a single retry

**Files:**
- Create: `src/tfsmcp/tfs/classifier.py`
- Create: `src/tfsmcp/tfs/recovery.py`
- Create: `src/tfsmcp/tfs/executor.py`
- Test: `tests/tfs/test_executor.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from tfsmcp.contracts import CommandResult
from tfsmcp.tfs.classifier import TfOutputClassifier
from tfsmcp.tfs.executor import RetryingTfsExecutor
from tfsmcp.tfs.recovery import UnauthorizedRecoveryManager


class FakeRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, args):
        self.calls += 1
        if self.calls == 1:
            return CommandResult(command=["tf", *args], exit_code=1, stdout="", stderr="Access is denied", category="raw")
        return CommandResult(command=["tf", *args], exit_code=0, stdout="checked out", stderr="", category="raw")


def test_classifier_marks_unauthorized_result():
    classifier = TfOutputClassifier()
    result = CommandResult(command=["tf"], exit_code=1, stdout="", stderr="Unauthorized access", category="raw")

    assert classifier.classify(result) == "unauthorized"


def test_executor_runs_all_scripts_and_retries_once(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "01-login.ps1").write_text("Write-Host one", encoding="utf-8")
    (scripts_dir / "02-context.ps1").write_text("Write-Host two", encoding="utf-8")

    executed = []
    recovery = UnauthorizedRecoveryManager(scripts_dir, lambda script: executed.append(script.name) or 0)
    executor = RetryingTfsExecutor(FakeRunner(), TfOutputClassifier(), recovery, max_retries=1)

    result = executor.run(["checkout", "D:/TFS/SPF/file.cs"])

    assert result.exit_code == 0
    assert result.recovery_triggered is True
    assert result.retried is True
    assert result.recovery_scripts == ["01-login.ps1", "02-context.ps1"]
    assert executed == ["01-login.ps1", "02-context.ps1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tfs/test_executor.py -q`
Expected: FAIL with `ModuleNotFoundError` for `tfsmcp.tfs.classifier`

- [ ] **Step 3: Write minimal implementation**

```python
# src/tfsmcp/tfs/classifier.py
from tfsmcp.contracts import CommandResult


class TfOutputClassifier:
    def classify(self, result: CommandResult) -> str:
        text = f"{result.stdout}\n{result.stderr}".lower()
        if result.exit_code == 0:
            return "success"
        if "unauthorized" in text or "access is denied" in text or "not authorized" in text:
            return "unauthorized"
        if "workspace" in text:
            return "workspace_error"
        if "mapping" in text:
            return "mapping_error"
        return "unknown_failure"
```

```python
# src/tfsmcp/tfs/recovery.py
from collections.abc import Callable
from pathlib import Path


class UnauthorizedRecoveryManager:
    def __init__(self, scripts_dir: Path, run_script: Callable[[Path], int]) -> None:
        self._scripts_dir = scripts_dir
        self._run_script = run_script

    def run_scripts(self) -> list[str]:
        executed: list[str] = []
        for script in sorted(self._scripts_dir.glob("*.ps1")):
            self._run_script(script)
            executed.append(script.name)
        return executed
```

```python
# src/tfsmcp/tfs/executor.py
from collections.abc import Sequence

from tfsmcp.contracts import CommandResult


class RetryingTfsExecutor:
    def __init__(self, runner, classifier, recovery_manager, max_retries: int) -> None:
        self._runner = runner
        self._classifier = classifier
        self._recovery_manager = recovery_manager
        self._max_retries = max_retries

    def run(self, args: Sequence[str]) -> CommandResult:
        result = self._runner.run(args)
        result.category = self._classifier.classify(result)
        if result.category != "unauthorized" or self._max_retries < 1:
            return result

        scripts = self._recovery_manager.run_scripts()
        retried = self._runner.run(args)
        retried.category = self._classifier.classify(retried)
        retried.recovery_triggered = True
        retried.retried = True
        retried.recovery_scripts = scripts
        return retried
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tfs/test_executor.py -q`
Expected: PASS with `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/tfsmcp/tfs/classifier.py src/tfsmcp/tfs/recovery.py src/tfsmcp/tfs/executor.py tests/tfs/test_executor.py
git commit -m "feat: add unauthorized recovery executor"
```

### Task 4: Detect TFS projects and build onboarding guidance

**Files:**
- Modify: `src/tfsmcp/contracts.py`
- Create: `src/tfsmcp/tfs/detector.py`
- Create: `src/tfsmcp/tfs/onboarding.py`
- Test: `tests/tfs/test_detection.py`

- [ ] **Step 1: Write the failing tests**

```python
from tfsmcp.contracts import CommandResult
from tfsmcp.tfs.detector import TfsProjectDetector
from tfsmcp.tfs.onboarding import TfsProjectOnboardingAdvisor


class FakeExecutor:
    def run(self, args):
        return CommandResult(
            command=["tf", *args],
            exit_code=0,
            stdout="Workspace: SPF_Joao\nServer path: $/SPF/Main\nLocal path: D:/TFS/SPF",
            stderr="",
            category="success",
        )


def test_detector_returns_high_confidence_mapping():
    detector = TfsProjectDetector(FakeExecutor())
    result = detector.detect("D:/TFS/SPF")

    assert result.kind == "tfs_mapped"
    assert result.confidence == "high"
    assert result.workspace_name == "SPF_Joao"
    assert result.server_path == "$/SPF/Main"
    assert result.is_agent_ready is True


def test_onboarding_recommends_session_workflow():
    advisor = TfsProjectOnboardingAdvisor(TfsProjectDetector(FakeExecutor()))
    result = advisor.build("D:/TFS/SPF")

    assert result.recommended_workflow["beforeEdit"] == "checkout"
    assert result.recommended_workflow["forParallelTask"] == "session_create"
    assert result.supports["unauthorizedRecovery"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tfs/test_detection.py -q`
Expected: FAIL with `ImportError` for `TfsProjectDetector`

- [ ] **Step 3: Write minimal implementation**

```python
# src/tfsmcp/contracts.py
from dataclasses import dataclass, field


@dataclass(slots=True)
class CommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    category: str = "unknown"
    recovery_triggered: bool = False
    retried: bool = False
    recovery_scripts: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProjectDetection:
    kind: str
    confidence: str
    workspace_name: str | None
    server_path: str | None
    local_path: str
    is_agent_ready: bool


@dataclass(slots=True)
class OnboardingAdvice:
    project_kind: str
    confidence: str
    workspace: dict[str, str | None]
    recommended_workflow: dict[str, str]
    supports: dict[str, bool]
    notes: list[str]
```

```python
# src/tfsmcp/tfs/detector.py
from tfsmcp.contracts import ProjectDetection


class TfsProjectDetector:
    def __init__(self, executor) -> None:
        self._executor = executor

    def detect(self, path: str) -> ProjectDetection:
        result = self._executor.run(["workfold", path])
        if result.exit_code != 0 or "$/" not in result.stdout:
            return ProjectDetection("not_tfs", "high", None, None, path, False)

        values = {}
        for line in result.stdout.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                values[key.strip().lower()] = value.strip()

        return ProjectDetection(
            kind="tfs_mapped",
            confidence="high",
            workspace_name=values.get("workspace"),
            server_path=values.get("server path"),
            local_path=values.get("local path", path),
            is_agent_ready=True,
        )
```

```python
# src/tfsmcp/tfs/onboarding.py
from tfsmcp.contracts import OnboardingAdvice


class TfsProjectOnboardingAdvisor:
    def __init__(self, detector) -> None:
        self._detector = detector

    def build(self, path: str) -> OnboardingAdvice:
        detection = self._detector.detect(path)
        return OnboardingAdvice(
            project_kind=detection.kind,
            confidence=detection.confidence,
            workspace={
                "name": detection.workspace_name,
                "serverPath": detection.server_path,
                "localPath": detection.local_path,
            },
            recommended_workflow={
                "beforeEdit": "checkout",
                "forParallelTask": "session_create",
                "forCheckpoint": "shelve",
                "forDiscard": "undo_or_session_discard",
            },
            supports={
                "basicTools": detection.kind == "tfs_mapped",
                "hybridSessions": detection.kind == "tfs_mapped",
                "unauthorizedRecovery": True,
            },
            notes=[
                "Always checkout before editing controlled files.",
                "If unauthorized occurs, recovery scripts are executed automatically.",
                "Use hybrid sessions for agent isolation.",
            ],
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tfs/test_detection.py -q`
Expected: PASS with `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/tfsmcp/contracts.py src/tfsmcp/tfs/detector.py src/tfsmcp/tfs/onboarding.py tests/tfs/test_detection.py
git commit -m "feat: add project detection and onboarding"
```

### Task 5: Persist and manage hybrid sessions

**Files:**
- Modify: `src/tfsmcp/contracts.py`
- Create: `src/tfsmcp/sessions/__init__.py`
- Create: `src/tfsmcp/sessions/store.py`
- Create: `src/tfsmcp/sessions/manager.py`
- Test: `tests/sessions/test_manager.py`
- Test: `tests/test_runtime.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from tfsmcp.runtime import build_runtime
from tfsmcp.sessions.manager import SessionManager
from tfsmcp.sessions.store import SessionStore


class FakeWorkspaceActions:
    def __init__(self) -> None:
        self.created = []
        self.shelvesets = []
        self.removed = []

    def create_workspace(self, name: str, source_path: str, session_path: str) -> str:
        self.created.append((name, source_path, session_path))
        return "$/SPF/Main"

    def create_shelveset(self, name: str) -> str:
        shelveset = f"{name}-checkpoint"
        self.shelvesets.append(shelveset)
        return shelveset

    def remove_workspace(self, name: str) -> None:
        self.removed.append(name)


class FakeRuntimeConfig:
    def __init__(self, tmp_path: Path):
        self.http_host = "127.0.0.1"
        self.http_port = 39393
        self.tf_path = "tf"
        self.command_timeout_seconds = 5
        self.max_unauthorized_retries = 1
        self.tfs_scripts_path = tmp_path / "scripts"
        self.state_dir = tmp_path / "state"
        self.tfs_scripts_path.mkdir()


class FakeLocator:
    def locate(self) -> str:
        return "tf"


class FakeRunnerForRuntime:
    def __init__(self, tf_path: str, timeout_seconds: int) -> None:
        self.tf_path = tf_path
        self.timeout_seconds = timeout_seconds

    def run(self, args):
        raise AssertionError("runtime wiring test should not execute tf commands")


class FakeOnboardingAdvisor:
    def __init__(self, detector) -> None:
        self.detector = detector

    def build(self, path: str):
        return {"projectKind": "tfs_mapped", "path": path}


def test_build_runtime_wires_dependencies(tmp_path, monkeypatch):
    monkeypatch.setattr("tfsmcp.runtime.load_config", lambda: FakeRuntimeConfig(tmp_path))
    monkeypatch.setattr("tfsmcp.runtime.TfExeLocator", lambda: FakeLocator())
    monkeypatch.setattr("tfsmcp.runtime.TfCommandRunner", FakeRunnerForRuntime)
    monkeypatch.setattr("tfsmcp.runtime.UnauthorizedRecoveryManager", lambda scripts_dir, run_script: object())
    monkeypatch.setattr("tfsmcp.runtime.SessionManager", lambda store, actions: {"store": store, "actions": actions})
    monkeypatch.setattr("tfsmcp.runtime.TfsProjectOnboardingAdvisor", FakeOnboardingAdvisor)

    runtime = build_runtime()

    assert runtime.config.http_host == "127.0.0.1"
    assert runtime.executor._runner.tf_path == "tf"
    assert runtime.onboarding.detector is runtime.detector
    assert runtime.sessions["store"]._path.name == "sessions.json"
    assert runtime.sessions["actions"] is None


def test_session_create_persists_workspace_session(tmp_path):
    store = SessionStore(tmp_path / "sessions.json")
    actions = FakeWorkspaceActions()
    manager = SessionManager(store, actions)

    record = manager.create("agent-auth", "D:/TFS/SPF", tmp_path / "agent-auth")

    assert record.name == "agent-auth"
    assert record.server_path == "$/SPF/Main"
    assert store.load_all()[0].workspace_name == "agent-auth"


def test_session_suspend_and_discard_update_state(tmp_path):
    store = SessionStore(tmp_path / "sessions.json")
    actions = FakeWorkspaceActions()
    manager = SessionManager(store, actions)
    manager.create("agent-auth", "D:/TFS/SPF", tmp_path / "agent-auth")

    suspended = manager.suspend("agent-auth")
    discarded = manager.discard("agent-auth")

    assert suspended.status == "suspended"
    assert suspended.last_shelveset == "agent-auth-checkpoint"
    assert discarded.status == "discarded"
    assert actions.removed == ["agent-auth"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/sessions/test_manager.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'tfsmcp.sessions'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/tfsmcp/contracts.py
from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class CommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    category: str = "unknown"
    recovery_triggered: bool = False
    retried: bool = False
    recovery_scripts: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProjectDetection:
    kind: str
    confidence: str
    workspace_name: str | None
    server_path: str | None
    local_path: str
    is_agent_ready: bool


@dataclass(slots=True)
class OnboardingAdvice:
    project_kind: str
    confidence: str
    workspace: dict[str, str | None]
    recommended_workflow: dict[str, str]
    supports: dict[str, bool]
    notes: list[str]


@dataclass(slots=True)
class SessionRecord:
    name: str
    project_path: str
    session_path: str
    server_path: str
    workspace_name: str
    mode: str
    status: str
    last_shelveset: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
```

```python
# src/tfsmcp/sessions/__init__.py
__all__ = ["manager", "store"]
```

```python
# src/tfsmcp/sessions/store.py
import json
from pathlib import Path

from tfsmcp.contracts import SessionRecord


class SessionStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load_all(self) -> list[SessionRecord]:
        if not self._path.exists():
            return []
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        return [SessionRecord(**item) for item in payload]

    def save_all(self, records: list[SessionRecord]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps([record.to_dict() for record in records], indent=2), encoding="utf-8")
```

```python
# src/tfsmcp/sessions/manager.py
from pathlib import Path

from tfsmcp.contracts import SessionRecord


class SessionManager:
    def __init__(self, store, actions) -> None:
        self._store = store
        self._actions = actions

    def list_records(self) -> list[SessionRecord]:
        return self._store.load_all()

    def create(self, name: str, source_path: str, session_path: Path) -> SessionRecord:
        server_path = self._actions.create_workspace(name, source_path, str(session_path))
        record = SessionRecord(name, source_path, str(session_path), server_path, name, "hybrid", "active")
        records = self._store.load_all()
        records.append(record)
        self._store.save_all(records)
        return record

    def suspend(self, name: str) -> SessionRecord:
        records = self._store.load_all()
        for record in records:
            if record.name == name:
                record.status = "suspended"
                record.last_shelveset = self._actions.create_shelveset(name)
                self._store.save_all(records)
                return record
        raise KeyError(name)

    def discard(self, name: str) -> SessionRecord:
        records = self._store.load_all()
        for record in records:
            if record.name == name:
                self._actions.remove_workspace(name)
                record.status = "discarded"
                self._store.save_all(records)
                return record
        raise KeyError(name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/sessions/test_manager.py -q`
Expected: PASS with `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/tfsmcp/contracts.py src/tfsmcp/sessions/__init__.py src/tfsmcp/sessions/store.py src/tfsmcp/sessions/manager.py tests/sessions/test_manager.py
git commit -m "feat: add hybrid session persistence"
```

### Task 6: Build the shared runtime and localhost HTTP API

**Files:**
- Create: `src/tfsmcp/runtime.py`
- Create: `src/tfsmcp/http_app.py`
- Test: `tests/test_http_app.py`

- [ ] **Step 1: Write the failing tests**

```python
from fastapi.testclient import TestClient

from tfsmcp.http_app import build_http_app
from tfsmcp.runtime import Runtime, build_runtime


class FakeDetector:
    def detect(self, path: str):
        return {
            "kind": "tfs_mapped",
            "confidence": "high",
            "workspaceName": "SPF_Joao",
            "serverPath": "$/SPF/Main",
            "localPath": path,
            "isAgentReady": True,
        }


class FakeOnboarding:
    def build(self, path: str):
        return {"projectKind": "tfs_mapped", "path": path}


class FakeExecutor:
    def run(self, args):
        return {"ok": True, "command": args, "meta": {"recoveryTriggered": False, "retried": False}}


class FakeSessions:
    def list_records(self):
        return []


def test_health_endpoint_reports_ok():
    runtime = Runtime(config=None, detector=FakeDetector(), onboarding=FakeOnboarding(), executor=FakeExecutor(), sessions=FakeSessions())
    client = TestClient(build_http_app(runtime))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_checkout_endpoint_returns_executor_payload():
    runtime = Runtime(config=None, detector=FakeDetector(), onboarding=FakeOnboarding(), executor=FakeExecutor(), sessions=FakeSessions())
    client = TestClient(build_http_app(runtime))

    response = client.post("/checkout", json={"path": "D:/TFS/SPF/file.cs"})

    assert response.status_code == 200
    assert response.json()["data"]["command"] == ["checkout", "D:/TFS/SPF/file.cs"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_http_app.py -q`
Expected: FAIL with `ModuleNotFoundError` for `tfsmcp.http_app`

- [ ] **Step 3: Write minimal implementation**

```python
# src/tfsmcp/runtime.py
from dataclasses import dataclass

from tfsmcp.config import load_config
from tfsmcp.sessions.manager import SessionManager
from tfsmcp.sessions.store import SessionStore
from tfsmcp.tfs.classifier import TfOutputClassifier
from tfsmcp.tfs.detector import TfsProjectDetector
from tfsmcp.tfs.executor import RetryingTfsExecutor
from tfsmcp.tfs.locator import TfExeLocator
from tfsmcp.tfs.onboarding import TfsProjectOnboardingAdvisor
from tfsmcp.tfs.recovery import UnauthorizedRecoveryManager
from tfsmcp.tfs.runner import TfCommandRunner


@dataclass(slots=True)
class Runtime:
    config: object
    detector: object
    onboarding: object
    executor: object
    sessions: object


def build_runtime() -> Runtime:
    config = load_config()
    tf_path = config.tf_path or TfExeLocator().locate()
    runner = TfCommandRunner(tf_path, timeout_seconds=config.command_timeout_seconds)
    classifier = TfOutputClassifier()
    recovery = UnauthorizedRecoveryManager(config.tfs_scripts_path, lambda script: 0)
    executor = RetryingTfsExecutor(runner, classifier, recovery, max_retries=config.max_unauthorized_retries)
    detector = TfsProjectDetector(executor)
    onboarding = TfsProjectOnboardingAdvisor(detector)
    sessions = SessionManager(SessionStore(config.state_dir / "sessions.json"), actions=None)
    return Runtime(config=config, detector=detector, onboarding=onboarding, executor=executor, sessions=sessions)
```

```python
# src/tfsmcp/http_app.py
from fastapi import FastAPI

from tfsmcp.runtime import Runtime


def build_http_app(runtime: Runtime) -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/projects/detect")
    def detect(path: str):
        return {"ok": True, "data": runtime.detector.detect(path), "error": None, "meta": {}}

    @app.get("/projects/onboard")
    def onboard(path: str):
        return {"ok": True, "data": runtime.onboarding.build(path), "error": None, "meta": {}}

    @app.post("/checkout")
    def checkout(payload: dict[str, str]):
        result = runtime.executor.run(["checkout", payload["path"]])
        return {"ok": True, "data": result, "error": None, "meta": result.get("meta", {})}

    @app.get("/sessions")
    def sessions():
        return {"ok": True, "data": runtime.sessions.list_records(), "error": None, "meta": {}}

    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_http_app.py -q`
Expected: PASS with `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/tfsmcp/runtime.py src/tfsmcp/http_app.py tests/test_runtime.py tests/test_http_app.py
git commit -m "feat: add localhost http api"
```

### Task 7: Expose the same runtime through MCP tools and a console entrypoint

**Files:**
- Create: `src/tfsmcp/mcp_server.py`
- Create: `src/tfsmcp/console.py`
- Create: `src/tfsmcp/__main__.py`
- Test: `tests/test_mcp_tools.py`
- Test: `tests/test_console.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing tests**

```python
from tfsmcp.mcp_server import build_tool_handlers
from tfsmcp.runtime import Runtime


class FakeDetector:
    def detect(self, path: str):
        return {"kind": "tfs_mapped", "localPath": path}


class FakeOnboarding:
    def build(self, path: str):
        return {"projectKind": "tfs_mapped", "localPath": path}


class FakeExecutor:
    def run(self, args):
        return {"command": args, "meta": {"recoveryTriggered": False, "retried": False}}


class FakeSessions:
    def create(self, name: str, source_path: str, session_path: str):
        return {"name": name, "sourcePath": source_path, "sessionPath": session_path}

    def list_records(self):
        return []


def test_handlers_delegate_to_runtime_dependencies():
    runtime = Runtime(config=None, detector=FakeDetector(), onboarding=FakeOnboarding(), executor=FakeExecutor(), sessions=FakeSessions())
    handlers = build_tool_handlers(runtime)

    assert handlers["tfs_detect_project"]("D:/TFS/SPF")["kind"] == "tfs_mapped"
    assert handlers["tfs_checkout"]("D:/TFS/SPF/file.cs")["command"] == ["checkout", "D:/TFS/SPF/file.cs"]
    assert handlers["tfs_session_list"]() == []
```

```python
from tfsmcp.console import run_console, start_http_server
from tfsmcp.runtime import Runtime


class FakeConfig:
    http_host = "127.0.0.1"
    http_port = 39393


class FakeServer:
    def __init__(self):
        self.ran = False

    def run(self):
        self.ran = True


def test_start_http_server_uses_runtime_config(monkeypatch):
    captured = {}

    class FakeConfigObject:
        def __init__(self, app, host: str, port: int):
            captured["host"] = host
            captured["port"] = port
            self.app = app

    monkeypatch.setattr("tfsmcp.console.uvicorn.Config", FakeConfigObject)
    monkeypatch.setattr("tfsmcp.console.uvicorn.Server", lambda config: {"config": config})

    runtime = Runtime(config=FakeConfig(), detector=None, onboarding=None, executor=None, sessions=None)
    server = start_http_server(runtime)

    assert captured == {"host": "127.0.0.1", "port": 39393}
    assert "config" in server


def test_run_console_builds_runtime_and_runs_server(monkeypatch):
    fake_server = FakeServer()
    monkeypatch.setattr("tfsmcp.console.build_runtime", lambda: Runtime(config=FakeConfig(), detector=None, onboarding=None, executor=None, sessions=None))
    monkeypatch.setattr("tfsmcp.console.start_http_server", lambda runtime: fake_server)

    run_console()

    assert fake_server.ran is True
```

```python
import runpy


def test_package_main_calls_run_console(monkeypatch):
    called = []
    monkeypatch.setattr("tfsmcp.console.run_console", lambda: called.append("ran"))

    runpy.run_module("tfsmcp", run_name="__main__")

    assert called == ["ran"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_mcp_tools.py tests/test_console.py tests/test_main.py -q`
Expected: FAIL with `ModuleNotFoundError` for `tfsmcp.mcp_server`

- [ ] **Step 3: Write minimal implementation**

```python
# src/tfsmcp/mcp_server.py
from mcp.server.fastmcp import FastMCP

from tfsmcp.runtime import Runtime


def build_tool_handlers(runtime: Runtime) -> dict[str, object]:
    return {
        "tfs_detect_project": lambda path: runtime.detector.detect(path),
        "tfs_onboard_project": lambda path: runtime.onboarding.build(path),
        "tfs_checkout": lambda filepath: runtime.executor.run(["checkout", filepath]),
        "tfs_undo": lambda filepath: runtime.executor.run(["undo", filepath]),
        "tfs_session_list": lambda: runtime.sessions.list_records(),
    }


def build_mcp_server(runtime: Runtime) -> FastMCP:
    server = FastMCP("TFS_Tools")
    handlers = build_tool_handlers(runtime)
    for name, handler in handlers.items():
        server.tool(name=name)(handler)
    return server
```

```python
# src/tfsmcp/console.py
import uvicorn

from tfsmcp.http_app import build_http_app
from tfsmcp.runtime import build_runtime


def start_http_server(runtime):
    config = uvicorn.Config(build_http_app(runtime), host=runtime.config.http_host, port=runtime.config.http_port)
    return uvicorn.Server(config)


def run_console() -> None:
    runtime = build_runtime()
    start_http_server(runtime).run()
```

```python
# src/tfsmcp/__main__.py
from tfsmcp.console import run_console


if __name__ == "__main__":
    run_console()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_mcp_tools.py tests/test_console.py tests/test_main.py -q`
Expected: PASS with `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/tfsmcp/mcp_server.py src/tfsmcp/console.py src/tfsmcp/__main__.py tests/test_mcp_tools.py tests/test_console.py tests/test_main.py
git commit -m "feat: expose mcp tool handlers"
```

### Task 8: Add Windows Service hosting and a Python installer/controller module

**Files:**
- Create: `src/tfsmcp/service/__init__.py`
- Create: `src/tfsmcp/service/windows_service.py`
- Create: `src/tfsmcp/service/installer.py`
- Create: `src/tfsmcp/service/__main__.py`
- Test: `tests/service/test_installer.py`
- Test: `tests/service/test_windows_service.py`
- Test: `tests/service/test_service_main.py`

- [ ] **Step 1: Write the failing tests**

```python
from tfsmcp.service.installer import ServiceInstaller


class FakeRunner:
    def __init__(self) -> None:
        self.commands = []

    def __call__(self, command):
        self.commands.append(command)
        return 0


def test_installer_builds_sc_commands_for_install_and_start():
    runner = FakeRunner()
    installer = ServiceInstaller(runner, service_name="TfsMcpService", display_name="TFS MCP Service")

    installer.install("python", "-m tfsmcp.service run")
    installer.start()

    assert runner.commands[0][:4] == ["sc", "create", "TfsMcpService", "binPath="]
    assert runner.commands[1] == ["sc", "start", "TfsMcpService"]
```

```python
from tfsmcp.service.windows_service import TfsMcpWindowsService


class FakeServer:
    def __init__(self):
        self.should_exit = False
        self.ran = False

    def run(self):
        self.ran = True


def test_windows_service_runs_http_server(monkeypatch):
    service = object.__new__(TfsMcpWindowsService)
    service.server = None
    service.ReportServiceStatus = lambda status: None
    service.stop_event = object()
    fake_server = FakeServer()

    monkeypatch.setattr("tfsmcp.service.windows_service.servicemanager.LogInfoMsg", lambda msg: None)
    monkeypatch.setattr("tfsmcp.service.windows_service.build_runtime", lambda: object())
    monkeypatch.setattr("tfsmcp.service.windows_service.start_http_server", lambda runtime: fake_server)

    service.SvcDoRun()

    assert service.server is fake_server
    assert fake_server.ran is True


def test_windows_service_stop_sets_should_exit(monkeypatch):
    service = object.__new__(TfsMcpWindowsService)
    service.server = FakeServer()
    reported = []
    service.ReportServiceStatus = lambda status: reported.append(status)

    monkeypatch.setattr("tfsmcp.service.windows_service.win32event.SetEvent", lambda event: None)
    monkeypatch.setattr("tfsmcp.service.windows_service.win32service.SERVICE_STOP_PENDING", 3)
    service.stop_event = object()

    service.SvcStop()

    assert reported == [3]
    assert service.server.should_exit is True
```

```python
from tfsmcp.service.__main__ import main


class FakeInstaller:
    def __init__(self):
        self.calls = []

    def install(self, executable: str, arguments: str) -> int:
        self.calls.append(("install", executable, arguments))
        return 0

    def uninstall(self) -> int:
        self.calls.append(("uninstall",))
        return 0

    def start(self) -> int:
        self.calls.append(("start",))
        return 0

    def stop(self) -> int:
        self.calls.append(("stop",))
        return 0

    def restart(self) -> int:
        self.calls.append(("restart",))
        return 0

    def status(self) -> int:
        self.calls.append(("status",))
        return 0


def test_service_main_dispatches_install(monkeypatch):
    fake = FakeInstaller()
    monkeypatch.setattr("tfsmcp.service.__main__.ServiceInstaller", lambda *args: fake)

    code = main(["install"])

    assert code == 0
    assert fake.calls == [("install", "python", "-m tfsmcp.service run")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/service/test_installer.py tests/service/test_windows_service.py tests/service/test_service_main.py -q`
Expected: FAIL with `ModuleNotFoundError` for `tfsmcp.service.installer`

- [ ] **Step 3: Write minimal implementation**

```python
# src/tfsmcp/service/__init__.py
__all__ = ["installer", "windows_service"]
```

```python
# src/tfsmcp/service/windows_service.py
import servicemanager
import win32event
import win32service
import win32serviceutil

from tfsmcp.console import build_runtime, start_http_server


class TfsMcpWindowsService(win32serviceutil.ServiceFramework):
    _svc_name_ = "TfsMcpService"
    _svc_display_name_ = "TFS MCP Service"

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.server = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.server is not None:
            self.server.should_exit = True
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("Starting TfsMcpService")
        runtime = build_runtime()
        self.server = start_http_server(runtime)
        self.server.run()
```

```python
# src/tfsmcp/service/installer.py
import subprocess


class ServiceInstaller:
    def __init__(self, run_command, service_name: str, display_name: str) -> None:
        self._run_command = run_command
        self._service_name = service_name
        self._display_name = display_name

    def install(self, executable: str, arguments: str) -> int:
        return self._run_command([
            "sc",
            "create",
            self._service_name,
            "binPath=",
            f'{executable} {arguments}',
            "DisplayName=",
            self._display_name,
            "start=",
            "auto",
        ])

    def uninstall(self) -> int:
        return self._run_command(["sc", "delete", self._service_name])

    def start(self) -> int:
        return self._run_command(["sc", "start", self._service_name])

    def stop(self) -> int:
        return self._run_command(["sc", "stop", self._service_name])

    def restart(self) -> int:
        self.stop()
        return self.start()

    def status(self) -> int:
        return self._run_command(["sc", "query", self._service_name])


def default_runner(command: list[str]) -> int:
    return subprocess.run(command, check=False).returncode
```

```python
# src/tfsmcp/service/__main__.py
import sys

from tfsmcp.service.installer import ServiceInstaller, default_runner
from tfsmcp.service.windows_service import TfsMcpWindowsService


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    installer = ServiceInstaller(default_runner, "TfsMcpService", "TFS MCP Service")
    if argv == ["install"]:
        return installer.install("python", "-m tfsmcp.service run")
    if argv == ["uninstall"]:
        return installer.uninstall()
    if argv == ["start"]:
        return installer.start()
    if argv == ["stop"]:
        return installer.stop()
    if argv == ["restart"]:
        return installer.restart()
    if argv == ["status"]:
        return installer.status()
    if argv == ["run"]:
        TfsMcpWindowsService.HandleCommandLine()
        return 0
    raise SystemExit("usage: python -m tfsmcp.service [install|uninstall|start|stop|restart|status|run]")


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/service/test_installer.py tests/service/test_windows_service.py tests/service/test_service_main.py -q`
Expected: PASS with `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/tfsmcp/service/__init__.py src/tfsmcp/service/windows_service.py src/tfsmcp/service/installer.py src/tfsmcp/service/__main__.py tests/service/test_installer.py tests/service/test_windows_service.py tests/service/test_service_main.py
git commit -m "feat: add windows service installer"
```

### Task 9: Document service installation and developer workflows

**Files:**
- Modify: `README.md`
- Test: `tests/test_readme.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_readme_mentions_service_install_and_recovery_scripts():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "python -m tfsmcp.service install" in readme
    assert "C:\\tfs_scripts" in readme
    assert "tfs_session_create" in readme
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_readme.py -q`
Expected: FAIL with `AssertionError` because README is still empty/minimal

- [ ] **Step 3: Write minimal documentation**

```md
# TfsMcp

Local TFS MCP service for Windows development machines.

## Install dependencies

```bash
pip install -e .[dev]
```

## Run tests

```bash
python -m pytest -q
```

## Install the Windows Service

```bash
python -m tfsmcp.service install
python -m tfsmcp.service start
python -m tfsmcp.service status
```

## Remove the Windows Service

```bash
python -m tfsmcp.service stop
python -m tfsmcp.service uninstall
```

## Unauthorized recovery

If a TFS command returns an unauthorized error, the service runs every `*.ps1` script inside `C:\tfs_scripts` in alphabetical order and retries the original command once.

## Agent workflow

1. Detect the project with `tfs_detect_project`.
2. Get guidance with `tfs_onboard_project`.
3. Create isolated work with `tfs_session_create`.
4. Checkout files before editing.
5. Use shelvesets for checkpoints.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_readme.py -q`
Expected: PASS with `1 passed`

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_readme.py
git commit -m "docs: add service usage guide"
```

## Final verification

- [ ] Run: `python -m pytest -q`
Expected: PASS with all tests green.

- [ ] Run: `python -m pytest tests/tfs/test_executor.py -q`
Expected: PASS and confirm the unauthorized retry path still works after all wiring changes.

- [ ] Run: `python -m pytest tests/service/test_installer.py -q`
Expected: PASS and confirm the service CLI surface still matches the README examples.
