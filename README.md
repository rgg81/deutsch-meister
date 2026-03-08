# DeutschMeister

A personal AI German language tutor delivered via Telegram, powered by GitHub Copilot (OAuth).

## Overview

DeutschMeister is a conversational German tutor that:
- Delivers personalized daily lessons via Telegram
- Tracks vocabulary progress using a Spaced Repetition System (SRS)
- Follows the CEFR curriculum (A1 → B1)
- Adapts to your learning pace and weaknesses

## Tech Stack

- **Framework**: NanoBot (Python agent framework, vendored)
- **Channel**: Telegram (via python-telegram-bot)
- **AI**: GitHub Copilot (OAuth — no API key required)
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
├── workspace/        # NanoBot workspace (SOUL.md personality, HEARTBEAT.md rules)
├── website/          # Static landing page
├── tests/            # pytest test suite
├── config.example.json   # NanoBot config template
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Setup

### 1. Get a Telegram Bot Token

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts to name your bot
3. BotFather will give you a token like `123456789:ABCdef...` — save it

### 2. Find Your Telegram User ID

1. Search for **@userinfobot** on Telegram
2. Send `/start` — it will reply with your numeric user ID (e.g. `987654321`)
3. This ID goes in `allowFrom` to restrict the bot to only you

### 3. Authenticate with GitHub Copilot (OAuth)

DeutschMeister uses your GitHub Copilot subscription for AI — no separate API key needed.

On first run, NanoBot will open a browser-based GitHub OAuth flow:
1. It prints a URL — open it in your browser
2. Log in with your GitHub account (that has an active Copilot subscription)
3. Authorize the app
4. The token is saved locally for future runs

> **Note**: A GitHub Copilot Individual or Business subscription is required.

### 4. (Optional) Get a Brave Search API Key

For web search capability:
1. Sign up at [brave.com/search/api](https://brave.com/search/api/)
2. Get a free API key (2,000 queries/month on the free tier)

### 5. Configure

```bash
cp config.example.json config.json
```

Edit `config.json` and fill in:
- `channels.telegram.token` — your bot token from @BotFather
- `channels.telegram.allowFrom` — your Telegram user ID from @userinfobot
- `tools.web.search.apiKey` — your Brave Search key (optional, remove if unused)

### 6. Run

```bash
pip install -r requirements.txt
nanobot gateway --config config.json
```

## Docker

```bash
cp config.example.json config.json
# Edit config.json with your credentials
docker-compose up -d
```

> **First-run OAuth**: For the GitHub Copilot OAuth flow in Docker, run interactively first:
> ```bash
> docker-compose run --rm bot nanobot gateway --config /app/config.json
> ```
> Complete the browser login, then start the service normally with `docker-compose up -d`.

## Development

```bash
# Run tests
pytest tests/

# Smoke-test the agent
python -m nanobot agent -m "test"
```

## License

MIT
