# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DeutschMeister is a personal German language tutor delivered via Telegram, built on NanoBot (a vendored Python agent framework) and powered by GitHub Copilot (OAuth, no API key required). It follows the CEFR curriculum (A1 → B1) with spaced repetition vocabulary tracking.

## Product Vision

DeutschMeister sits in a gap that no existing product fills well. Duolingo gamifies at the cost of depth. ChatGPT has depth but no memory, no curriculum, no structure. Private tutors have everything but cost €30+/hour and don't scale to your schedule.

DeutschMeister is the intersection: **structured CEFR curriculum + persistent memory + spaced repetition + always available**. The teaching persona (SOUL.md + SKILL.md) is genuinely excellent — story-driven grammar, recurring characters, spiral review, adaptive German/English ratio. This is real pedagogy, not a toy.

This product can help thousands of people learn German who can't afford tutors or don't have time for classes. Every contribution should serve that mission: make the learning experience more effective, more personal, and more human.

## Commands

```bash
# Setup (uv manages Python + venv)
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt -e nanobot/

# Run tests (PYTHONPATH=. needed for src/ imports)
PYTHONPATH=. pytest tests/

# Run a single test file
PYTHONPATH=. pytest tests/test_example.py

# Smoke-test the agent (triggers GitHub Copilot OAuth on first run)
python -m nanobot agent -m "test"

# Start the bot (Telegram gateway)
python -m nanobot gateway --config config.json

# Lint (ruff is configured in nanobot/pyproject.toml)
ruff check src/ nanobot/

# Run with Docker
docker-compose up -d
```

## Architecture

**NanoBot framework** (`nanobot/`): Vendored fork — minimize changes here. Provides the agent loop, channel adapters (Telegram, Slack, etc.), LLM provider abstraction (uses litellm + GitHub Copilot OAuth), tool system, cron scheduling, and skill loading. Entry point: `python -m nanobot` which calls `nanobot/nanobot/cli/commands.py`.

**Teaching persona** is defined in two layers:
- `workspace/SOUL.md` — agent personality and teaching philosophy (loaded by NanoBot as the agent's system prompt)
- `skills/deutsch-meister/SKILL.md` — detailed lesson structure, slash commands, SRS logic, communication style rules
- `workspace/HEARTBEAT.md` — rules for daily check-in reminders (24h nudge)

**Custom modules** (`src/`): Where project-specific Python code goes:
- `src/db/` — SQLite data layer (async, WAL mode, migration runner)
- `src/srs/` — Spaced repetition engine + NanoBot tool
- `src/progress/` — Curriculum position tracker + NanoBot tool
- `src/profile/` — Student profile management + NanoBot tool
- `src/context/` — Teacher's Notebook context provider (injected before every LLM interaction)
- `src/tts/`, `src/stt/` — Audio providers (TTS/STT)
- `src/tools/` — Custom NanoBot tools (speak)

**Curriculum** (`curriculum/`): CEFR reference files listing topics per level. `a1.md` exists; A2 and B1 are planned.

**Config**: `config.json` (gitignored, created from `config.example.json`) configures the LLM provider, Telegram bot token, and allowed user IDs.

## Code Style

- Python: PEP 8, type hints, docstrings on public functions
- Ruff linter config: line-length 100, target Python 3.11, rules E/F/I/N/W (E501 ignored)
- Package management: `uv` for Python version + venv + deps (no conda/asdf)
- Tests: pytest with `asyncio_mode = "auto"`, run with `PYTHONPATH=.`
- Commits: conventional commits (`feat:`, `fix:`, `docs:`, `test:`)

## Key Decisions

- SQLite over markdown files for vocabulary/progress (queryable, supports SRS interval calculations)
- NanoBot's SKILL.md for teaching persona and lesson flow (not hardcoded in Python)
- GitHub Copilot over Anthropic API — uses existing Copilot subscription via OAuth, no separate API key needed
- `nanobot/` is a vendored fork; custom logic belongs in `src/`

## CI

GitHub Actions workflow (`.github/workflows/claude.yml`) runs Claude Code Action on issues/PRs when `@claude` is mentioned. It has restricted tool access (`git clone`, `git subtree` only).
