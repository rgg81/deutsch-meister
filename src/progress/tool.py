"""Progress tracking tool for the LLM agent.

Bridges the pure curriculum logic in :mod:`src.progress.tracker` with the
database layer in :mod:`src.db`, exposing a single NanoBot tool that the
LLM can call to read and write student progress.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from nanobot.agent.tools.base import Tool

from src.progress.tracker import compute_advance, get_position

if TYPE_CHECKING:
    from src.db.connection import Database


class ProgressTool(Tool):
    """Tool for tracking student curriculum progress.

    Provides four actions:

    * ``get_status`` — read current CEFR level, position, and stats.
    * ``advance``    — move to the next theme or grammar topic.
    * ``record_lesson`` — record a completed lesson and update streak.
    * ``set_level``  — manually set the CEFR level and reset position.
    """

    def __init__(self, db: Database) -> None:
        self._db = db
        self._sender_id: str | None = None

    def set_user_context(self, sender_id: str) -> None:
        """Set the Telegram user ID for scoping all DB operations."""
        self._sender_id = sender_id

    @property
    def name(self) -> str:
        return "progress"

    @property
    def description(self) -> str:
        return (
            "Track and manage student curriculum progress. Actions: "
            "'get_status' returns current CEFR level, position, and stats; "
            "'advance' moves to next theme or grammar topic; "
            "'record_lesson' records a completed lesson; "
            "'set_level' sets CEFR level manually."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get_status", "advance", "record_lesson", "set_level"],
                    "description": "The progress action to perform",
                },
                "advance_what": {
                    "type": "string",
                    "enum": ["theme", "grammar"],
                    "description": "What to advance (for 'advance' action)",
                },
                "cefr_level": {
                    "type": "string",
                    "enum": ["A1", "A2", "B1"],
                    "description": "CEFR level (for 'set_level' action)",
                },
                "block": {
                    "type": "integer",
                    "description": "Lesson block 1-3 (for 'record_lesson')",
                },
                "story_type": {
                    "type": "string",
                    "description": "Story type (for 'record_lesson')",
                },
                "theme": {
                    "type": "string",
                    "description": "Theme covered (for 'record_lesson')",
                },
                "grammar_topic": {
                    "type": "string",
                    "description": "Grammar topic covered (for 'record_lesson')",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Lesson duration in minutes (for 'record_lesson')",
                },
            },
            "required": ["action"],
        }

    async def execute(self, action: str, **kwargs: Any) -> str:
        """Dispatch to the appropriate action handler.

        Args:
            action: One of ``get_status``, ``advance``, ``record_lesson``,
                    ``set_level``.
            **kwargs: Action-specific parameters.

        Returns:
            A human-readable status string for the LLM to relay to the student.
        """
        if not self._sender_id:
            return "Error: No user context set."

        from src.db.queries import get_or_create_user

        user = await get_or_create_user(self._db, self._sender_id)

        if action == "get_status":
            return await self._get_status(user.id)
        elif action == "advance":
            return await self._advance(user.id, kwargs.get("advance_what", "theme"))
        elif action == "record_lesson":
            return await self._record_lesson(user.id, kwargs)
        elif action == "set_level":
            return await self._set_level(user.id, kwargs.get("cefr_level", "A1"))
        else:
            return f"Error: Unknown action '{action}'"

    async def _get_status(self, user_id: int) -> str:
        """Return a formatted summary of the student's current progress."""
        from src.db.queries import get_user_progress, update_progress

        progress = await get_user_progress(self._db, user_id)
        if progress is None:
            await update_progress(self._db, user_id)
            progress = await get_user_progress(self._db, user_id)
            assert progress is not None

        pos = get_position(
            progress.cefr_level,
            progress.theme_index,
            progress.grammar_index,
            progress.phase,
            progress.week_number,
        )

        lines = [
            f"CEFR Level: {pos.cefr_level}",
            f"Theme progress: {pos.theme_index}/15",
            f"Grammar progress: {pos.grammar_index}/15",
            f"Phase: {pos.phase}, Week: {pos.week_number}",
            f"Words learned: {progress.words_learned}",
            f"Lessons completed: {progress.lessons_completed}",
            f"Current streak: {progress.current_streak} days",
            f"Longest streak: {progress.longest_streak} days",
            f"Level complete: {'Yes' if pos.is_level_complete else 'No'}",
        ]
        return "\n".join(lines)

    async def _advance(self, user_id: int, advance_what: str) -> str:
        """Advance the theme or grammar index by one step."""
        from src.db.queries import get_user_progress, update_progress

        progress = await get_user_progress(self._db, user_id)
        if progress is None:
            await update_progress(self._db, user_id)
            progress = await get_user_progress(self._db, user_id)
            assert progress is not None

        new_theme, new_grammar = compute_advance(
            progress.theme_index,
            progress.grammar_index,
            advance_what,
            progress.cefr_level,
        )

        await update_progress(
            self._db, user_id,
            theme_index=new_theme,
            grammar_index=new_grammar,
        )

        return (
            f"Advanced {advance_what}. "
            f"Theme: {new_theme}/15, Grammar: {new_grammar}/15."
        )

    async def _record_lesson(self, user_id: int, kwargs: dict[str, Any]) -> str:
        """Record a lesson and update the streak."""
        from src.db.queries import (
            get_user_progress,
            record_lesson,
            update_progress,
        )

        today = date.today().isoformat()

        await record_lesson(
            self._db,
            user_id,
            today,
            block=kwargs.get("block"),
            story_type=kwargs.get("story_type"),
            theme=kwargs.get("theme"),
            grammar_topic=kwargs.get("grammar_topic"),
            duration_minutes=kwargs.get("duration_minutes"),
            completed=True,
        )

        progress = await get_user_progress(self._db, user_id)
        if progress is None:
            await update_progress(self._db, user_id)
            progress = await get_user_progress(self._db, user_id)
            assert progress is not None

        new_lessons = progress.lessons_completed + 1

        # Streak logic: increment if last lesson was today or yesterday,
        # reset to 1 otherwise.
        new_streak = 1
        if progress.last_lesson_date:
            last = date.fromisoformat(progress.last_lesson_date)
            today_date = date.today()
            gap = (today_date - last).days
            if gap == 0:
                # Already had a lesson today — keep the current streak
                new_streak = progress.current_streak
            elif gap == 1:
                # Consecutive day — extend the streak
                new_streak = progress.current_streak + 1
            # gap > 1 → streak resets to 1 (default)

        new_longest = max(progress.longest_streak, new_streak)

        await update_progress(
            self._db, user_id,
            lessons_completed=new_lessons,
            current_streak=new_streak,
            longest_streak=new_longest,
            last_lesson_date=today,
        )

        return (
            f"Lesson recorded. "
            f"Total lessons: {new_lessons}. "
            f"Streak: {new_streak} days."
        )

    async def _set_level(self, user_id: int, cefr_level: str) -> str:
        """Set the CEFR level and reset theme/grammar indices to 0."""
        from src.db.queries import update_progress, update_user

        valid_levels = {"A1", "A2", "B1"}
        if cefr_level not in valid_levels:
            return f"Error: Invalid CEFR level '{cefr_level}'. Must be A1, A2, or B1."

        # Update both the users table and the progress table
        await update_user(self._db, user_id, cefr_level=cefr_level)
        await update_progress(
            self._db, user_id,
            cefr_level=cefr_level,
            theme_index=0,
            grammar_index=0,
            phase=1,
            week_number=1,
        )

        return f"CEFR level set to {cefr_level}. Theme and grammar indices reset to 0."
