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
    assert config.recovery_cooldown_seconds == 120


def test_load_config_uses_process_environment_when_env_not_passed(monkeypatch, tmp_path):
    monkeypatch.setenv("TFSMCP_HTTP_PORT", "40123")
    monkeypatch.setenv("TFSMCP_STATE_DIR", str(tmp_path / "runtime-state"))

    config = load_config()

    assert config.http_port == 40123
    assert config.state_dir == tmp_path / "runtime-state"


def test_load_config_uses_custom_recovery_cooldown(tmp_path):
    config = load_config(
        {
            "TFSMCP_STATE_DIR": str(tmp_path / "state"),
            "TFSMCP_RECOVERY_COOLDOWN": "15",
        }
    )

    assert config.recovery_cooldown_seconds == 15


def test_configure_logging_creates_log_file(tmp_path):
    log_file = tmp_path / "service.log"

    logger = configure_logging(log_file)
    logger.info("hello")

    assert log_file.exists()
    assert "hello" in log_file.read_text(encoding="utf-8")
