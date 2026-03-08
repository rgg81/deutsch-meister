"""Core NanoBot agent."""
from __future__ import annotations

import os
from pathlib import Path


class Agent:
    """NanoBot agent that loads skills and routes messages through providers."""

    def __init__(self, skill_dir: str | None = None):
        self.skill_dir = skill_dir or os.getenv("NANOBOT_SKILL_DIR", "skills")

    def run(self, message: str = "") -> str:
        """Run the agent with an optional initial message."""
        skill = self._load_skill()
        provider = self._get_provider()
        return provider.complete(skill, message)

    def _load_skill(self) -> str:
        """Load SKILL.md content from the skill directory."""
        skill_path = Path(self.skill_dir) / "deutsch-meister" / "SKILL.md"
        if skill_path.exists():
            return skill_path.read_text()
        return ""

    def _get_provider(self):
        from nanobot.providers.anthropic import AnthropicProvider
        return AnthropicProvider()
