from pathlib import Path


README_PATH = Path(__file__).resolve().parents[1] / "README.md"


def test_readme_mentions_service_install_and_recovery_scripts():
    readme = README_PATH.read_text(encoding="utf-8")

    assert "python -m tfsmcp.service install" in readme
    assert "C:\\tfs_scripts" in readme
    assert "source_path" in readme
    assert "session_path" in readme


def test_readme_mentions_session_lifecycle_surface():
    readme = README_PATH.read_text(encoding="utf-8")

    assert "tfs_session_create" in readme
    assert "tfs_session_list" in readme
    assert "tfs_session_suspend" in readme
    assert "tfs_session_discard" in readme
    assert "POST /sessions" in readme
    assert "POST /sessions/{name}/suspend" in readme
    assert "DELETE /sessions/{name}" in readme


def test_readme_mentions_real_workspace_session_surface():
    readme = README_PATH.read_text(encoding="utf-8")

    assert "tfs_session_resume" in readme
    assert "tfs_session_promote" in readme
    assert "POST /sessions/{name}/resume" in readme
    assert "POST /sessions/{name}/promote" in readme
    assert "tf workspace /new" in readme
    assert "tf workfold /map" in readme
    assert "tf get" in readme
