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
├── nanobot/              # Vendored NanoBot core framework
├── src/                  # Custom modules (SRS engine, curriculum, exercises, progress)
├── curriculum/           # CEFR reference files (A1, A2, B1 topic lists)
├── skills/
│   └── deutsch-meister/  # Teaching skill (SKILL.md persona & lesson flow)
├── workspace/            # NanoBot workspace (SOUL.md, HEARTBEAT.md, memory)
├── website/              # Static landing page
├── tests/                # pytest test suite
├── config.example.json   # Config template (copy to config.json and fill in credentials)
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Setup

### 1. Clone this repository

```bash
git clone https://github.com/rgg81/deutsch-meister.git
cd deutsch-meister
```

### 2. Create your config file

```bash
cp config.example.json config.json
```

Then edit `config.json` and fill in your credentials (see below for how to get each one).

### 3. Get a Telegram bot token

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts to name your bot
3. BotFather will give you a token like `123456789:ABCDefGhIJKlmNoPQRstuVWXyz`
4. Paste this token into `config.json` under `channels.telegram.token`

### 4. Get your Telegram user ID

1. Search for **@userinfobot** on Telegram and send `/start`
2. It will reply with your numeric user ID (e.g. `123456789`)
3. Paste this into `config.json` under `channels.telegram.allowFrom`

### 5. Get your Anthropic API key

1. Go to [console.anthropic.com](https://console.anthropic.com) and sign in
2. Navigate to **API Keys** and create a new key
3. Paste it into `config.json` under `providers.anthropic.apiKey`

### 6. (Optional) Get a Brave Search API key

For web search capability, get a free API key from [brave.com/search/api](https://brave.com/search/api/)
and add it under `tools.web.search.apiKey` in `config.json`.

### 7. Run the agent

```bash
pip install -r requirements.txt
python -m nanobot agent -m "Hallo!"
```

## Docker

```bash
cp config.example.json config.json
# Edit config.json with your credentials
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
