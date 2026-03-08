# DeutschMeister — AI German Tutor

## Project Overview

A personal German language tutor built on NanoBot (Python agent framework),
delivered via Telegram, powered by Claude API.

## Tech Stack

- Python 3.11+, NanoBot framework (forked)
- python-telegram-bot (via NanoBot's channel adapter)
- Anthropic Claude API (via NanoBot's provider system)
- SQLite for vocabulary SRS and progress tracking
- APScheduler / NanoBot cron for daily lesson scheduling
- Static HTML/CSS/JS for the landing page (website/ directory)

## Code Style

- Python: PEP 8, type hints, docstrings on public functions
- Tests: pytest, aim for >80% coverage on src/ modules
- Commits: conventional commits (feat:, fix:, docs:, test:)

## Key Directories

- nanobot/ — forked NanoBot core (minimize changes here)
- skills/deutsch-meister/ — the SKILL.md teaching instructions
- src/ — custom modules (SRS engine, curriculum, exercises, progress)
- curriculum/ — CEFR reference files (A1, A2, B1 topic lists)
- website/ — static landing page
- tests/ — pytest test suite

## Development Workflow

- All changes via PRs (Claude Code Action or manual)
- Tests must pass before merge
- Run pytest tests/ to validate
- Run python -m nanobot agent -m "test" to smoke-test the agent

## Important Decisions

- SQLite over markdown files for vocabulary/progress (queryable, supports SRS interval calculations efficiently)
- NanoBot's SKILL.md for teaching persona and lesson flow
- Custom Python modules for algorithmic logic (SRS, curriculum state)
