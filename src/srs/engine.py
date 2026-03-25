"""SRS engine: spaced repetition scheduling logic.

Pure computation module -- no database imports. Takes data, returns decisions.
Uses SM-2-inspired fixed intervals for predictable, simple scheduling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# Fixed interval ladder (in days). Correct answers advance one step;
# incorrect answers reset to the first step.
INTERVALS: list[int] = [1, 3, 7, 14, 30]

DEFAULT_EASE: float = 2.5
EASE_MIN: float = 1.3
EASE_MAX: float = 3.0
EASE_BONUS: float = 0.1
EASE_PENALTY: float = 0.2


@dataclass
class ReviewResult:
    """Result of processing a single review answer."""

    new_interval_days: int
    next_review: date
    ease_factor: float


def compute_next_review(
    current_interval: int,
    correct: bool,
    ease_factor: float = DEFAULT_EASE,
    review_date: date | None = None,
) -> ReviewResult:
    """Compute the next review date based on answer correctness.

    SM-2-inspired fixed intervals for v1:
    - Correct: advance to the next interval in :data:`INTERVALS`.
    - Incorrect: reset to the first interval (1 day).

    Args:
        current_interval: The card's current ``interval_days`` value.
        correct: Whether the student answered correctly.
        ease_factor: The card's current ease factor.
        review_date: Override for "today" (useful in tests).

    Returns:
        A :class:`ReviewResult` with the new scheduling parameters.
    """
    today = review_date or date.today()

    if not correct:
        new_ease = max(EASE_MIN, ease_factor - EASE_PENALTY)
        return ReviewResult(
            new_interval_days=INTERVALS[0],
            next_review=today + timedelta(days=INTERVALS[0]),
            ease_factor=new_ease,
        )

    # Find the next interval step
    try:
        idx = INTERVALS.index(current_interval)
        next_idx = min(idx + 1, len(INTERVALS) - 1)
    except ValueError:
        # Current interval is not in the fixed list -- find the nearest larger step.
        next_idx = len(INTERVALS) - 1  # default: cap at max
        for i, iv in enumerate(INTERVALS):
            if iv > current_interval:
                next_idx = i
                break

    new_interval = INTERVALS[next_idx]
    new_ease = min(EASE_MAX, ease_factor + EASE_BONUS)

    return ReviewResult(
        new_interval_days=new_interval,
        next_review=today + timedelta(days=new_interval),
        ease_factor=new_ease,
    )


def split_due_cards(
    cards: list,
    new_limit: int = 10,
    review_limit: int = 30,
) -> tuple[list, list]:
    """Split due cards into *new* and *review* buckets, applying respective caps.

    A card is considered **new** if it has never been reviewed
    (``next_review is None``).  All other due cards are **reviews**.

    Args:
        cards: List of card objects (e.g. :class:`VocabCard`). Each must have
               a ``next_review`` attribute.
        new_limit: Maximum number of new cards to return.
        review_limit: Maximum number of review cards to return.

    Returns:
        A ``(new_cards, review_cards)`` tuple.
    """
    new_cards = [c for c in cards if c.next_review is None][:new_limit]
    review_cards = [c for c in cards if c.next_review is not None][:review_limit]
    return new_cards, review_cards
