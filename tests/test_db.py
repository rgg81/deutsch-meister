"""Unit tests for the SQLite database layer."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.db.connection import Database
from src.db.queries import (
    add_vocab_card,
    get_cards_due,
    get_or_create_user,
    get_user_progress,
    record_lesson,
    update_card_review,
    update_progress,
    update_user,
)


@pytest.fixture
async def db(tmp_path):
    """Create a temporary database, run migrations, and tear down after test."""
    database = Database(tmp_path / "test.db")
    await database.connect()
    yield database
    await database.close()


# ---------------------------------------------------------------------------
# Connection & migrations
# ---------------------------------------------------------------------------


class TestConnection:
    """Tests for Database.connect() and migration runner."""

    @pytest.mark.asyncio
    async def test_connect_creates_tables(self, db: Database):
        tables = await db.fetchall(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
        names = {t["name"] for t in tables}
        assert "users" in names
        assert "vocab_cards" in names
        assert "lesson_records" in names
        assert "user_progress" in names
        assert "schema_version" in names

    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self, db: Database):
        row = await db.fetchone("PRAGMA journal_mode")
        assert row is not None
        # journal_mode returns a row with a single column
        mode = list(row.values())[0]
        assert mode == "wal"

    @pytest.mark.asyncio
    async def test_foreign_keys_enabled(self, db: Database):
        row = await db.fetchone("PRAGMA foreign_keys")
        assert row is not None
        enabled = list(row.values())[0]
        assert enabled == 1

    @pytest.mark.asyncio
    async def test_migration_version_recorded(self, db: Database):
        row = await db.fetchone("SELECT MAX(version) AS v FROM schema_version")
        assert row is not None
        assert row["v"] == 1

    @pytest.mark.asyncio
    async def test_migrations_are_idempotent(self, tmp_path):
        """Running connect() twice must not fail or duplicate the version row."""
        database = Database(tmp_path / "idempotent.db")
        await database.connect()
        await database.close()

        database2 = Database(tmp_path / "idempotent.db")
        await database2.connect()
        rows = await database2.fetchall("SELECT version FROM schema_version")
        await database2.close()
        assert len(rows) == 1
        assert rows[0]["version"] == 1

    @pytest.mark.asyncio
    async def test_conn_raises_when_not_connected(self):
        database = Database(":memory:")
        with pytest.raises(RuntimeError, match="not connected"):
            _ = database.conn


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class TestUsers:
    """Tests for user CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_or_create_user_creates(self, db: Database):
        user = await get_or_create_user(db, "12345", "Alice")
        assert user.telegram_id == "12345"
        assert user.display_name == "Alice"
        assert user.cefr_level == "A1"
        assert user.onboarding_complete is False

    @pytest.mark.asyncio
    async def test_get_or_create_user_returns_existing(self, db: Database):
        user1 = await get_or_create_user(db, "12345", "Alice")
        user2 = await get_or_create_user(db, "12345", "Alice Updated")
        assert user1.id == user2.id
        # display_name should NOT be updated by get_or_create
        assert user2.display_name == "Alice"

    @pytest.mark.asyncio
    async def test_update_user(self, db: Database):
        user = await get_or_create_user(db, "99", "Bob")
        await update_user(db, user.id, cefr_level="A2", timezone="UTC")
        row = await db.fetchone("SELECT * FROM users WHERE id = ?", (user.id,))
        assert row is not None
        assert row["cefr_level"] == "A2"
        assert row["timezone"] == "UTC"

    @pytest.mark.asyncio
    async def test_update_user_ignores_unknown_fields(self, db: Database):
        user = await get_or_create_user(db, "100")
        # Should not raise even with unknown keys
        await update_user(db, user.id, nonexistent_field="value")


# ---------------------------------------------------------------------------
# Vocab cards
# ---------------------------------------------------------------------------


class TestVocabCards:
    """Tests for vocabulary card operations."""

    @pytest.mark.asyncio
    async def test_add_vocab_card(self, db: Database):
        user = await get_or_create_user(db, "1")
        card = await add_vocab_card(
            db, user.id, "Hund", "dog",
            gender="der", part_of_speech="noun", plural="Hunde",
        )
        assert card.word_de == "Hund"
        assert card.word_en == "dog"
        assert card.gender == "der"
        assert card.interval_days == 0
        assert card.ease_factor == 2.5
        assert card.next_review is None

    @pytest.mark.asyncio
    async def test_get_cards_due_returns_new_cards(self, db: Database):
        user = await get_or_create_user(db, "1")
        await add_vocab_card(db, user.id, "Katze", "cat")
        await add_vocab_card(db, user.id, "Hund", "dog")
        due = await get_cards_due(db, user.id)
        assert len(due) == 2

    @pytest.mark.asyncio
    async def test_get_cards_due_excludes_future(self, db: Database):
        user = await get_or_create_user(db, "1")
        card = await add_vocab_card(db, user.id, "Haus", "house")
        # Push review into the future
        future = (date.today() + timedelta(days=30)).isoformat()
        await db.execute(
            "UPDATE vocab_cards SET next_review = ? WHERE id = ?",
            (future, card.id),
        )
        await db.commit()
        due = await get_cards_due(db, user.id)
        assert len(due) == 0

    @pytest.mark.asyncio
    async def test_get_cards_due_respects_limit(self, db: Database):
        user = await get_or_create_user(db, "1")
        for i in range(5):
            await add_vocab_card(db, user.id, f"Wort{i}", f"word{i}")
        due = await get_cards_due(db, user.id, limit=3)
        assert len(due) == 3

    @pytest.mark.asyncio
    async def test_update_card_review_correct(self, db: Database):
        user = await get_or_create_user(db, "1")
        card = await add_vocab_card(db, user.id, "Buch", "book")

        await update_card_review(db, card.id, correct=True)
        row = await db.fetchone("SELECT * FROM vocab_cards WHERE id = ?", (card.id,))
        assert row is not None
        assert row["interval_days"] == 1
        assert row["review_count"] == 1
        assert row["correct_count"] == 1
        assert row["ease_factor"] == pytest.approx(2.6, abs=0.01)

        # Second correct review: interval 1 -> 6
        await update_card_review(db, card.id, correct=True)
        row = await db.fetchone("SELECT * FROM vocab_cards WHERE id = ?", (card.id,))
        assert row is not None
        assert row["interval_days"] == 6
        assert row["review_count"] == 2
        assert row["correct_count"] == 2

        # Third correct: interval = round(6 * 2.7) = 16
        await update_card_review(db, card.id, correct=True)
        row = await db.fetchone("SELECT * FROM vocab_cards WHERE id = ?", (card.id,))
        assert row is not None
        assert row["interval_days"] == round(6 * 2.7)

    @pytest.mark.asyncio
    async def test_update_card_review_incorrect_resets(self, db: Database):
        user = await get_or_create_user(db, "1")
        card = await add_vocab_card(db, user.id, "Stuhl", "chair")

        # Get to interval=6 first
        await update_card_review(db, card.id, correct=True)
        await update_card_review(db, card.id, correct=True)

        # Now fail
        await update_card_review(db, card.id, correct=False)
        row = await db.fetchone("SELECT * FROM vocab_cards WHERE id = ?", (card.id,))
        assert row is not None
        assert row["interval_days"] == 0
        assert row["review_count"] == 3
        assert row["correct_count"] == 2
        # ease should have dropped
        assert row["ease_factor"] < 2.7

    @pytest.mark.asyncio
    async def test_ease_factor_floor(self, db: Database):
        """Ease factor must never drop below 1.3."""
        user = await get_or_create_user(db, "1")
        card = await add_vocab_card(db, user.id, "Tisch", "table")

        # Fail many times
        for _ in range(20):
            await update_card_review(db, card.id, correct=False)

        row = await db.fetchone("SELECT * FROM vocab_cards WHERE id = ?", (card.id,))
        assert row is not None
        assert row["ease_factor"] >= 1.3


# ---------------------------------------------------------------------------
# Lesson records
# ---------------------------------------------------------------------------


class TestLessonRecords:
    """Tests for lesson record operations."""

    @pytest.mark.asyncio
    async def test_record_lesson(self, db: Database):
        user = await get_or_create_user(db, "1")
        lesson = await record_lesson(
            db, user.id, "2026-03-25",
            block=2, story_type="alltag", theme="Einkaufen",
            grammar_topic="Akkusativ", completed=True,
        )
        assert lesson.user_id == user.id
        assert lesson.lesson_date == "2026-03-25"
        assert lesson.block == 2
        assert lesson.completed is True

    @pytest.mark.asyncio
    async def test_multiple_lessons_same_day(self, db: Database):
        user = await get_or_create_user(db, "1")
        await record_lesson(db, user.id, "2026-03-25", block=1)
        await record_lesson(db, user.id, "2026-03-25", block=2)
        rows = await db.fetchall(
            "SELECT * FROM lesson_records WHERE user_id = ? AND lesson_date = ?",
            (user.id, "2026-03-25"),
        )
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# User progress
# ---------------------------------------------------------------------------


class TestUserProgress:
    """Tests for user progress operations."""

    @pytest.mark.asyncio
    async def test_get_progress_returns_none_initially(self, db: Database):
        user = await get_or_create_user(db, "1")
        progress = await get_user_progress(db, user.id)
        assert progress is None

    @pytest.mark.asyncio
    async def test_update_progress_creates_row(self, db: Database):
        user = await get_or_create_user(db, "1")
        await update_progress(db, user.id, words_learned=10, current_streak=3)
        progress = await get_user_progress(db, user.id)
        assert progress is not None
        assert progress.words_learned == 10
        assert progress.current_streak == 3
        assert progress.cefr_level == "A1"  # default

    @pytest.mark.asyncio
    async def test_update_progress_modifies_existing(self, db: Database):
        user = await get_or_create_user(db, "1")
        await update_progress(db, user.id, words_learned=5)
        await update_progress(db, user.id, words_learned=15, cefr_level="A2")
        progress = await get_user_progress(db, user.id)
        assert progress is not None
        assert progress.words_learned == 15
        assert progress.cefr_level == "A2"

    @pytest.mark.asyncio
    async def test_update_progress_ignores_unknown_fields(self, db: Database):
        user = await get_or_create_user(db, "1")
        await update_progress(db, user.id, nonexistent="value")
        # Row should be created with defaults
        progress = await get_user_progress(db, user.id)
        assert progress is not None


# ---------------------------------------------------------------------------
# Multi-user isolation
# ---------------------------------------------------------------------------


class TestMultiUserIsolation:
    """Verify all queries are properly scoped by user_id."""

    @pytest.mark.asyncio
    async def test_vocab_cards_isolated(self, db: Database):
        alice = await get_or_create_user(db, "alice_tg")
        bob = await get_or_create_user(db, "bob_tg")

        await add_vocab_card(db, alice.id, "Apfel", "apple")
        await add_vocab_card(db, alice.id, "Birne", "pear")
        await add_vocab_card(db, bob.id, "Wasser", "water")

        alice_due = await get_cards_due(db, alice.id)
        bob_due = await get_cards_due(db, bob.id)

        assert len(alice_due) == 2
        assert len(bob_due) == 1
        assert all(c.user_id == alice.id for c in alice_due)
        assert all(c.user_id == bob.id for c in bob_due)

    @pytest.mark.asyncio
    async def test_lessons_isolated(self, db: Database):
        alice = await get_or_create_user(db, "alice_tg")
        bob = await get_or_create_user(db, "bob_tg")

        await record_lesson(db, alice.id, "2026-03-25", block=1)
        await record_lesson(db, bob.id, "2026-03-25", block=2)

        alice_lessons = await db.fetchall(
            "SELECT * FROM lesson_records WHERE user_id = ?", (alice.id,)
        )
        bob_lessons = await db.fetchall(
            "SELECT * FROM lesson_records WHERE user_id = ?", (bob.id,)
        )

        assert len(alice_lessons) == 1
        assert alice_lessons[0]["block"] == 1
        assert len(bob_lessons) == 1
        assert bob_lessons[0]["block"] == 2

    @pytest.mark.asyncio
    async def test_progress_isolated(self, db: Database):
        alice = await get_or_create_user(db, "alice_tg")
        bob = await get_or_create_user(db, "bob_tg")

        await update_progress(db, alice.id, words_learned=50)
        await update_progress(db, bob.id, words_learned=10)

        alice_p = await get_user_progress(db, alice.id)
        bob_p = await get_user_progress(db, bob.id)

        assert alice_p is not None and alice_p.words_learned == 50
        assert bob_p is not None and bob_p.words_learned == 10
