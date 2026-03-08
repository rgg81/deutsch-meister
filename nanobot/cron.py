"""APScheduler-based cron helper for NanoBot scheduled tasks."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler


class CronScheduler:
    """Thin wrapper around APScheduler for NanoBot cron jobs."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def add_daily(self, func, hour: int = 8, minute: int = 0):
        """Schedule a function to run daily at a given hour:minute (UTC)."""
        self.scheduler.add_job(func, "cron", hour=hour, minute=minute)

    def start(self):
        self.scheduler.start()

    def stop(self):
        self.scheduler.shutdown()
