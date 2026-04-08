import subprocess
from dataclasses import dataclass
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
    def __init__(self, executor) -> None:
        self._executor = executor

    def create_workspace(self, name: str, source_path: str, session_path: str) -> str:
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
        self._executor.run(["workspace", "/new", name])
        self._executor.run(["workfold", "/map", server_path, session_path, f"/workspace:{name}"])
        self._executor.run(["get", session_path, "/recursive"])
        return server_path

    def create_shelveset(self, workspace_name: str) -> str:
        self._executor.run(["shelve", workspace_name])
        return workspace_name

    def remove_workspace(self, workspace_name: str) -> None:
        self._executor.run(["workspace", "/delete", workspace_name])

    def resume_workspace(self, workspace_name: str, session_path: str) -> None:
        self._executor.run(["get", session_path, "/recursive", f"/workspace:{workspace_name}"])

    def promote_workspace(self, workspace_name: str, comment: str | None) -> str:
        final_comment = comment or workspace_name
        self._executor.run(["checkin", f"/comment:{final_comment}", f"/workspace:{workspace_name}"])
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
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
    ]
    creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    return subprocess.run(command, check=False, creationflags=creationflags).returncode


def build_runtime() -> Runtime:
    config = load_config()
    tf_path = config.tf_path or TfExeLocator().locate()
    runner = TfCommandRunner(tf_path, timeout_seconds=config.command_timeout_seconds)
    classifier = TfOutputClassifier()
    recovery = UnauthorizedRecoveryManager(config.tfs_scripts_path, run_recovery_script)
    executor = RetryingTfsExecutor(runner, classifier, recovery, max_retries=config.max_unauthorized_retries)
    detector = TfsProjectDetector(executor)
    onboarding = TfsProjectOnboardingAdvisor(detector)
    sessions = SessionManager(
        SessionStore(config.state_dir / "sessions.json"),
        actions=RuntimeSessionActions(executor),
    )
    return Runtime(config=config, detector=detector, onboarding=onboarding, executor=executor, sessions=sessions)
