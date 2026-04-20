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
    tfs_user: str | None
    tfs_pat: str | None
    session_base_dir: Path
    state_dir: Path
    command_timeout_seconds: int
    max_unauthorized_retries: int
    recovery_cooldown_seconds: int
    session_create_auto_get: bool
    disable_pat_dialog: bool


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def load_config(env: Mapping[str, str] | None = None) -> ServiceConfig:
    env = os.environ if env is None else env
    default_state_dir = Path(env.get("LOCALAPPDATA", "C:/ProgramData")) / "TfsMcp"
    state_dir = Path(env.get("TFSMCP_STATE_DIR", str(default_state_dir)))
    return ServiceConfig(
        http_host=env.get("TFSMCP_HTTP_HOST", "127.0.0.1"),
        http_port=int(env.get("TFSMCP_HTTP_PORT", "39393")),
        tf_path=env.get("TFSMCP_TF_PATH") or None,
        tfs_scripts_path=Path(env.get("TFSMCP_SCRIPTS_DIR", "C:/tfs_scripts")),
        tfs_user=env.get("TFSMCP_TFS_USER") or None,
        tfs_pat=env.get("TFSMCP_TFS_PAT") or None,
        session_base_dir=Path(env.get("TFSMCP_SESSION_DIR", "D:/TFS/.tfs-sessions")),
        state_dir=state_dir,
        command_timeout_seconds=int(env.get("TFSMCP_TIMEOUT", "120")),
        max_unauthorized_retries=int(env.get("TFSMCP_MAX_RETRIES", "1")),
        recovery_cooldown_seconds=int(env.get("TFSMCP_RECOVERY_COOLDOWN", "120")),
        session_create_auto_get=_to_bool(env.get("TFSMCP_SESSION_CREATE_AUTO_GET"), False),
        disable_pat_dialog=_to_bool(env.get("TFSMCP_DISABLE_PAT_DIALOG"), False),
    )
