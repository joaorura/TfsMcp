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
        temp_path = self._path.with_name(f"{self._path.name}.tmp")
        temp_path.write_text(
            json.dumps([record.to_dict() for record in records], indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self._path)
