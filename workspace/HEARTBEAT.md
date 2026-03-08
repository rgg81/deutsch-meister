# Heartbeat Rules — DeutschMeister

Review the following conditions and call the `heartbeat` tool with `action: "run"` if any apply,
or `action: "skip"` if none apply.

## Active Task Conditions

### Daily Check-in Reminder
- **Trigger**: If the learner has not sent a message in the last **24 hours**, send a gentle
  reminder to keep their German learning streak alive.
- **Message style**: Warm and encouraging, never nagging. Include a small teaser (e.g., a fun
  German word or phrase) to spark curiosity.
- **Example**: "Hallo! 👋 Ready for a quick German moment today? Here's one to get you thinking:
  *Fernweh* (n.) — the longing to travel to distant places. Bis bald!"

### No Active Conditions
- If the learner has messaged recently (within 24 hours), return `action: "skip"`.
- If there are no pending lessons or reminders, return `action: "skip"`.

## Notes

- Keep reminders light and optional — never pressure the learner.
- One reminder per 24-hour window is sufficient. Do not send multiple reminders.
