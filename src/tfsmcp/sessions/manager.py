from pathlib import Path

from tfsmcp.contracts import SessionRecord


class SessionManager:
    def __init__(self, store, actions) -> None:
        self._store = store
        self._actions = actions

    def list_records(self) -> list[SessionRecord]:
        return self._store.load_all()

    def create(self, name: str, source_path: str, session_path: Path) -> SessionRecord:
        records = self._store.load_all()
        for record in records:
            if record.name == name:
                raise ValueError(name)

        server_path = self._actions.create_workspace(name, source_path, str(session_path))
        record = SessionRecord(
            name,
            source_path,
            str(session_path),
            server_path,
            name,
            "hybrid",
            "active",
        )
        records.append(record)
        self._store.save_all(records)
        return record

    def suspend(self, name: str) -> SessionRecord:
        records = self._store.load_all()
        for record in records:
            if record.name == name:
                record.status = "suspended"
                record.last_shelveset = self._actions.create_shelveset(record.workspace_name)
                self._store.save_all(records)
                return record
        raise KeyError(name)

    def discard(self, name: str) -> SessionRecord:
        records = self._store.load_all()
        for record in records:
            if record.name == name:
                self._actions.remove_workspace(record.workspace_name)
                record.status = "discarded"
                self._store.save_all(records)
                return record
        raise KeyError(name)

    def resume(self, name: str) -> SessionRecord:
        records = self._store.load_all()
        for record in records:
            if record.name == name:
                if record.status != "suspended":
                    raise ValueError(record.status)
                self._actions.resume_workspace(record.workspace_name, record.session_path)
                record.status = "active"
                self._store.save_all(records)
                return record
        raise KeyError(name)

    def promote(self, name: str, comment: str | None) -> SessionRecord:
        records = self._store.load_all()
        for record in records:
            if record.name == name:
                if record.status != "active":
                    raise ValueError(record.status)
                record.last_shelveset = self._actions.promote_workspace(record.workspace_name, comment)
                record.status = "promoted"
                self._store.save_all(records)
                return record
        raise KeyError(name)
