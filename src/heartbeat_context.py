"""Context provider for the heartbeat decision phase.

Computes runtime data (pause state, user activity, last reminder)
so the LLM can make an informed skip/run decision instead of
always returning 'run' from reading HEARTBEAT.md alone.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Awaitable, Callable

if TYPE_CHECKING:
    from nanobot.session.manager import SessionManager
    from src.heartbeat_state import HeartbeatState


def make_heartbeat_context_provider(
    state: HeartbeatState,
    session_manager: SessionManager,
    inactivity_threshold_h: float = 24.0,
) -> Callable[[], Awaitable[str]]:
    """Create an async context provider for HeartbeatService.

    Returns a coroutine that produces a Runtime Context block with:
    - pause state
    - hours since last user activity
    - hours since last reminder
    - a clear directive (skip / run)
    """

    async def provider() -> str:
        # 1. Check pause state
        if state.paused:
            return (
                "## Runtime Context\n"
                "- Paused: yes\n"
                "- Action: **skip** (reminders are paused by the user)\n"
            )

        # 2. Find last user activity across sessions
        last_activity_hours: float | None = None
        now = datetime.now(timezone.utc)

        for item in session_manager.list_sessions():
            key = item.get("key", "")
            # Skip internal sessions
            if key.startswith("cron:") or key == "heartbeat":
                continue
            updated = item.get("updated_at")
            if updated:
                try:
                    ts = datetime.fromisoformat(updated)
                    # Ensure timezone-aware comparison
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    hours = (now - ts).total_seconds() / 3600
                    if last_activity_hours is None or hours < last_activity_hours:
                        last_activity_hours = hours
                except (ValueError, TypeError):
                    continue

        # 3. Check last reminder
        last_reminder = state.last_reminder_at
        reminder_hours: float | None = None
        if last_reminder:
            if last_reminder.tzinfo is None:
                last_reminder = last_reminder.replace(tzinfo=timezone.utc)
            reminder_hours = (now - last_reminder).total_seconds() / 3600

        # 4. Determine action
        if last_activity_hours is None:
            action = "skip"
            reason = "no user sessions found"
        elif last_activity_hours < inactivity_threshold_h:
            action = "skip"
            reason = f"user active {last_activity_hours:.1f}h ago (threshold: {inactivity_threshold_h}h)"
        elif reminder_hours is not None and reminder_hours < inactivity_threshold_h:
            action = "skip"
            reason = f"reminder already sent {reminder_hours:.1f}h ago"
        else:
            action = "run"
            reason = f"user inactive {last_activity_hours:.1f}h (threshold: {inactivity_threshold_h}h)"

        lines = [
            "## Runtime Context",
            f"- Paused: no",
            f"- Last user activity: {f'{last_activity_hours:.1f}h ago' if last_activity_hours is not None else 'unknown'}",
            f"- Last reminder sent: {f'{reminder_hours:.1f}h ago' if reminder_hours is not None else 'never'}",
            f"- Inactivity threshold: {inactivity_threshold_h}h",
            f"- Action: **{action}** ({reason})",
        ]
        return "\n".join(lines) + "\n"

    return provider
