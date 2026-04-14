import subprocess
from dataclasses import dataclass
from pathlib import Path
from pathlib import PureWindowsPath

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


class RuntimeSessionActions:
    def __init__(self, executor, default_materialize_on_create: bool = False) -> None:
        self._executor = executor
        self._default_materialize_on_create = default_materialize_on_create

    def _run_workspace_create(self, name: str, session_path: str) -> None:
        runner = getattr(self._executor, "_runner", None)
        if runner is None or not hasattr(runner, "_working_directory"):
            self._run_or_raise(["workspace", "/new", name, "/location:server", "/noprompt"])
            return

        Path(session_path).mkdir(parents=True, exist_ok=True)
        original_cwd = getattr(runner, "_working_directory", None)
        runner._working_directory = session_path
        try:
            self._run_or_raise(["workspace", "/new", name, "/location:server", "/noprompt"])
        finally:
            runner._working_directory = original_cwd

    def _run_or_raise(self, args: list[str]):
        result = self._executor.run(args)
        if getattr(result, "exit_code", 1) != 0:
            stderr = (getattr(result, "stderr", "") or "").strip()
            stdout = (getattr(result, "stdout", "") or "").strip()
            details = stderr or stdout or f"TF command failed: {' '.join(args)}"
            raise RuntimeError(details)
        return result

    def create_workspace(
        self,
        name: str,
        source_path: str,
        session_path: str,
        perform_get: bool | None = None,
    ) -> str:
        normalized_source = source_path.replace("\\", "/")
        server_path = (
            normalized_source
            if normalized_source.startswith("$/")
            else "$/"
            + "/".join(
                part.strip("/\\")
                for part in PureWindowsPath(source_path).parts
                if part and not part.endswith(":\\")
            )
        )
        self._run_workspace_create(name, session_path)
        self._run_or_raise(["workfold", "/map", server_path, session_path, f"/workspace:{name}", "/noprompt"])
        materialize = self._default_materialize_on_create if perform_get is None else perform_get
        if materialize:
            self.materialize_workspace(session_path)
        return server_path

    def materialize_workspace(self, session_path: str) -> None:
        # Optional explicit content materialization to avoid long create calls by default.
        self._run_or_raise(["get", session_path, "/recursive", "/noprompt"])

    def create_shelveset(self, workspace_name: str) -> str:
        self._run_or_raise(["shelve", workspace_name, "/noprompt"])
        return workspace_name

    def remove_workspace(self, workspace_name: str) -> None:
        self._run_or_raise(["workspace", "/delete", workspace_name, "/noprompt"])

    def resume_workspace(self, workspace_name: str, session_path: str) -> None:
        _ = workspace_name
        self._run_or_raise(["get", session_path, "/recursive", "/noprompt"])

    def promote_workspace(self, workspace_name: str, comment: str | None) -> str:
        final_comment = comment or workspace_name
        self._run_or_raise(["checkin", f"/comment:{final_comment}", f"/workspace:{workspace_name}", "/noprompt"])
        return final_comment


@dataclass(slots=True)
class Runtime:
    config: object
    detector: object
    onboarding: object
    executor: object
    sessions: object


def run_recovery_script(script_path) -> int:
    command = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
    ]
    # Avoid opening a new console window per script; this prevents popup storms
    # when fallback triggers repeatedly in headless/background usage.
    return subprocess.run(command, check=False).returncode


def build_runtime() -> Runtime:
    config = load_config()
    config.state_dir.mkdir(parents=True, exist_ok=True)
    tf_path = config.tf_path or TfExeLocator().locate()
    runner = TfCommandRunner(
        tf_path,
        timeout_seconds=config.command_timeout_seconds,
        # Do not force cwd to state_dir for tf.exe commands.
        # Using a mapped local folder here can make `tf workspace /new`
        # fail with "path already mapped" against unrelated workspaces.
        working_directory=None,
    )
    classifier = TfOutputClassifier()
    recovery = UnauthorizedRecoveryManager(
        config.tfs_scripts_path,
        run_recovery_script,
        cooldown_seconds=config.recovery_cooldown_seconds,
    )
    executor = RetryingTfsExecutor(runner, classifier, recovery, max_retries=config.max_unauthorized_retries)
    detector = TfsProjectDetector(executor)
    onboarding = TfsProjectOnboardingAdvisor(detector)
    sessions = SessionManager(
        SessionStore(config.state_dir / "sessions.json"),
        actions=RuntimeSessionActions(executor, default_materialize_on_create=config.session_create_auto_get),
    )
    return Runtime(config=config, detector=detector, onboarding=onboarding, executor=executor, sessions=sessions)
