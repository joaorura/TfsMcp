import os
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
    recovery_cooldown_seconds: int


def load_config(env: Mapping[str, str] | None = None) -> ServiceConfig:
    env = os.environ if env is None else env
    default_state_dir = Path(env.get("LOCALAPPDATA", "C:/ProgramData")) / "TfsMcp"
    state_dir = Path(env.get("TFSMCP_STATE_DIR", str(default_state_dir)))
    return ServiceConfig(
        http_host=env.get("TFSMCP_HTTP_HOST", "127.0.0.1"),
        http_port=int(env.get("TFSMCP_HTTP_PORT", "39393")),
        tf_path=env.get("TFSMCP_TF_PATH") or None,
        tfs_scripts_path=Path(env.get("TFSMCP_SCRIPTS_DIR", "C:/tfs_scripts")),
        session_base_dir=Path(env.get("TFSMCP_SESSION_DIR", "D:/TFS/.tfs-sessions")),
        state_dir=state_dir,
        command_timeout_seconds=int(env.get("TFSMCP_TIMEOUT", "120")),
        max_unauthorized_retries=int(env.get("TFSMCP_MAX_RETRIES", "1")),
        recovery_cooldown_seconds=int(env.get("TFSMCP_RECOVERY_COOLDOWN", "120")),
    )
