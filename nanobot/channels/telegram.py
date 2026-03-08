"""Telegram channel adapter for NanoBot."""
from __future__ import annotations

import os
from nanobot.agent import Agent


class TelegramChannel:
    """Connects NanoBot agent to a Telegram bot."""

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.agent = Agent()

    def start(self):
        """Start polling for Telegram updates."""
        from telegram.ext import Application, MessageHandler, filters

        app = Application.builder().token(self.token).build()
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle))
        app.run_polling()

    async def _handle(self, update, context):
        message = update.message.text or ""
        reply = self.agent.run(message)
        await update.message.reply_text(reply)
