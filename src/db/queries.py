"""CRUD query functions for the DeutschMeister database.

Every public function accepts a :class:`Database` instance as its first
argument and uses parameterised queries exclusively — no f-strings in SQL.
All data access is scoped by ``user_id``.
"""

from __future__ import annotations

from datetime import date, timedelta

from src.db.connection import Database
from src.db.models import LessonRecord, User, UserProgress, VocabCard


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

async def get_or_create_user(
    db: Database,
    telegram_id: str,
    display_name: str | None = None,
) -> User:
    """Return the user for *telegram_id*, creating one if it does not exist."""
    row = await db.fetchone(
        "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
    )
    if row:
        return User.from_row(row)

    await db.execute(
        "INSERT INTO users (telegram_id, display_name) VALUES (?, ?)",
        (telegram_id, display_name),
    )
    await db.commit()

    row = await db.fetchone(
        "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
    )
    assert row is not None  # just inserted
    return User.from_row(row)


async def update_user(db: Database, user_id: int, **fields: object) -> None:
    """Update arbitrary columns on a user row.

    Only columns present in the ``users`` table are accepted.
    """
    allowed = {
        "display_name", "cefr_level", "timezone", "native_language",
        "daily_goal_minutes", "preferred_lesson_time", "interests",
        "onboarding_complete",
    }
    to_update = {k: v for k, v in fields.items() if k in allowed}
    if not to_update:
        return
    to_update["updated_at"] = "datetime('now')"

    set_clause_parts: list[str] = []
    params: list[object] = []
    for col, val in to_update.items():
        if val == "datetime('now')":
            set_clause_parts.append(f"{col} = datetime('now')")
        else:
            set_clause_parts.append(f"{col} = ?")
            params.append(val)
    params.append(user_id)

    sql = f"UPDATE users SET {', '.join(set_clause_parts)} WHERE id = ?"  # noqa: E501
    await db.execute(sql, tuple(params))
    await db.commit()


# ---------------------------------------------------------------------------
# Vocab cards
# ---------------------------------------------------------------------------

async def add_vocab_card(
    db: Database,
    user_id: int,
    word_de: str,
    word_en: str,
    *,
    gender: str | None = None,
    plural: str | None = None,
    part_of_speech: str | None = None,
    example_sentence: str | None = None,
) -> VocabCard:
    """Insert a new vocabulary card and return it."""
    await db.execute(
        "INSERT INTO vocab_cards "
        "(user_id, word_de, word_en, gender, plural, part_of_speech, example_sentence) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, word_de, word_en, gender, plural, part_of_speech, example_sentence),
    )
    await db.commit()

    row = await db.fetchone(
        "SELECT * FROM vocab_cards WHERE user_id = ? AND word_de = ? ORDER BY id DESC LIMIT 1",
        (user_id, word_de),
    )
    assert row is not None
    return VocabCard.from_row(row)


async def get_cards_due(
    db: Database,
    user_id: int,
    limit: int = 20,
) -> list[VocabCard]:
    """Return cards due for review today (or with no scheduled date yet)."""
    today = date.today().isoformat()
    rows = await db.fetchall(
        "SELECT * FROM vocab_cards "
        "WHERE user_id = ? AND (next_review IS NULL OR next_review <= ?) "
        "ORDER BY next_review ASC "
        "LIMIT ?",
        (user_id, today, limit),
    )
    return [VocabCard.from_row(r) for r in rows]


async def update_card_review(db: Database, card_id: int, correct: bool) -> None:
    """Update a card after a review using a simplified SM-2 algorithm.

    * Correct: ``interval_days`` grows (1 -> 6 -> prior * ease), ease bumps +0.1.
    * Incorrect: ``interval_days`` resets to 0, ease drops by 0.2 (min 1.3).
    """
    row = await db.fetchone("SELECT * FROM vocab_cards WHERE id = ?", (card_id,))
    if row is None:
        return

    interval = row["interval_days"]
    ease = row["ease_factor"]
    review_count = row["review_count"] + 1
    correct_count = row["correct_count"] + (1 if correct else 0)

    if correct:
        if interval == 0:
            new_interval = 1
        elif interval == 1:
            new_interval = 6
        else:
            new_interval = round(interval * ease)
        ease = min(ease + 0.1, 3.0)
    else:
        new_interval = 0
        ease = max(ease - 0.2, 1.3)

    next_review = (date.today() + timedelta(days=new_interval)).isoformat()

    await db.execute(
        "UPDATE vocab_cards SET "
        "interval_days = ?, ease_factor = ?, next_review = ?, "
        "review_count = ?, correct_count = ?, updated_at = datetime('now') "
        "WHERE id = ?",
        (new_interval, ease, next_review, review_count, correct_count, card_id),
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Lesson records
# ---------------------------------------------------------------------------

async def record_lesson(
    db: Database,
    user_id: int,
    lesson_date: str,
    *,
    block: int | None = None,
    story_type: str | None = None,
    theme: str | None = None,
    grammar_topic: str | None = None,
    duration_minutes: int | None = None,
    completed: bool = False,
    notes: str | None = None,
) -> LessonRecord:
    """Insert a lesson record and return it."""
    await db.execute(
        "INSERT INTO lesson_records "
        "(user_id, lesson_date, block, story_type, theme, grammar_topic, "
        "duration_minutes, completed, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id, lesson_date, block, story_type, theme,
            grammar_topic, duration_minutes, int(completed), notes,
        ),
    )
    await db.commit()

    row = await db.fetchone(
        "SELECT * FROM lesson_records WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    )
    assert row is not None
    return LessonRecord.from_row(row)


# ---------------------------------------------------------------------------
# User progress
# ---------------------------------------------------------------------------

async def get_user_progress(db: Database, user_id: int) -> UserProgress | None:
    """Return the progress row for *user_id*, or ``None`` if none exists."""
    row = await db.fetchone(
        "SELECT * FROM user_progress WHERE user_id = ?", (user_id,)
    )
    return UserProgress.from_row(row) if row else None


async def update_progress(db: Database, user_id: int, **fields: object) -> None:
    """Upsert curriculum progress for a user.

    If no progress row exists yet, one is created with defaults before
    applying the requested updates.
    """
    allowed = {
        "cefr_level", "theme_index", "grammar_index", "phase",
        "week_number", "words_learned", "lessons_completed",
        "current_streak", "longest_streak", "last_lesson_date",
    }
    to_update = {k: v for k, v in fields.items() if k in allowed}

    existing = await db.fetchone(
        "SELECT id FROM user_progress WHERE user_id = ?", (user_id,)
    )
    if not existing:
        await db.execute(
            "INSERT INTO user_progress (user_id) VALUES (?)", (user_id,)
        )
        await db.commit()

    if not to_update:
        return

    set_clause_parts: list[str] = []
    params: list[object] = []
    for col, val in to_update.items():
        set_clause_parts.append(f"{col} = ?")
        params.append(val)
    set_clause_parts.append("updated_at = datetime('now')")
    params.append(user_id)

    sql = f"UPDATE user_progress SET {', '.join(set_clause_parts)} WHERE user_id = ?"  # noqa: E501
    await db.execute(sql, tuple(params))
    await db.commit()
