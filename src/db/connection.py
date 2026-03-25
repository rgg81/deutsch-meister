"""Async SQLite connection manager with WAL mode and migration support."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
from loguru import logger


class Database:
    """Async SQLite database with WAL mode and auto-migration.

    Usage::

        db = Database("./data/app.db")
        await db.connect()   # opens connection, runs pending migrations
        row = await db.fetchone("SELECT 1")
        await db.close()
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open connection, enable WAL mode, run migrations."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self._db_path))
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._run_migrations()

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        """Return the active connection or raise if not connected."""
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Execute a single SQL statement."""
        return await self.conn.execute(sql, params)

    async def executemany(self, sql: str, params_seq: list[tuple]) -> aiosqlite.Cursor:
        """Execute a SQL statement against all parameter sequences."""
        return await self.conn.executemany(sql, params_seq)

    async def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        """Execute *sql* and return the first row as a dict, or ``None``."""
        cursor = await self.conn.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute *sql* and return all rows as a list of dicts."""
        cursor = await self.conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self.conn.commit()

    async def _run_migrations(self) -> None:
        """Run pending SQL migrations from ``src/db/migrations/``."""
        await self.conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            "  version INTEGER PRIMARY KEY,"
            "  applied_at TEXT NOT NULL DEFAULT (datetime('now'))"
            ")"
        )
        await self.conn.commit()

        cursor = await self.conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_version"
        )
        row = await cursor.fetchone()
        current_version = row[0] if row else 0

        migrations_dir = Path(__file__).parent / "migrations"
        if not migrations_dir.exists():
            return

        migration_files = sorted(migrations_dir.glob("*.sql"))
        for mf in migration_files:
            version = int(mf.stem.split("_")[0])
            if version <= current_version:
                continue
            logger.info("Applying migration {} ({})", version, mf.name)
            sql = mf.read_text(encoding="utf-8")
            await self.conn.executescript(sql)
            await self.conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (version,)
            )
            await self.conn.commit()
            logger.info("Migration {} applied", version)
