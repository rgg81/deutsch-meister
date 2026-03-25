"""Tests for the progress tracking module.

Covers pure logic (tracker.py) and database-integrated tool (tool.py).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.db.connection import Database
from src.db.queries import get_or_create_user, get_user_progress, update_progress
from src.progress.tracker import (
    A1_GRAMMAR_TOPICS,
    A1_THEMES,
    CurriculumPosition,
    compute_advance,
    get_position,
)
from src.progress.tool import ProgressTool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db(tmp_path):
    """Create a temporary database, run migrations, and tear down after test."""
    database = Database(tmp_path / "test.db")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
async def tool(db: Database) -> ProgressTool:
    """Return a ProgressTool wired to the test DB with a sender context set."""
    t = ProgressTool(db)
    t.set_user_context("test_user_123")
    return t


# ---------------------------------------------------------------------------
# Pure logic — tracker.py
# ---------------------------------------------------------------------------


class TestGetPosition:
    """Tests for get_position()."""

    def test_returns_curriculum_position(self):
        pos = get_position("A1", 3, 2, 1, 2)
        assert isinstance(pos, CurriculumPosition)
        assert pos.cefr_level == "A1"
        assert pos.theme_index == 3
        assert pos.grammar_index == 2
        assert pos.phase == 1
        assert pos.week_number == 2
        assert pos.is_level_complete is False

    def test_level_complete_when_all_done(self):
        pos = get_position("A1", A1_THEMES, A1_GRAMMAR_TOPICS, 5, 12)
        assert pos.is_level_complete is True

    def test_not_complete_when_themes_remain(self):
        pos = get_position("A1", A1_THEMES - 1, A1_GRAMMAR_TOPICS, 5, 12)
        assert pos.is_level_complete is False

    def test_not_complete_when_grammar_remains(self):
        pos = get_position("A1", A1_THEMES, A1_GRAMMAR_TOPICS - 1, 5, 12)
        assert pos.is_level_complete is False

    def test_clamps_theme_to_max(self):
        pos = get_position("A1", 99, 0, 1, 1)
        assert pos.theme_index == A1_THEMES

    def test_clamps_grammar_to_max(self):
        pos = get_position("A1", 0, 99, 1, 1)
        assert pos.grammar_index == A1_GRAMMAR_TOPICS

    def test_unknown_level_falls_back_to_a1(self):
        pos = get_position("C2", 10, 10, 3, 5)
        assert pos.theme_index == 10
        assert pos.grammar_index == 10


class TestComputeAdvance:
    """Tests for compute_advance()."""

    def test_advance_theme(self):
        new_theme, new_grammar = compute_advance(3, 2, "theme")
        assert new_theme == 4
        assert new_grammar == 2

    def test_advance_grammar(self):
        new_theme, new_grammar = compute_advance(3, 2, "grammar")
        assert new_theme == 3
        assert new_grammar == 3

    def test_advance_theme_caps_at_max(self):
        new_theme, new_grammar = compute_advance(A1_THEMES, 0, "theme")
        assert new_theme == A1_THEMES

    def test_advance_grammar_caps_at_max(self):
        new_theme, new_grammar = compute_advance(0, A1_GRAMMAR_TOPICS, "grammar")
        assert new_grammar == A1_GRAMMAR_TOPICS

    def test_unknown_advance_type_returns_unchanged(self):
        new_theme, new_grammar = compute_advance(5, 5, "unknown")
        assert new_theme == 5
        assert new_grammar == 5


# ---------------------------------------------------------------------------
# Integration — tool.py with real Database
# ---------------------------------------------------------------------------


class TestProgressToolGetStatus:
    """Tests for ProgressTool.get_status action."""

    @pytest.mark.asyncio
    async def test_get_status_format(self, tool: ProgressTool):
        result = await tool.execute(action="get_status")
        assert "CEFR Level: A1" in result
        assert "Theme progress: 0/15" in result
        assert "Grammar progress: 0/15" in result
        assert "Words learned: 0" in result
        assert "Lessons completed: 0" in result
        assert "Current streak: 0 days" in result
        assert "Level complete: No" in result

    @pytest.mark.asyncio
    async def test_get_status_reflects_progress(self, db: Database, tool: ProgressTool):
        user = await get_or_create_user(db, "test_user_123")
        await update_progress(
            db, user.id,
            theme_index=5, grammar_index=3,
            words_learned=120, lessons_completed=10,
            current_streak=7, longest_streak=14,
        )
        result = await tool.execute(action="get_status")
        assert "Theme progress: 5/15" in result
        assert "Grammar progress: 3/15" in result
        assert "Words learned: 120" in result
        assert "Lessons completed: 10" in result
        assert "Current streak: 7 days" in result
        assert "Longest streak: 14 days" in result

    @pytest.mark.asyncio
    async def test_get_status_no_user_context(self, db: Database):
        tool = ProgressTool(db)
        result = await tool.execute(action="get_status")
        assert "Error" in result


class TestProgressToolAdvance:
    """Tests for ProgressTool.advance action."""

    @pytest.mark.asyncio
    async def test_advance_theme_updates_db(self, db: Database, tool: ProgressTool):
        result = await tool.execute(action="advance", advance_what="theme")
        assert "Advanced theme" in result
        assert "Theme: 1/15" in result

        user = await get_or_create_user(db, "test_user_123")
        progress = await get_user_progress(db, user.id)
        assert progress is not None
        assert progress.theme_index == 1

    @pytest.mark.asyncio
    async def test_advance_grammar_updates_db(self, db: Database, tool: ProgressTool):
        result = await tool.execute(action="advance", advance_what="grammar")
        assert "Advanced grammar" in result
        assert "Grammar: 1/15" in result

        user = await get_or_create_user(db, "test_user_123")
        progress = await get_user_progress(db, user.id)
        assert progress is not None
        assert progress.grammar_index == 1

    @pytest.mark.asyncio
    async def test_advance_multiple_times(self, db: Database, tool: ProgressTool):
        await tool.execute(action="advance", advance_what="theme")
        await tool.execute(action="advance", advance_what="theme")
        result = await tool.execute(action="advance", advance_what="theme")
        assert "Theme: 3/15" in result

        user = await get_or_create_user(db, "test_user_123")
        progress = await get_user_progress(db, user.id)
        assert progress is not None
        assert progress.theme_index == 3


class TestProgressToolRecordLesson:
    """Tests for ProgressTool.record_lesson action."""

    @pytest.mark.asyncio
    async def test_record_lesson_creates_record(self, db: Database, tool: ProgressTool):
        result = await tool.execute(
            action="record_lesson",
            block=2,
            story_type="alltag",
            theme="Greetings",
            grammar_topic="Personal Pronouns",
            duration_minutes=30,
        )
        assert "Lesson recorded" in result
        assert "Total lessons: 1" in result
        assert "Streak: 1 day" in result

        user = await get_or_create_user(db, "test_user_123")
        rows = await db.fetchall(
            "SELECT * FROM lesson_records WHERE user_id = ?", (user.id,)
        )
        assert len(rows) == 1
        assert rows[0]["block"] == 2
        assert rows[0]["story_type"] == "alltag"
        assert rows[0]["theme"] == "Greetings"

    @pytest.mark.asyncio
    async def test_record_lesson_increments_count(self, db: Database, tool: ProgressTool):
        await tool.execute(action="record_lesson", block=1)
        result = await tool.execute(action="record_lesson", block=2)
        assert "Total lessons: 2" in result

    @pytest.mark.asyncio
    async def test_record_lesson_same_day_keeps_streak(
        self, db: Database, tool: ProgressTool,
    ):
        """Two lessons on the same day should not double-count the streak."""
        await tool.execute(action="record_lesson", block=1)
        result = await tool.execute(action="record_lesson", block=2)
        assert "Streak: 1 day" in result


class TestProgressToolSetLevel:
    """Tests for ProgressTool.set_level action."""

    @pytest.mark.asyncio
    async def test_set_level_resets_position(self, db: Database, tool: ProgressTool):
        # Advance first
        await tool.execute(action="advance", advance_what="theme")
        await tool.execute(action="advance", advance_what="grammar")

        # Now set to A2
        result = await tool.execute(action="set_level", cefr_level="A2")
        assert "CEFR level set to A2" in result
        assert "reset to 0" in result

        user = await get_or_create_user(db, "test_user_123")
        progress = await get_user_progress(db, user.id)
        assert progress is not None
        assert progress.cefr_level == "A2"
        assert progress.theme_index == 0
        assert progress.grammar_index == 0
        assert progress.phase == 1
        assert progress.week_number == 1

    @pytest.mark.asyncio
    async def test_set_level_updates_users_table(self, db: Database, tool: ProgressTool):
        await tool.execute(action="set_level", cefr_level="B1")
        user = await get_or_create_user(db, "test_user_123")
        assert user.cefr_level == "B1"

    @pytest.mark.asyncio
    async def test_set_level_invalid(self, tool: ProgressTool):
        result = await tool.execute(action="set_level", cefr_level="C2")
        assert "Error" in result
        assert "C2" in result


class TestStreakLogic:
    """Tests for streak calculation across days."""

    @pytest.mark.asyncio
    async def test_consecutive_days_increment_streak(
        self, db: Database, tool: ProgressTool,
    ):
        """Lessons on consecutive days should grow the streak."""
        yesterday = date.today() - timedelta(days=1)
        user = await get_or_create_user(db, "test_user_123")
        await update_progress(
            db, user.id,
            current_streak=3,
            longest_streak=5,
            last_lesson_date=yesterday.isoformat(),
            lessons_completed=10,
        )

        result = await tool.execute(action="record_lesson", block=1)
        assert "Streak: 4 days" in result
        assert "Total lessons: 11" in result

    @pytest.mark.asyncio
    async def test_gap_resets_streak(self, db: Database, tool: ProgressTool):
        """A gap of more than one day should reset the streak to 1."""
        three_days_ago = date.today() - timedelta(days=3)
        user = await get_or_create_user(db, "test_user_123")
        await update_progress(
            db, user.id,
            current_streak=10,
            longest_streak=10,
            last_lesson_date=three_days_ago.isoformat(),
            lessons_completed=20,
        )

        result = await tool.execute(action="record_lesson", block=1)
        assert "Streak: 1 day" in result

        progress = await get_user_progress(db, user.id)
        assert progress is not None
        assert progress.current_streak == 1
        # longest_streak should be preserved
        assert progress.longest_streak == 10

    @pytest.mark.asyncio
    async def test_streak_updates_longest(self, db: Database, tool: ProgressTool):
        """When the current streak surpasses longest, longest should update."""
        yesterday = date.today() - timedelta(days=1)
        user = await get_or_create_user(db, "test_user_123")
        await update_progress(
            db, user.id,
            current_streak=5,
            longest_streak=5,
            last_lesson_date=yesterday.isoformat(),
            lessons_completed=5,
        )

        result = await tool.execute(action="record_lesson", block=1)
        assert "Streak: 6 days" in result

        progress = await get_user_progress(db, user.id)
        assert progress is not None
        assert progress.longest_streak == 6


class TestUnknownAction:
    """Test edge cases."""

    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self, tool: ProgressTool):
        result = await tool.execute(action="nonexistent")
        assert "Error" in result
        assert "nonexistent" in result
