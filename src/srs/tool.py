"""SRS review tool for the LLM agent.

Bridges the pure SRS engine logic with the database layer, exposing
spaced-repetition actions as a NanoBot :class:`Tool` that the agent can call.

Registration
------------
The tool is not yet auto-registered in the agent loop.  To wire it up,
instantiate with a connected :class:`Database` and register on the tool
registry::

    from src.srs.tool import SRSTool
    srs_tool = SRSTool(db)
    agent.tools.register(srs_tool)

The ``set_user_context`` method is called automatically by NanoBot before
each message, providing the sender's Telegram ID.
"""

from __future__ import annotations

from datetime import date
from typing import Any, TYPE_CHECKING

from nanobot.agent.tools.base import Tool

from src.srs.engine import compute_next_review, split_due_cards

if TYPE_CHECKING:
    from src.db.connection import Database


class SRSTool(Tool):
    """Tool for managing spaced repetition vocabulary reviews."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._sender_id: str | None = None

    def set_user_context(self, sender_id: str) -> None:
        """Store the current Telegram sender ID for per-user scoping."""
        self._sender_id = sender_id

    # ------------------------------------------------------------------
    # Tool schema
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "srs"

    @property
    def description(self) -> str:
        return (
            "Manage spaced repetition vocabulary reviews. Actions: "
            "'get_due' returns cards due for review today, "
            "'record_answer' records whether the student got a card correct/incorrect, "
            "'add_card' adds a new vocabulary card to the SRS deck, "
            "'get_stats' returns review statistics."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get_due", "record_answer", "add_card", "get_stats"],
                    "description": "The SRS action to perform",
                },
                "card_id": {
                    "type": "integer",
                    "description": "Card ID (for record_answer)",
                },
                "correct": {
                    "type": "boolean",
                    "description": "Whether the answer was correct (for record_answer)",
                },
                "word_de": {
                    "type": "string",
                    "description": "German word (for add_card)",
                },
                "word_en": {
                    "type": "string",
                    "description": "English translation (for add_card)",
                },
                "gender": {
                    "type": "string",
                    "description": (
                        "Grammatical gender: der/die/das (for add_card, nouns only)"
                    ),
                },
                "plural": {
                    "type": "string",
                    "description": "Plural form (for add_card)",
                },
                "part_of_speech": {
                    "type": "string",
                    "description": (
                        "Part of speech: noun/verb/adjective/etc (for add_card)"
                    ),
                },
                "example_sentence": {
                    "type": "string",
                    "description": "Example sentence (for add_card)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max cards to return (for get_due, default 20)",
                },
            },
            "required": ["action"],
        }

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(self, action: str, **kwargs: Any) -> str:
        """Dispatch to the appropriate SRS action handler."""
        if not self._sender_id:
            return "Error: No user context set."

        from src.db.queries import get_or_create_user

        user = await get_or_create_user(self._db, self._sender_id)

        handlers = {
            "get_due": self._get_due,
            "record_answer": self._record_answer,
            "add_card": self._add_card,
            "get_stats": self._get_stats,
        }

        handler = handlers.get(action)
        if handler is None:
            return f"Error: Unknown action '{action}'"

        try:
            return await handler(user_id=user.id, **kwargs)
        except Exception as exc:
            return f"Error in srs.{action}: {exc}"

    # ------------------------------------------------------------------
    # Private action handlers
    # ------------------------------------------------------------------

    async def _get_due(
        self,
        user_id: int,
        limit: int = 20,
        **_: Any,
    ) -> str:
        """Return cards due for review, split into new / review buckets."""
        from src.db.queries import get_cards_due

        cards = await get_cards_due(self._db, user_id, limit=limit)

        if not cards:
            return "No cards due for review today. Great job staying on top of things!"

        new_cards, review_cards = split_due_cards(cards, new_limit=10, review_limit=30)

        lines: list[str] = []
        if new_cards:
            lines.append(f"New cards ({len(new_cards)}):")
            for c in new_cards:
                gender_str = f" ({c.gender})" if c.gender else ""
                lines.append(f"  [#{c.id}] {c.word_de}{gender_str} - {c.word_en}")
        if review_cards:
            lines.append(f"Review cards ({len(review_cards)}):")
            for c in review_cards:
                gender_str = f" ({c.gender})" if c.gender else ""
                lines.append(f"  [#{c.id}] {c.word_de}{gender_str} - {c.word_en}")

        total = len(new_cards) + len(review_cards)
        lines.append(f"\nTotal: {total} cards ready for review.")
        return "\n".join(lines)

    async def _record_answer(
        self,
        user_id: int,
        card_id: int | None = None,
        correct: bool | None = None,
        **_: Any,
    ) -> str:
        """Record a review answer and update the card's schedule."""
        if card_id is None:
            return "Error: card_id is required for record_answer."
        if correct is None:
            return "Error: correct is required for record_answer."

        # Fetch the card to verify ownership and get current state
        row = await self._db.fetchone(
            "SELECT * FROM vocab_cards WHERE id = ? AND user_id = ?",
            (card_id, user_id),
        )
        if row is None:
            return f"Error: Card #{card_id} not found for this user."

        # Compute new schedule using the pure engine
        result = compute_next_review(
            current_interval=row["interval_days"],
            correct=correct,
            ease_factor=row["ease_factor"],
            review_date=date.today(),
        )

        review_count = row["review_count"] + 1
        correct_count = row["correct_count"] + (1 if correct else 0)

        await self._db.execute(
            "UPDATE vocab_cards SET "
            "interval_days = ?, ease_factor = ?, next_review = ?, "
            "review_count = ?, correct_count = ?, updated_at = datetime('now') "
            "WHERE id = ?",
            (
                result.new_interval_days,
                result.ease_factor,
                result.next_review.isoformat(),
                review_count,
                correct_count,
                card_id,
            ),
        )
        await self._db.commit()

        verdict = "Correct!" if correct else "Incorrect."
        return (
            f"{verdict} Card #{card_id} ('{row['word_de']}') "
            f"next review in {result.new_interval_days} day(s) "
            f"({result.next_review.isoformat()})."
        )

    async def _add_card(
        self,
        user_id: int,
        word_de: str | None = None,
        word_en: str | None = None,
        gender: str | None = None,
        plural: str | None = None,
        part_of_speech: str | None = None,
        example_sentence: str | None = None,
        **_: Any,
    ) -> str:
        """Add a new vocabulary card to the user's SRS deck."""
        if not word_de:
            return "Error: word_de is required for add_card."
        if not word_en:
            return "Error: word_en is required for add_card."

        from src.db.queries import add_vocab_card

        card = await add_vocab_card(
            self._db,
            user_id,
            word_de,
            word_en,
            gender=gender,
            plural=plural,
            part_of_speech=part_of_speech,
            example_sentence=example_sentence,
        )

        gender_str = f" ({card.gender})" if card.gender else ""
        pos_str = f" [{card.part_of_speech}]" if card.part_of_speech else ""
        return (
            f"Added card #{card.id}: {card.word_de}{gender_str} - "
            f"{card.word_en}{pos_str}. It will appear in your next review session."
        )

    async def _get_stats(self, user_id: int, **_: Any) -> str:
        """Return review statistics for the user."""
        total_row = await self._db.fetchone(
            "SELECT COUNT(*) AS total FROM vocab_cards WHERE user_id = ?",
            (user_id,),
        )
        total = total_row["total"] if total_row else 0

        today = date.today().isoformat()
        due_row = await self._db.fetchone(
            "SELECT COUNT(*) AS due FROM vocab_cards "
            "WHERE user_id = ? AND (next_review IS NULL OR next_review <= ?)",
            (user_id, today),
        )
        due = due_row["due"] if due_row else 0

        review_row = await self._db.fetchone(
            "SELECT COALESCE(SUM(review_count), 0) AS reviews, "
            "COALESCE(SUM(correct_count), 0) AS correct "
            "FROM vocab_cards WHERE user_id = ?",
            (user_id,),
        )
        reviews = review_row["reviews"] if review_row else 0
        correct_total = review_row["correct"] if review_row else 0
        accuracy = (correct_total / reviews * 100) if reviews > 0 else 0.0

        mature_row = await self._db.fetchone(
            "SELECT COUNT(*) AS mature FROM vocab_cards "
            "WHERE user_id = ? AND interval_days >= 14",
            (user_id,),
        )
        mature = mature_row["mature"] if mature_row else 0

        stats = {
            "total_cards": total,
            "due_today": due,
            "total_reviews": reviews,
            "correct_answers": correct_total,
            "accuracy_pct": round(accuracy, 1),
            "mature_cards": mature,
        }

        lines = [
            "SRS Statistics:",
            f"  Total cards: {total}",
            f"  Due today: {due}",
            f"  Total reviews: {reviews}",
            f"  Correct answers: {correct_total}",
            f"  Accuracy: {stats['accuracy_pct']}%",
            f"  Mature cards (14+ day interval): {mature}",
        ]
        return "\n".join(lines)
