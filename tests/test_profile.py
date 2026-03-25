"""Tests for the student profile tool."""

from __future__ import annotations

import json

import pytest

from src.db.connection import Database
from src.db.queries import get_or_create_user, update_user
from src.profile.tool import ProfileTool


@pytest.fixture
async def db(tmp_path):
    """Create a temporary database, run migrations, and tear down after test."""
    database = Database(tmp_path / "test.db")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def tool(db: Database) -> ProfileTool:
    """Return a ProfileTool wired to the test database."""
    return ProfileTool(db)


# ---------------------------------------------------------------------------
# User context
# ---------------------------------------------------------------------------


class TestUserContext:
    """Tests for set_user_context and missing context."""

    @pytest.mark.asyncio
    async def test_no_user_context_returns_error(self, tool: ProfileTool):
        result = await tool.execute(action="get_profile")
        assert result == "Error: No user context set."

    @pytest.mark.asyncio
    async def test_set_user_context_works(self, tool: ProfileTool):
        tool.set_user_context("12345")
        result = await tool.execute(action="get_profile")
        assert "CEFR Level" in result


# ---------------------------------------------------------------------------
# get_profile
# ---------------------------------------------------------------------------


class TestGetProfile:
    """Tests for the get_profile action."""

    @pytest.mark.asyncio
    async def test_get_profile_returns_formatted_profile(
        self, db: Database, tool: ProfileTool
    ):
        tool.set_user_context("42")
        await get_or_create_user(db, "42", "Maria")

        result = await tool.execute(action="get_profile")
        assert "Name: Maria" in result
        assert "CEFR Level: A1" in result
        assert "Timezone: Europe/Berlin" in result
        assert "Native Language: en" in result
        assert "Daily Goal: 60 minutes" in result
        assert "Preferred Time: morning" in result
        assert "Onboarding Complete: No" in result

    @pytest.mark.asyncio
    async def test_get_profile_shows_not_set_for_missing_name(
        self, tool: ProfileTool
    ):
        tool.set_user_context("99")
        result = await tool.execute(action="get_profile")
        assert "Name: Not set" in result

    @pytest.mark.asyncio
    async def test_get_profile_formats_json_interests(
        self, db: Database, tool: ProfileTool
    ):
        tool.set_user_context("50")
        user = await get_or_create_user(db, "50")
        await update_user(
            db, user.id, interests=json.dumps(["tech", "music", "cooking"])
        )

        result = await tool.execute(action="get_profile")
        assert "Interests: tech, music, cooking" in result


# ---------------------------------------------------------------------------
# update_profile
# ---------------------------------------------------------------------------


class TestUpdateProfile:
    """Tests for the update_profile action."""

    @pytest.mark.asyncio
    async def test_update_profile_updates_fields(
        self, db: Database, tool: ProfileTool
    ):
        tool.set_user_context("10")
        await get_or_create_user(db, "10")

        result = await tool.execute(
            action="update_profile",
            display_name="Hans",
            cefr_level="A2",
            daily_goal_minutes=30,
        )
        assert "display_name" in result
        assert "cefr_level" in result
        assert "daily_goal_minutes" in result

        # Verify via get_profile
        profile = await tool.execute(action="get_profile")
        assert "Name: Hans" in profile
        assert "CEFR Level: A2" in profile
        assert "Daily Goal: 30 minutes" in profile

    @pytest.mark.asyncio
    async def test_update_profile_partial_update(
        self, db: Database, tool: ProfileTool
    ):
        tool.set_user_context("11")
        await get_or_create_user(db, "11", "Original")

        # Update only timezone
        result = await tool.execute(action="update_profile", timezone="US/Eastern")
        assert "timezone" in result

        profile = await tool.execute(action="get_profile")
        assert "Timezone: US/Eastern" in profile
        # Name should be unchanged
        assert "Name: Original" in profile

    @pytest.mark.asyncio
    async def test_update_profile_ignores_unknown_fields(
        self, tool: ProfileTool
    ):
        tool.set_user_context("12")
        result = await tool.execute(
            action="update_profile",
            nonexistent_field="value",
            another_bad="data",
        )
        assert result == "No valid fields to update."

    @pytest.mark.asyncio
    async def test_update_profile_no_fields_returns_message(
        self, tool: ProfileTool
    ):
        tool.set_user_context("13")
        result = await tool.execute(action="update_profile")
        assert result == "No valid fields to update."

    @pytest.mark.asyncio
    async def test_interests_stored_as_json_array(
        self, db: Database, tool: ProfileTool
    ):
        tool.set_user_context("14")
        user = await get_or_create_user(db, "14")

        await tool.execute(
            action="update_profile", interests="tech, music, cooking"
        )

        # Read raw value from DB
        row = await db.fetchone(
            "SELECT interests FROM users WHERE id = ?", (user.id,)
        )
        assert row is not None
        parsed = json.loads(row["interests"])
        assert parsed == ["tech", "music", "cooking"]

    @pytest.mark.asyncio
    async def test_interests_display_in_profile(
        self, tool: ProfileTool
    ):
        tool.set_user_context("15")
        await tool.execute(
            action="update_profile", interests="travel, sports"
        )
        profile = await tool.execute(action="get_profile")
        assert "Interests: travel, sports" in profile


# ---------------------------------------------------------------------------
# complete_onboarding
# ---------------------------------------------------------------------------


class TestCompleteOnboarding:
    """Tests for the complete_onboarding action."""

    @pytest.mark.asyncio
    async def test_complete_onboarding_sets_flag(
        self, tool: ProfileTool
    ):
        tool.set_user_context("20")
        result = await tool.execute(action="complete_onboarding")
        assert result == "Onboarding marked as complete."

        profile = await tool.execute(action="get_profile")
        assert "Onboarding Complete: Yes" in profile

    @pytest.mark.asyncio
    async def test_complete_onboarding_is_idempotent(
        self, tool: ProfileTool
    ):
        tool.set_user_context("21")
        result1 = await tool.execute(action="complete_onboarding")
        result2 = await tool.execute(action="complete_onboarding")
        assert result1 == result2 == "Onboarding marked as complete."

        profile = await tool.execute(action="get_profile")
        assert "Onboarding Complete: Yes" in profile


# ---------------------------------------------------------------------------
# Unknown action
# ---------------------------------------------------------------------------


class TestUnknownAction:
    """Tests for invalid action values."""

    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self, tool: ProfileTool):
        tool.set_user_context("30")
        result = await tool.execute(action="delete_everything")
        assert "Error: Unknown action 'delete_everything'" in result
