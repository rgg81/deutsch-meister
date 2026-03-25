"""Database layer for DeutschMeister — async SQLite with WAL mode."""

from __future__ import annotations

from src.db.connection import Database


def get_db(config: dict) -> Database:
    """Create a Database instance from application config.

    Args:
        config: Application configuration dict. Expects a ``database.path`` key
                pointing to the SQLite file location.

    Returns:
        An uninitialised :class:`Database` — caller must ``await db.connect()``.
    """
    db_section = config.get("database", {})
    path = db_section.get("path", "./workspace/deutschmeister.db")
    return Database(path)
