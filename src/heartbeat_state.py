"""JSON-backed state for heartbeat pause/resume and last-reminder tracking."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class HeartbeatState:
    """Manages heartbeat state persisted in a JSON file.

    State file stores:
        - paused: whether the user has paused reminders
        - last_reminder_at: ISO timestamp of the last sent reminder
    """

    def __init__(self, path: Path):
        self._path = path

    def _read(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {"paused": False, "last_reminder_at": None}

    def _write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    @property
    def paused(self) -> bool:
        return bool(self._read().get("paused", False))

    def pause(self) -> None:
        data = self._read()
        data["paused"] = True
        self._write(data)

    def resume(self) -> None:
        data = self._read()
        data["paused"] = False
        self._write(data)

    @property
    def last_reminder_at(self) -> datetime | None:
        raw = self._read().get("last_reminder_at")
        if raw:
            return datetime.fromisoformat(raw)
        return None

    def record_reminder(self) -> None:
        data = self._read()
        data["last_reminder_at"] = datetime.now(timezone.utc).isoformat()
        self._write(data)
