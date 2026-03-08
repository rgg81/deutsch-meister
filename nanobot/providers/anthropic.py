"""Anthropic Claude provider for NanoBot."""
from __future__ import annotations

import os


class AnthropicProvider:
    """Wraps the Anthropic API for NanoBot."""

    def __init__(self, model: str = "claude-opus-4-6"):
        self.model = model
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")

    def complete(self, system_prompt: str, message: str) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": message}],
        )
        return response.content[0].text
