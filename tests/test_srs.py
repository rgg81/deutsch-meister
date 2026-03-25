"""Tests for the SRS engine and tool."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.db.connection import Database
from src.db.queries import add_vocab_card, get_or_create_user
from src.srs.engine import (
    DEFAULT_EASE,
    EASE_MAX,
    EASE_MIN,
    INTERVALS,
    ReviewResult,
    compute_next_review,
    split_due_cards,
)
from src.srs.tool import SRSTool


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
async def user(db):
    """Create a test user."""
    return await get_or_create_user(db, "test_user_42", "TestUser")


@pytest.fixture
async def tool(db):
    """Create an SRSTool with user context set."""
    t = SRSTool(db)
    t.set_user_context("test_user_42")
    return t


# ===========================================================================
# Engine tests — pure logic, no DB
# ===========================================================================


class TestComputeNextReview:
    """Test the fixed-interval scheduling logic."""

    REVIEW_DATE = date(2026, 3, 25)

    def test_new_card_correct_advances_to_first_interval(self):
        """interval_days=0 (new card), correct -> interval=1."""
        result = compute_next_review(0, correct=True, review_date=self.REVIEW_DATE)
        assert result.new_interval_days == INTERVALS[0]  # 1
        assert result.next_review == self.REVIEW_DATE + timedelta(days=1)

    def test_interval_1_correct_advances_to_3(self):
        result = compute_next_review(1, correct=True, review_date=self.REVIEW_DATE)
        assert result.new_interval_days == 3

    def test_interval_3_correct_advances_to_7(self):
        result = compute_next_review(3, correct=True, review_date=self.REVIEW_DATE)
        assert result.new_interval_days == 7

    def test_interval_7_correct_advances_to_14(self):
        result = compute_next_review(7, correct=True, review_date=self.REVIEW_DATE)
        assert result.new_interval_days == 14

    def test_interval_14_correct_advances_to_30(self):
        result = compute_next_review(14, correct=True, review_date=self.REVIEW_DATE)
        assert result.new_interval_days == 30

    def test_interval_30_correct_stays_at_30(self):
        """At the max interval, correct answers keep it at 30."""
        result = compute_next_review(30, correct=True, review_date=self.REVIEW_DATE)
        assert result.new_interval_days == 30
        assert result.next_review == self.REVIEW_DATE + timedelta(days=30)

    def test_incorrect_resets_to_1(self):
        """Any incorrect answer resets to interval=1."""
        for interval in [0, 1, 3, 7, 14, 30]:
            result = compute_next_review(
                interval, correct=False, review_date=self.REVIEW_DATE
            )
            assert result.new_interval_days == INTERVALS[0]  # 1
            assert result.next_review == self.REVIEW_DATE + timedelta(days=1)

    def test_unknown_interval_finds_nearest_larger(self):
        """If current interval is 5 (not in INTERVALS), advance to 7."""
        result = compute_next_review(5, correct=True, review_date=self.REVIEW_DATE)
        assert result.new_interval_days == 7

    def test_unknown_interval_larger_than_all_caps_at_max(self):
        """If current interval is 50, cap at 30."""
        result = compute_next_review(50, correct=True, review_date=self.REVIEW_DATE)
        assert result.new_interval_days == 30

    def test_next_review_date_is_correct(self):
        result = compute_next_review(3, correct=True, review_date=self.REVIEW_DATE)
        assert result.next_review == self.REVIEW_DATE + timedelta(days=7)

    def test_defaults_to_today_when_no_review_date(self):
        result = compute_next_review(1, correct=True)
        assert result.next_review == date.today() + timedelta(days=3)


class TestEaseFactor:
    """Test ease factor adjustments."""

    def test_correct_increases_ease(self):
        result = compute_next_review(1, correct=True, ease_factor=2.5)
        assert result.ease_factor == pytest.approx(2.6, abs=0.01)

    def test_incorrect_decreases_ease(self):
        result = compute_next_review(1, correct=False, ease_factor=2.5)
        assert result.ease_factor == pytest.approx(2.3, abs=0.01)

    def test_ease_never_below_minimum(self):
        result = compute_next_review(1, correct=False, ease_factor=EASE_MIN)
        assert result.ease_factor >= EASE_MIN

    def test_ease_never_above_maximum(self):
        result = compute_next_review(1, correct=True, ease_factor=EASE_MAX)
        assert result.ease_factor <= EASE_MAX

    def test_repeated_incorrect_floors_at_minimum(self):
        ease = DEFAULT_EASE
        for _ in range(20):
            result = compute_next_review(1, correct=False, ease_factor=ease)
            ease = result.ease_factor
        assert ease >= EASE_MIN

    def test_repeated_correct_caps_at_maximum(self):
        ease = DEFAULT_EASE
        for _ in range(20):
            result = compute_next_review(1, correct=True, ease_factor=ease)
            ease = result.ease_factor
        assert ease <= EASE_MAX


class TestSplitDueCards:
    """Test due card splitting with configurable limits."""

    class FakeCard:
        """Minimal card-like object for testing split logic."""

        def __init__(self, card_id: int, next_review: str | None):
            self.id = card_id
            self.next_review = next_review

    def test_separates_new_and_review(self):
        cards = [
            self.FakeCard(1, None),       # new
            self.FakeCard(2, None),       # new
            self.FakeCard(3, "2026-03-25"),  # review
            self.FakeCard(4, "2026-03-20"),  # review
        ]
        new, review = split_due_cards(cards)
        assert len(new) == 2
        assert len(review) == 2

    def test_new_limit(self):
        cards = [self.FakeCard(i, None) for i in range(15)]
        new, review = split_due_cards(cards, new_limit=5)
        assert len(new) == 5
        assert len(review) == 0

    def test_review_limit(self):
        cards = [self.FakeCard(i, "2026-03-25") for i in range(40)]
        new, review = split_due_cards(cards, review_limit=10)
        assert len(new) == 0
        assert len(review) == 10

    def test_both_limits_applied(self):
        cards = [
            *[self.FakeCard(i, None) for i in range(15)],
            *[self.FakeCard(100 + i, "2026-03-25") for i in range(40)],
        ]
        new, review = split_due_cards(cards, new_limit=5, review_limit=10)
        assert len(new) == 5
        assert len(review) == 10

    def test_empty_cards(self):
        new, review = split_due_cards([])
        assert new == []
        assert review == []

    def test_all_new_cards(self):
        cards = [self.FakeCard(i, None) for i in range(3)]
        new, review = split_due_cards(cards, new_limit=10, review_limit=30)
        assert len(new) == 3
        assert len(review) == 0

    def test_all_review_cards(self):
        cards = [self.FakeCard(i, "2026-03-25") for i in range(3)]
        new, review = split_due_cards(cards, new_limit=10, review_limit=30)
        assert len(new) == 0
        assert len(review) == 3


# ===========================================================================
# Tool tests — integration with real DB
# ===========================================================================


class TestSRSToolGetDue:
    """Test the get_due action."""

    @pytest.mark.asyncio
    async def test_get_due_no_cards(self, tool: SRSTool, user, db: Database):
        result = await tool.execute(action="get_due")
        assert "No cards due" in result

    @pytest.mark.asyncio
    async def test_get_due_returns_new_cards(self, tool: SRSTool, user, db: Database):
        await add_vocab_card(db, user.id, "Hund", "dog", gender="der")
        await add_vocab_card(db, user.id, "Katze", "cat", gender="die")
        result = await tool.execute(action="get_due")
        assert "New cards (2)" in result
        assert "Hund" in result
        assert "Katze" in result
        assert "(der)" in result

    @pytest.mark.asyncio
    async def test_get_due_returns_review_cards(
        self, tool: SRSTool, user, db: Database
    ):
        card = await add_vocab_card(db, user.id, "Haus", "house")
        # Set next_review to today (making it a review card, not new)
        today = date.today().isoformat()
        await db.execute(
            "UPDATE vocab_cards SET next_review = ? WHERE id = ?",
            (today, card.id),
        )
        await db.commit()
        result = await tool.execute(action="get_due")
        assert "Review cards (1)" in result
        assert "Haus" in result

    @pytest.mark.asyncio
    async def test_get_due_respects_limit(self, tool: SRSTool, user, db: Database):
        for i in range(10):
            await add_vocab_card(db, user.id, f"Wort{i}", f"word{i}")
        result = await tool.execute(action="get_due", limit=3)
        assert "Total: 3 cards" in result

    @pytest.mark.asyncio
    async def test_get_due_shows_total(self, tool: SRSTool, user, db: Database):
        await add_vocab_card(db, user.id, "Buch", "book")
        result = await tool.execute(action="get_due")
        assert "Total: 1 cards" in result


class TestSRSToolRecordAnswer:
    """Test the record_answer action."""

    @pytest.mark.asyncio
    async def test_record_correct_answer(self, tool: SRSTool, user, db: Database):
        card = await add_vocab_card(db, user.id, "Hund", "dog")
        result = await tool.execute(
            action="record_answer", card_id=card.id, correct=True
        )
        assert "Correct!" in result
        assert "1 day(s)" in result

        # Verify DB was updated
        row = await db.fetchone(
            "SELECT * FROM vocab_cards WHERE id = ?", (card.id,)
        )
        assert row["interval_days"] == 1
        assert row["review_count"] == 1
        assert row["correct_count"] == 1

    @pytest.mark.asyncio
    async def test_record_incorrect_answer(self, tool: SRSTool, user, db: Database):
        card = await add_vocab_card(db, user.id, "Katze", "cat")
        # First get it to interval 3
        await tool.execute(action="record_answer", card_id=card.id, correct=True)
        await tool.execute(action="record_answer", card_id=card.id, correct=True)

        result = await tool.execute(
            action="record_answer", card_id=card.id, correct=False
        )
        assert "Incorrect." in result
        assert "1 day(s)" in result

        row = await db.fetchone(
            "SELECT * FROM vocab_cards WHERE id = ?", (card.id,)
        )
        assert row["interval_days"] == 1

    @pytest.mark.asyncio
    async def test_record_answer_full_interval_ladder(
        self, tool: SRSTool, user, db: Database
    ):
        """Walk through all interval steps: 0->1->3->7->14->30."""
        card = await add_vocab_card(db, user.id, "Stuhl", "chair")

        expected_intervals = [1, 3, 7, 14, 30]
        for expected in expected_intervals:
            await tool.execute(
                action="record_answer", card_id=card.id, correct=True
            )
            row = await db.fetchone(
                "SELECT * FROM vocab_cards WHERE id = ?", (card.id,)
            )
            assert row["interval_days"] == expected

    @pytest.mark.asyncio
    async def test_record_answer_missing_card_id(self, tool: SRSTool, user):
        result = await tool.execute(action="record_answer", correct=True)
        assert "Error" in result
        assert "card_id" in result

    @pytest.mark.asyncio
    async def test_record_answer_missing_correct(self, tool: SRSTool, user):
        result = await tool.execute(action="record_answer", card_id=1)
        assert "Error" in result
        assert "correct" in result

    @pytest.mark.asyncio
    async def test_record_answer_wrong_user(
        self, tool: SRSTool, user, db: Database
    ):
        """Cannot record answer for a card owned by another user."""
        other = await get_or_create_user(db, "other_user")
        card = await add_vocab_card(db, other.id, "Tisch", "table")
        result = await tool.execute(
            action="record_answer", card_id=card.id, correct=True
        )
        assert "not found" in result


class TestSRSToolAddCard:
    """Test the add_card action."""

    @pytest.mark.asyncio
    async def test_add_card(self, tool: SRSTool, user, db: Database):
        result = await tool.execute(
            action="add_card",
            word_de="der Hund",
            word_en="the dog",
            gender="der",
            part_of_speech="noun",
        )
        assert "Added card" in result
        assert "der Hund" in result
        assert "(der)" in result
        assert "[noun]" in result

    @pytest.mark.asyncio
    async def test_add_card_minimal(self, tool: SRSTool, user, db: Database):
        result = await tool.execute(
            action="add_card",
            word_de="schnell",
            word_en="fast",
        )
        assert "Added card" in result
        assert "schnell" in result

    @pytest.mark.asyncio
    async def test_add_card_with_example(self, tool: SRSTool, user, db: Database):
        result = await tool.execute(
            action="add_card",
            word_de="laufen",
            word_en="to run",
            part_of_speech="verb",
            example_sentence="Ich laufe jeden Morgen.",
        )
        assert "Added card" in result

    @pytest.mark.asyncio
    async def test_add_card_missing_word_de(self, tool: SRSTool, user):
        result = await tool.execute(action="add_card", word_en="dog")
        assert "Error" in result
        assert "word_de" in result

    @pytest.mark.asyncio
    async def test_add_card_missing_word_en(self, tool: SRSTool, user):
        result = await tool.execute(action="add_card", word_de="Hund")
        assert "Error" in result
        assert "word_en" in result


class TestSRSToolGetStats:
    """Test the get_stats action."""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, tool: SRSTool, user, db: Database):
        result = await tool.execute(action="get_stats")
        assert "Total cards: 0" in result
        assert "Accuracy: 0.0%" in result

    @pytest.mark.asyncio
    async def test_get_stats_with_data(self, tool: SRSTool, user, db: Database):
        card = await add_vocab_card(db, user.id, "Hund", "dog")
        await tool.execute(action="record_answer", card_id=card.id, correct=True)
        await tool.execute(action="record_answer", card_id=card.id, correct=True)
        await tool.execute(action="record_answer", card_id=card.id, correct=False)

        result = await tool.execute(action="get_stats")
        assert "Total cards: 1" in result
        assert "Total reviews: 3" in result
        assert "Correct answers: 2" in result
        assert "66.7%" in result

    @pytest.mark.asyncio
    async def test_get_stats_mature_count(self, tool: SRSTool, user, db: Database):
        card = await add_vocab_card(db, user.id, "Haus", "house")
        # Manually set to a mature interval
        await db.execute(
            "UPDATE vocab_cards SET interval_days = 14 WHERE id = ?",
            (card.id,),
        )
        await db.commit()

        result = await tool.execute(action="get_stats")
        assert "Mature cards (14+ day interval): 1" in result


class TestSRSToolEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_no_user_context(self, db: Database):
        tool = SRSTool(db)
        # Do NOT call set_user_context
        result = await tool.execute(action="get_due")
        assert "Error: No user context" in result

    @pytest.mark.asyncio
    async def test_unknown_action(self, tool: SRSTool, user):
        result = await tool.execute(action="nonexistent")
        assert "Unknown action" in result

    @pytest.mark.asyncio
    async def test_tool_name(self, tool: SRSTool):
        assert tool.name == "srs"

    @pytest.mark.asyncio
    async def test_tool_description(self, tool: SRSTool):
        desc = tool.description
        assert "get_due" in desc
        assert "record_answer" in desc
        assert "add_card" in desc
        assert "get_stats" in desc

    @pytest.mark.asyncio
    async def test_tool_parameters_schema(self, tool: SRSTool):
        params = tool.parameters
        assert params["type"] == "object"
        assert "action" in params["properties"]
        assert params["properties"]["action"]["enum"] == [
            "get_due", "record_answer", "add_card", "get_stats"
        ]
        assert params["required"] == ["action"]

    @pytest.mark.asyncio
    async def test_tool_to_schema(self, tool: SRSTool):
        schema = tool.to_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "srs"
