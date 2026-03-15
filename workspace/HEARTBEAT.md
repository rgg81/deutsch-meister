# Heartbeat: Daily Inactivity Reminder

## Phase 1 — Decision Rules

Read the **Runtime Context** section below carefully. It contains computed data about the current state.

- If `Action: **skip**` → call `heartbeat(action="skip")`. Done.
- If `Action: **run**` → call `heartbeat(action="run", tasks="<instruction>")` where `<instruction>` is the Phase 2 message below.

Do NOT infer activity or pause state from the task description itself — only use the Runtime Context fields.

## Phase 2 — Task Instruction (only when action=run)

Use exactly this as the `tasks` value:

> Send Roberto a friendly German lesson check-in message on Telegram. Reference the current CEFR topic, suggest reviewing recent vocabulary, or share a cultural tidbit. Keep it short (2-3 sentences), warm, and in your DeutschMeister voice. No guilt language. Example tone: "Hallo Roberto! Ready to practice some German today? Maybe we can pick up where we left off with ordering food — Ich möchte einen Kaffee, bitte! ☕🇩🇪"
