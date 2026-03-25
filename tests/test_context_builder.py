"""Tests for the lesson context provider.

Covers graceful degradation, full data scenarios, difficulty signal
thresholds, and multi-user correctness.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.context.builder import make_lesson_context_provider
from src.db.connection import Database
from src.db.queries import (
    add_vocab_card,
    get_or_create_user,
    record_lesson,
    update_card_review,
    update_progress,
    update_user,
)


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
def provider(db: Database):
    """Return a lesson context provider wired to the test database."""
    return make_lesson_context_provider(db)


# ---------------------------------------------------------------------------
# New user — graceful degradation
# ---------------------------------------------------------------------------


class TestNewUser:
    """Provider must return valid output for a brand-new user with no data."""

    @pytest.mark.asyncio
    async def test_new_user_returns_notebook(self, provider):
        result = await provider("new_user_999")
        assert result.startswith("## Teacher's Notebook")

    @pytest.mark.asyncio
    async def test_new_user_has_profile_section(self, provider):
        result = await provider("new_user_999")
        assert "### Student Profile" in result
        assert "Name: Unknown" in result

    @pytest.mark.asyncio
    async def test_new_user_has_no_progress(self, provider):
        result = await provider("new_user_999")
        assert "No progress data yet" in result

    @pytest.mark.asyncio
    async def test_new_user_has_no_engagement(self, provider):
        result = await provider("new_user_999")
        assert "No engagement data yet" in result

    @pytest.mark.asyncio
    async def test_new_user_has_no_srs(self, provider):
        result = await provider("new_user_999")
        # Either "No SRS data available yet" or "Total Cards: 0"
        assert "Total Cards: 0" in result or "No SRS data" in result

    @pytest.mark.asyncio
    async def test_new_user_has_no_lessons(self, provider):
        result = await provider("new_user_999")
        assert "No lessons recorded yet" in result

    @pytest.mark.asyncio
    async def test_new_user_difficulty_not_enough_data(self, provider):
        result = await provider("new_user_999")
        assert "Not enough data for difficulty assessment" in result

    @pytest.mark.asyncio
    async def test_new_user_onboarding_incomplete(self, provider):
        result = await provider("new_user_999")
        assert "NOT complete" in result


# ---------------------------------------------------------------------------
# Full profile data
# ---------------------------------------------------------------------------


class TestFullProfile:
    """Provider includes user profile details when available."""

    @pytest.mark.asyncio
    async def test_profile_with_name(self, db: Database, provider):
        user = await get_or_create_user(db, "alice_tg", "Alice")
        result = await provider("alice_tg")
        assert "Name: Alice" in result

    @pytest.mark.asyncio
    async def test_profile_with_interests_json_array(self, db: Database, provider):
        user = await get_or_create_user(db, "bob_tg", "Bob")
        await update_user(db, user.id, interests='["cooking", "travel"]')
        result = await provider("bob_tg")
        assert "cooking" in result
        assert "travel" in result

    @pytest.mark.asyncio
    async def test_profile_with_interests_plain_string(self, db: Database, provider):
        user = await get_or_create_user(db, "carol_tg", "Carol")
        await update_user(db, user.id, interests="music")
        result = await provider("carol_tg")
        assert "music" in result

    @pytest.mark.asyncio
    async def test_profile_shows_cefr_level(self, db: Database, provider):
        user = await get_or_create_user(db, "dave_tg", "Dave")
        await update_user(db, user.id, cefr_level="A2")
        result = await provider("dave_tg")
        assert "CEFR Level: A2" in result

    @pytest.mark.asyncio
    async def test_profile_onboarding_complete(self, db: Database, provider):
        user = await get_or_create_user(db, "eve_tg", "Eve")
        await update_user(db, user.id, onboarding_complete=1)
        result = await provider("eve_tg")
        assert "Onboarding: complete" in result

    @pytest.mark.asyncio
    async def test_profile_shows_timezone(self, db: Database, provider):
        user = await get_or_create_user(db, "tz_tg", "TimezoneUser")
        await update_user(db, user.id, timezone="America/New_York")
        result = await provider("tz_tg")
        assert "America/New_York" in result

    @pytest.mark.asyncio
    async def test_profile_shows_daily_goal(self, db: Database, provider):
        result = await provider("goal_tg")
        # Default is 60 min
        assert "Daily Goal: 60 min" in result


# ---------------------------------------------------------------------------
# Progress data
# ---------------------------------------------------------------------------


class TestProgressData:
    """Provider includes curriculum position when progress exists."""

    @pytest.mark.asyncio
    async def test_progress_shows_position(self, db: Database, provider):
        user = await get_or_create_user(db, "prog_tg")
        await update_progress(
            db, user.id,
            cefr_level="A1", theme_index=5, grammar_index=3,
            phase=2, week_number=4,
            words_learned=120, lessons_completed=15,
        )
        result = await provider("prog_tg")
        assert "Level: A1" in result
        assert "Theme: 5/15" in result
        assert "Grammar: 3/15" in result
        assert "Phase: 2, Week: 4" in result
        assert "Words Learned: 120" in result
        assert "Lessons Completed: 15" in result

    @pytest.mark.asyncio
    async def test_streak_displayed(self, db: Database, provider):
        user = await get_or_create_user(db, "streak_tg")
        await update_progress(
            db, user.id,
            current_streak=7, longest_streak=14,
        )
        result = await provider("streak_tg")
        assert "Current Streak: 7 days" in result
        assert "Longest Streak: 14 days" in result

    @pytest.mark.asyncio
    async def test_last_lesson_today(self, db: Database, provider):
        user = await get_or_create_user(db, "today_tg")
        await update_progress(
            db, user.id,
            last_lesson_date=date.today().isoformat(),
        )
        result = await provider("today_tg")
        assert "Last Lesson: today" in result

    @pytest.mark.asyncio
    async def test_last_lesson_yesterday(self, db: Database, provider):
        user = await get_or_create_user(db, "yest_tg")
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        await update_progress(db, user.id, last_lesson_date=yesterday)
        result = await provider("yest_tg")
        assert "Last Lesson: yesterday" in result

    @pytest.mark.asyncio
    async def test_last_lesson_days_ago_with_away_hint(self, db: Database, provider):
        user = await get_or_create_user(db, "away_tg")
        five_days_ago = (date.today() - timedelta(days=5)).isoformat()
        await update_progress(db, user.id, last_lesson_date=five_days_ago)
        result = await provider("away_tg")
        assert "5 days ago" in result
        assert "welcome back warmly" in result

    @pytest.mark.asyncio
    async def test_last_lesson_never(self, db: Database, provider):
        user = await get_or_create_user(db, "never_tg")
        await update_progress(db, user.id, words_learned=0)
        result = await provider("never_tg")
        assert "Last Lesson: never" in result


# ---------------------------------------------------------------------------
# SRS stats
# ---------------------------------------------------------------------------


class TestSRSStats:
    """Provider includes SRS review statistics."""

    @pytest.mark.asyncio
    async def test_srs_with_cards(self, db: Database, provider):
        user = await get_or_create_user(db, "srs_tg")
        await add_vocab_card(db, user.id, "Hund", "dog")
        await add_vocab_card(db, user.id, "Katze", "cat")
        result = await provider("srs_tg")
        assert "Total Cards: 2" in result
        assert "Due Today: 2" in result

    @pytest.mark.asyncio
    async def test_srs_new_vs_review(self, db: Database, provider):
        user = await get_or_create_user(db, "mix_tg")
        c1 = await add_vocab_card(db, user.id, "Buch", "book")
        c2 = await add_vocab_card(db, user.id, "Tisch", "table")
        # Review c1 so it's no longer "new" but still due (interval=1, next_review=today)
        await update_card_review(db, c1.id, correct=True)
        # Set next_review to today so it's still due
        await db.execute(
            "UPDATE vocab_cards SET next_review = ? WHERE id = ?",
            (date.today().isoformat(), c1.id),
        )
        await db.commit()
        result = await provider("mix_tg")
        assert "1 new" in result
        assert "1 review" in result

    @pytest.mark.asyncio
    async def test_srs_accuracy(self, db: Database, provider):
        user = await get_or_create_user(db, "acc_tg")
        c1 = await add_vocab_card(db, user.id, "Stuhl", "chair")
        # 4 correct, 1 incorrect => 4/5 = 80%
        await update_card_review(db, c1.id, correct=True)
        await update_card_review(db, c1.id, correct=True)
        await update_card_review(db, c1.id, correct=True)
        await update_card_review(db, c1.id, correct=True)
        await update_card_review(db, c1.id, correct=False)
        result = await provider("acc_tg")
        assert "Overall Accuracy: 80%" in result

    @pytest.mark.asyncio
    async def test_srs_mature_cards(self, db: Database, provider):
        user = await get_or_create_user(db, "mature_tg")
        c1 = await add_vocab_card(db, user.id, "Haus", "house")
        c2 = await add_vocab_card(db, user.id, "Baum", "tree")
        # Make c1 mature (interval >= 14)
        await db.execute(
            "UPDATE vocab_cards SET interval_days = 21 WHERE id = ?", (c1.id,)
        )
        await db.commit()
        result = await provider("mature_tg")
        assert "Mature Cards" in result
        assert "1" in result  # Only c1 is mature


# ---------------------------------------------------------------------------
# Lesson history
# ---------------------------------------------------------------------------


class TestLessonHistory:
    """Provider includes last lesson records."""

    @pytest.mark.asyncio
    async def test_lesson_history(self, db: Database, provider):
        user = await get_or_create_user(db, "lesson_tg")
        await record_lesson(
            db, user.id, "2026-03-25",
            block=2, story_type="alltag", theme="Einkaufen",
            grammar_topic="Akkusativ",
        )
        result = await provider("lesson_tg")
        assert "[2026-03-25]" in result
        assert "Block 2 (Core)" in result
        assert "Type: alltag" in result
        assert "Theme: Einkaufen" in result
        assert "Grammar: Akkusativ" in result

    @pytest.mark.asyncio
    async def test_lesson_history_multiple(self, db: Database, provider):
        user = await get_or_create_user(db, "multi_lesson_tg")
        await record_lesson(db, user.id, "2026-03-24", block=1)
        await record_lesson(db, user.id, "2026-03-25", block=2)
        result = await provider("multi_lesson_tg")
        assert "[2026-03-24]" in result
        assert "[2026-03-25]" in result

    @pytest.mark.asyncio
    async def test_lesson_block_names(self, db: Database, provider):
        user = await get_or_create_user(db, "block_tg")
        await record_lesson(db, user.id, "2026-03-25", block=1)
        await record_lesson(db, user.id, "2026-03-25", block=3)
        result = await provider("block_tg")
        assert "Warm-up" in result
        assert "Recap" in result


# ---------------------------------------------------------------------------
# Difficulty signal thresholds
# ---------------------------------------------------------------------------


class TestDifficultySignal:
    """Difficulty signal changes based on accuracy thresholds."""

    async def _make_user_with_accuracy(
        self, db: Database, sender_id: str, correct: int, incorrect: int,
    ) -> None:
        """Helper: create a user with cards reviewed to achieve target accuracy."""
        user = await get_or_create_user(db, sender_id)
        card = await add_vocab_card(db, user.id, "Wort", "word")
        for _ in range(correct):
            await update_card_review(db, card.id, correct=True)
        for _ in range(incorrect):
            await update_card_review(db, card.id, correct=False)

    @pytest.mark.asyncio
    async def test_strong_signal(self, db: Database, provider):
        # 9/10 = 90% -> STRONG
        await self._make_user_with_accuracy(db, "strong_tg", 9, 1)
        result = await provider("strong_tg")
        assert "STRONG" in result

    @pytest.mark.asyncio
    async def test_on_track_signal(self, db: Database, provider):
        # 7/10 = 70% -> ON TRACK (and < 85%)
        await self._make_user_with_accuracy(db, "ontrack_tg", 7, 3)
        result = await provider("ontrack_tg")
        assert "ON TRACK" in result

    @pytest.mark.asyncio
    async def test_struggling_signal(self, db: Database, provider):
        # 5/10 = 50% -> STRUGGLING
        await self._make_user_with_accuracy(db, "struggle_tg", 5, 5)
        result = await provider("struggle_tg")
        assert "STRUGGLING" in result

    @pytest.mark.asyncio
    async def test_needs_support_signal(self, db: Database, provider):
        # 2/10 = 20% -> NEEDS SUPPORT
        await self._make_user_with_accuracy(db, "support_tg", 2, 8)
        result = await provider("support_tg")
        assert "NEEDS SUPPORT" in result

    @pytest.mark.asyncio
    async def test_no_reviews_no_signal(self, db: Database, provider):
        user = await get_or_create_user(db, "norev_tg")
        # Add card but don't review
        await add_vocab_card(db, user.id, "Apfel", "apple")
        result = await provider("norev_tg")
        assert "Not enough data" in result


# ---------------------------------------------------------------------------
# Section independence — each section survives failures in others
# ---------------------------------------------------------------------------


class TestSectionIndependence:
    """Each section must work independently; failures don't cascade."""

    @pytest.mark.asyncio
    async def test_has_all_sections(self, db: Database, provider):
        """Verify all major sections appear in the output."""
        user = await get_or_create_user(db, "sections_tg", "Sections")
        await update_progress(db, user.id, words_learned=10, current_streak=2)
        await add_vocab_card(db, user.id, "Hallo", "hello")
        await record_lesson(db, user.id, "2026-03-25", block=1)

        result = await provider("sections_tg")
        assert "### Student Profile" in result
        assert "### Curriculum Position" in result
        assert "### Engagement" in result
        assert "### SRS Review Stats" in result
        assert "### Last Lesson" in result
        assert "### Difficulty Signal" in result

    @pytest.mark.asyncio
    async def test_output_ends_with_newline(self, provider):
        result = await provider("newline_tg")
        assert result.endswith("\n")


# ---------------------------------------------------------------------------
# Multi-user correctness
# ---------------------------------------------------------------------------


class TestMultiUser:
    """Two users must receive different contexts."""

    @pytest.mark.asyncio
    async def test_two_users_get_different_contexts(self, db: Database, provider):
        alice = await get_or_create_user(db, "alice_multi", "Alice")
        bob = await get_or_create_user(db, "bob_multi", "Bob")

        await update_user(db, alice.id, cefr_level="A2")
        await update_user(db, bob.id, cefr_level="B1")

        await update_progress(db, alice.id, words_learned=200, current_streak=14)
        await update_progress(db, bob.id, words_learned=50, current_streak=3)

        await add_vocab_card(db, alice.id, "Apfel", "apple")
        await add_vocab_card(db, alice.id, "Birne", "pear")
        await add_vocab_card(db, bob.id, "Wasser", "water")

        alice_ctx = await provider("alice_multi")
        bob_ctx = await provider("bob_multi")

        assert "Alice" in alice_ctx
        assert "Bob" in bob_ctx
        assert "Alice" not in bob_ctx
        assert "Bob" not in alice_ctx

        assert "CEFR Level: A2" in alice_ctx
        assert "CEFR Level: B1" in bob_ctx

        assert "Words Learned: 200" in alice_ctx
        assert "Words Learned: 50" in bob_ctx

        assert "Current Streak: 14" in alice_ctx
        assert "Current Streak: 3" in bob_ctx

        # SRS: Alice has 2 cards, Bob has 1
        assert "Total Cards: 2" in alice_ctx
        assert "Total Cards: 1" in bob_ctx
