# DeutschMeister

A personal AI German language tutor delivered via Telegram, powered by Claude API.

## Overview

DeutschMeister is a conversational German tutor that:
- Delivers personalized daily lessons via Telegram
- Tracks vocabulary progress using a Spaced Repetition System (SRS)
- Follows the CEFR curriculum (A1 → B1)
- Adapts to your learning pace and weaknesses

## Tech Stack

- **Framework**: NanoBot (Python agent framework, vendored)
- **Channel**: Telegram (via python-telegram-bot)
- **AI**: Anthropic Claude API
- **Storage**: SQLite (vocabulary SRS, progress tracking)
- **Scheduler**: APScheduler (daily lesson reminders)

## Project Structure

```
deutsch-meister/
├── nanobot/          # Vendored NanoBot core framework
├── src/              # Custom modules (SRS engine, curriculum, exercises, progress)
├── curriculum/       # CEFR reference files (A1, A2, B1 topic lists)
├── skills/
│   └── deutsch-meister/  # Teaching skill (SKILL.md persona & lesson flow)
├── website/          # Static landing page
├── tests/            # pytest test suite
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Setup

1. Clone this repository
2. Copy `.env.example` to `.env` and fill in your credentials:
   ```
   ANTHROPIC_API_KEY=your_key_here
   TELEGRAM_BOT_TOKEN=your_token_here
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the agent:
   ```bash
   python -m nanobot agent -m "Hallo!"
   ```

## Docker

```bash
docker-compose up -d
```

## Development

```bash
# Run tests
pytest tests/

# Smoke-test the agent
python -m nanobot agent -m "test"
```

## License

MIT
