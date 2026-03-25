"""Context provider for lesson interactions.

Compiles a 'teacher's notebook' that the LLM receives before every
interaction, giving it full awareness of the student's state.
"""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING, Awaitable, Callable

from loguru import logger

if TYPE_CHECKING:
    from src.db.connection import Database


def make_lesson_context_provider(
    db: Database,
) -> Callable[[str], Awaitable[str]]:
    """Create an async context provider for lesson interactions.

    Returns a coroutine that takes ``sender_id`` (Telegram user ID) and
    produces a Teacher's Notebook markdown block with student profile,
    progress, SRS stats, and difficulty signal.

    The provider degrades gracefully: if any section fails, it is skipped
    rather than crashing the entire context build.
    """

    async def provider(sender_id: str) -> str:
        from src.db.queries import (
            get_cards_due,
            get_or_create_user,
            get_user_progress,
        )

        try:
            user = await get_or_create_user(db, sender_id)
        except Exception:
            logger.debug("lesson_context: could not resolve user for {}", sender_id)
            return ""  # Graceful degradation

        lines: list[str] = ["## Teacher's Notebook"]

        # ---------------------------------------------------------------
        # 1. Student Profile
        # ---------------------------------------------------------------
        lines.append("")
        lines.append("### Student Profile")
        lines.append(f"- Name: {user.display_name or 'Unknown'}")
        lines.append(f"- CEFR Level: {user.cefr_level}")
        lines.append(f"- Native Language: {user.native_language or 'unknown'}")
        lines.append(f"- Timezone: {user.timezone or 'unknown'}")
        if user.interests:
            try:
                interests = (
                    json.loads(user.interests)
                    if isinstance(user.interests, str) and user.interests.startswith("[")
                    else [user.interests]
                )
                lines.append(f"- Interests: {', '.join(str(i) for i in interests)}")
            except (json.JSONDecodeError, TypeError):
                lines.append(f"- Interests: {user.interests}")
        lines.append(f"- Daily Goal: {user.daily_goal_minutes} min")
        lines.append(f"- Preferred Time: {user.preferred_lesson_time or 'not set'}")
        onboarding_status = "complete" if user.onboarding_complete else (
            "NOT complete — run onboarding first!"
        )
        lines.append(f"- Onboarding: {onboarding_status}")

        # ---------------------------------------------------------------
        # 2. Curriculum Position
        # ---------------------------------------------------------------
        progress = None
        try:
            progress = await get_user_progress(db, user.id)
        except Exception:
            logger.debug("lesson_context: failed to fetch progress for user {}", user.id)

        lines.append("")
        lines.append("### Curriculum Position")
        if progress:
            lines.append(f"- Level: {progress.cefr_level}")
            lines.append(f"- Theme: {progress.theme_index}/15")
            lines.append(f"- Grammar: {progress.grammar_index}/15")
            lines.append(f"- Phase: {progress.phase}, Week: {progress.week_number}")
            lines.append(f"- Words Learned: {progress.words_learned}")
            lines.append(f"- Lessons Completed: {progress.lessons_completed}")
        else:
            lines.append("- No progress data yet — this is a new student")

        # ---------------------------------------------------------------
        # 3. Streak & Last Lesson
        # ---------------------------------------------------------------
        lines.append("")
        lines.append("### Engagement")
        if progress:
            lines.append(f"- Current Streak: {progress.current_streak} days")
            lines.append(f"- Longest Streak: {progress.longest_streak} days")
            if progress.last_lesson_date:
                try:
                    last = date.fromisoformat(progress.last_lesson_date)
                    days_ago = (date.today() - last).days
                    if days_ago == 0:
                        lines.append("- Last Lesson: today")
                    elif days_ago == 1:
                        lines.append("- Last Lesson: yesterday")
                    else:
                        lines.append(f"- Last Lesson: {days_ago} days ago")
                        if days_ago >= 3:
                            lines.append(
                                "  → Student has been away"
                                " — welcome back warmly, quick review first"
                            )
                except ValueError:
                    lines.append(f"- Last Lesson: {progress.last_lesson_date}")
            else:
                lines.append("- Last Lesson: never")
        else:
            lines.append("- No engagement data yet")

        # ---------------------------------------------------------------
        # 4. SRS Review Stats
        # ---------------------------------------------------------------
        total_reviews = 0
        accuracy = 0.0
        lines.append("")
        lines.append("### SRS Review Stats")
        try:
            due_cards = await get_cards_due(db, user.id, limit=200)
            total_due = len(due_cards)
            new_cards = sum(1 for c in due_cards if c.next_review is None)
            review_cards = total_due - new_cards

            all_cards_rows = await db.fetchall(
                "SELECT review_count, correct_count, interval_days "
                "FROM vocab_cards WHERE user_id = ?",
                (user.id,),
            )
            total_cards = len(all_cards_rows)
            total_reviews = sum(c["review_count"] for c in all_cards_rows)
            total_correct = sum(c["correct_count"] for c in all_cards_rows)
            accuracy = (total_correct / total_reviews * 100) if total_reviews > 0 else 0.0
            mature_cards = sum(1 for c in all_cards_rows if c["interval_days"] >= 14)

            lines.append(f"- Total Cards: {total_cards}")
            lines.append(
                f"- Due Today: {total_due} ({new_cards} new, {review_cards} review)"
            )
            lines.append(f"- Overall Accuracy: {accuracy:.0f}%")
            lines.append(f"- Mature Cards (≥14d): {mature_cards}")
        except Exception:
            logger.debug("lesson_context: SRS stats unavailable for user {}", user.id)
            lines.append("- No SRS data available yet")

        # ---------------------------------------------------------------
        # 5. Last Lesson Summary
        # ---------------------------------------------------------------
        lines.append("")
        lines.append("### Last Lesson")
        try:
            last_lessons = await db.fetchall(
                "SELECT lesson_date, block, story_type, theme, grammar_topic "
                "FROM lesson_records WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT 3",
                (user.id,),
            )
            if last_lessons:
                block_names = {1: "Warm-up", 2: "Core", 3: "Recap"}
                for lesson in last_lessons:
                    parts: list[str] = []
                    if lesson.get("story_type"):
                        parts.append(f"Type: {lesson['story_type']}")
                    if lesson.get("theme"):
                        parts.append(f"Theme: {lesson['theme']}")
                    if lesson.get("grammar_topic"):
                        parts.append(f"Grammar: {lesson['grammar_topic']}")
                    block_label = block_names.get(lesson.get("block"), "")
                    detail = ", ".join(parts) if parts else "no details"
                    lines.append(
                        f"- [{lesson['lesson_date']}] "
                        f"Block {lesson.get('block', '?')} ({block_label}): {detail}"
                    )
            else:
                lines.append("- No lessons recorded yet")
        except Exception:
            logger.debug(
                "lesson_context: lesson history unavailable for user {}", user.id,
            )
            lines.append("- No lesson history available")

        # ---------------------------------------------------------------
        # 6. Difficulty Signal
        # ---------------------------------------------------------------
        lines.append("")
        lines.append("### Difficulty Signal")
        if total_reviews > 0:
            if accuracy >= 85:
                lines.append("- Performance: STRONG — consider increasing difficulty")
            elif accuracy >= 70:
                lines.append("- Performance: ON TRACK — maintain current difficulty")
            elif accuracy >= 50:
                lines.append("- Performance: STRUGGLING — slow down, more review")
            else:
                lines.append("- Performance: NEEDS SUPPORT — simplify, more repetition")
        else:
            lines.append("- Not enough data for difficulty assessment")

        return "\n".join(lines) + "\n"

    return provider
