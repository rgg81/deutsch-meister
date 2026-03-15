# DeutschMeister

A personal AI German language tutor delivered via Telegram, powered by GitHub Copilot.

## Overview

DeutschMeister is a conversational German tutor that:
- Delivers personalized daily lessons via Telegram
- Tracks vocabulary progress using a Spaced Repetition System (SRS)
- Follows the CEFR curriculum (A1 → B1)
- Adapts to your learning pace and weaknesses
- Provides audio pronunciation for vocabulary and listening exercises (use `/pronounce [word]` or ask the tutor)

## Tech Stack

- **Framework**: NanoBot (Python agent framework, vendored)
- **Channel**: Telegram (via python-telegram-bot)
- **AI**: GitHub Copilot (via NanoBot's OAuth provider — no API key required)
- **Storage**: SQLite (vocabulary SRS, progress tracking)
- **Scheduler**: APScheduler (daily lesson reminders)

### Audio Features

- **Speech-to-Text**: Pluggable STT abstraction (`src/stt/`) with a Groq Whisper Large v3 implementation
- Send voice messages to the bot and they are automatically transcribed before being processed by the tutor
- STT provider is configured via `config.json` under the `"stt"` key (see Setup)
- The `GROQ_API_KEY` environment variable can be used as an alternative to setting the key in `config.json`

- **Text-to-Speech / Speak tool**: The `speak` agent tool (`src/tools/speak.py`) generates `.ogg` audio files from German text using the configured TTS provider
- The tutor calls `speak` automatically when pronunciation audio would be helpful; the resulting file is sent as a Telegram voice message
- Generated audio is cached on disk under the NanoBot media directory (keyed by text content and voice), so repeated requests for the same phrase are served instantly without re-synthesizing
- The TTS provider and voice are configured via the `"tts"` key in `config.json` (see the TTS provider docs for available voices)

## Project Structure

```
deutsch-meister/
├── nanobot/          # Vendored NanoBot core framework
├── src/              # Custom modules (SRS engine, curriculum, exercises, progress)
├── curriculum/       # CEFR reference files (A1, A2, B1 topic lists)
├── skills/
│   └── deutsch-meister/  # Teaching skill (SKILL.md persona & lesson flow)
├── workspace/
│   ├── SOUL.md       # Agent personality and teaching philosophy
│   └── HEARTBEAT.md  # Periodic check-in rules
├── website/          # Static landing page
├── tests/            # pytest test suite
├── config.example.json
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Setup

### 1. Get a Telegram Bot Token

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts to name your bot
3. BotFather will give you a token like `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`
4. Save it — you'll need it for `config.json`

### 2. Find Your Telegram User ID

1. Search for **@userinfobot** on Telegram
2. Send `/start` — it will reply with your numeric user ID (e.g. `123456789`)
3. Add this ID to the `allowFrom` field in your config to restrict access to yourself only

### 3. Configure the Bot

```bash
cp config.example.json config.json
```

Edit `config.json` and fill in your values:

```json
{
  "providers": {
    "github_copilot": {}
  },
  "agents": {
    "defaults": {
      "model": "github_copilot/gpt-4o",
      "provider": "github_copilot",
      "workspace": "./workspace"
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_TELEGRAM_USER_ID"]
    }
  },
  "stt": {
    "provider": "groq",
    "groq": {
      "apiKey": "YOUR_GROQ_API_KEY"
    }
  }
}
```

> **Optional**: Add a `tools.web.search.apiKey` with a [Brave Search API key](https://brave.com/search/api/) to enable web search during lessons.

> **Optional**: Add an `stt.groq.apiKey` (or set the `GROQ_API_KEY` environment variable) to enable voice message transcription via [Groq](https://console.groq.com/).

> **Optional**: Add a `tts` section to enable voice output. The bot works normally without it — the `speak` tool simply won't be available to the agent. Example:
> ```json
> "tts": {
>   "provider": "edge_with_fallback",
>   "voice": "de-DE-ConradNeural",
>   "piper": {
>     "model": "de_DE-thorsten-high"
>   }
> }
> ```
> Supported providers: `edge` (Microsoft Neural TTS, cloud), `piper` (local/offline), `edge_with_fallback` (Edge with Piper as offline backup).

### 4. Authenticate with GitHub Copilot (OAuth)

DeutschMeister uses your GitHub Copilot subscription for AI — **no API key needed**.

NanoBot handles the OAuth flow automatically on first run:

```bash
# Run the agent — it will prompt you to authenticate via browser if needed
python -m nanobot agent -m "Hallo!"
```

You will be shown a URL to open in your browser and a code to enter. After authenticating once, the token is cached locally under `~/.config/litellm/`.

> **Requirements**: You need an active [GitHub Copilot subscription](https://github.com/features/copilot) (Individual, Business, or Enterprise).

### 5. Run the Agent

```bash
pip install -r requirements.txt
python -m nanobot gateway --config config.json
```

## Docker

```bash
cp config.example.json config.json
# Edit config.json with your Telegram token and user ID

docker-compose up -d
```

The Docker setup mounts `config.json` and the `workspace/` directory into the container.

> **Note on GitHub Copilot auth in Docker**: Run `python -m nanobot agent -m "test"` locally first to complete the OAuth flow. This caches your token under `~/.config/litellm/` on your host machine. Then mount it into the container by adding this volume to `docker-compose.yml`:
>
> ```yaml
> volumes:
>   - ./config.json:/app/config.json:ro
>   - ./workspace:/app/workspace
>   - ./data:/app/data
>   - ~/.config/litellm:/root/.config/litellm:ro
> ```

## Development

```bash
# Run tests
pytest tests/

# Smoke-test the agent (triggers GitHub Copilot OAuth on first run)
python -m nanobot agent -m "test"
```

### Testing Audio

```bash
# Run automated audio integration tests (no Telegram connection needed)
pytest tests/test_audio_e2e.py -v

# Run the full test suite
pytest tests/
```

Manual end-to-end audio testing (bot running, real Telegram): see [`scripts/test_audio_manual.md`](scripts/test_audio_manual.md).

**Prerequisites for audio tests**: `ffmpeg` (required), `edge-tts` (installed via `requirements.txt`), `faster-whisper` and `piper-tts` (optional, for fallback providers).

## License

MIT
