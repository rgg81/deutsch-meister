"""Student profile tool for the LLM agent."""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from src.db.connection import Database


class ProfileTool(Tool):
    """Tool for managing student profile and onboarding data."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._sender_id: str | None = None

    def set_user_context(self, sender_id: str) -> None:
        """Set the Telegram sender ID for the current request."""
        self._sender_id = sender_id

    @property
    def name(self) -> str:
        return "profile"

    @property
    def description(self) -> str:
        return (
            "Manage student profile and onboarding. Actions: "
            "'get_profile' returns the student's saved profile, "
            "'update_profile' saves or updates profile fields, "
            "'complete_onboarding' marks onboarding as complete."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get_profile", "update_profile", "complete_onboarding"],
                    "description": "The profile action to perform",
                },
                "display_name": {
                    "type": "string",
                    "description": "Student's display name",
                },
                "cefr_level": {
                    "type": "string",
                    "enum": ["A1", "A2", "B1"],
                    "description": "Current CEFR level",
                },
                "timezone": {
                    "type": "string",
                    "description": "Timezone (e.g., 'Europe/Berlin')",
                },
                "native_language": {
                    "type": "string",
                    "description": "Native language code (e.g., 'en', 'es')",
                },
                "daily_goal_minutes": {
                    "type": "integer",
                    "description": "Daily study goal in minutes",
                },
                "preferred_lesson_time": {
                    "type": "string",
                    "description": "Preferred lesson time (morning/afternoon/evening)",
                },
                "interests": {
                    "type": "string",
                    "description": (
                        "Comma-separated interests (e.g., 'tech, music, cooking')"
                    ),
                },
            },
            "required": ["action"],
        }

    async def execute(self, action: str, **kwargs: Any) -> str:
        """Execute a profile action (get, update, or complete onboarding)."""
        if not self._sender_id:
            return "Error: No user context set."

        from src.db.queries import get_or_create_user, update_user

        user = await get_or_create_user(self._db, self._sender_id)

        if action == "get_profile":
            return self._format_profile(user)
        elif action == "update_profile":
            valid_fields = {
                "display_name",
                "cefr_level",
                "timezone",
                "native_language",
                "daily_goal_minutes",
                "preferred_lesson_time",
                "interests",
            }
            updates = {
                k: v for k, v in kwargs.items() if k in valid_fields and v is not None
            }
            if not updates:
                return "No valid fields to update."
            if "interests" in updates and isinstance(updates["interests"], str):
                updates["interests"] = json.dumps(
                    [i.strip() for i in updates["interests"].split(",")]
                )
            await update_user(self._db, user.id, **updates)
            return f"Profile updated: {', '.join(updates.keys())}"
        elif action == "complete_onboarding":
            await update_user(self._db, user.id, onboarding_complete=1)
            return "Onboarding marked as complete."
        else:
            return f"Error: Unknown action '{action}'"

    def _format_profile(self, user: Any) -> str:
        """Format user profile as readable text."""
        interests = user.interests
        if interests and interests.startswith("["):
            try:
                interests = ", ".join(json.loads(interests))
            except (json.JSONDecodeError, TypeError):
                pass

        lines = [
            f"Name: {user.display_name or 'Not set'}",
            f"CEFR Level: {user.cefr_level}",
            f"Timezone: {user.timezone}",
            f"Native Language: {user.native_language}",
            f"Daily Goal: {user.daily_goal_minutes} minutes",
            f"Preferred Time: {user.preferred_lesson_time}",
            f"Interests: {interests or 'Not set'}",
            f"Onboarding Complete: {'Yes' if user.onboarding_complete else 'No'}",
        ]
        return "\n".join(lines)
