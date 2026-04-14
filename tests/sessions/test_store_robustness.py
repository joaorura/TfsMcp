import json
from pathlib import Path

from tfsmcp.sessions.store import SessionStore


def test_session_store_handles_legacy_single_object_format(tmp_path):
    """Test that SessionStore can load legacy JSON format with single object instead of array."""
    store_path = tmp_path / "sessions.json"
    
    # Write legacy format (single object, not array)
    legacy_data = {
        "name": "legacy-session",
        "project_path": "$/Project",
        "session_path": "D:/sessions/legacy",
        "server_path": "$/Project",
        "workspace_name": "legacy-ws",
        "mode": "hybrid",
        "status": "active",
        "last_shelveset": None
    }
    store_path.write_text(json.dumps(legacy_data), encoding="utf-8")
    
    # Load should convert single object to list
    store = SessionStore(store_path)
    records = store.load_all()
    
    assert len(records) == 1
    assert records[0].name == "legacy-session"
    assert records[0].status == "active"


def test_session_store_handles_array_format(tmp_path):
    """Test that SessionStore works with standard array format."""
    store_path = tmp_path / "sessions.json"
    
    # Write standard array format
    array_data = [{
        "name": "session-1",
        "project_path": "$/Project",
        "session_path": "D:/sessions/1",
        "server_path": "$/Project",
        "workspace_name": "ws-1",
        "mode": "hybrid",
        "status": "active",
        "last_shelveset": None
    }]
    store_path.write_text(json.dumps(array_data), encoding="utf-8")
    
    store = SessionStore(store_path)
    records = store.load_all()
    
    assert len(records) == 1
    assert records[0].name == "session-1"


def test_session_store_handles_malformed_json_gracefully(tmp_path):
    """Test that SessionStore returns empty list for malformed JSON."""
    store_path = tmp_path / "sessions.json"
    
    # Write invalid JSON structure (string instead of object/array)
    store_path.write_text(json.dumps("not-a-valid-structure"), encoding="utf-8")
    
    store = SessionStore(store_path)
    records = store.load_all()
    
    assert records == []


def test_session_store_skips_non_dict_items_in_array(tmp_path):
    """Test that SessionStore skips invalid items in array."""
    store_path = tmp_path / "sessions.json"
    
    # Write array with mixed valid and invalid items
    mixed_data = [
        {
            "name": "valid-session",
            "project_path": "$/Project",
            "session_path": "D:/sessions/valid",
            "server_path": "$/Project",
            "workspace_name": "valid-ws",
            "mode": "hybrid",
            "status": "active",
            "last_shelveset": None
        },
        "invalid-item",
        123,
        None
    ]
    store_path.write_text(json.dumps(mixed_data), encoding="utf-8")
    
    store = SessionStore(store_path)
    records = store.load_all()
    
    assert len(records) == 1
    assert records[0].name == "valid-session"
