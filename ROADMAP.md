# DeutschMeister Improvements Roadmap

## Current State

DeutschMeister is a German language tutor Telegram bot built on the NanoBot framework. The teaching persona (SOUL.md, SKILL.md) and A1 curriculum are fully specified. Audio (TTS/STT) is production-ready with tests. However, the core learning engine is missing: no SRS implementation, no database, no user state persistence, no exercise generators, no progress tracking. The bot currently works as a single-user LLM conversation with a well-crafted system prompt but no structured data backing.

This roadmap proposes concrete, phased improvements across three pillars — (1) learning process, (2) real-teacher simulation, (3) monetization — building on the existing NanoBot architecture with custom code in `src/`. **Priority: learning engine first**, then teacher intelligence, then monetization.

---

## Phase 1: Foundation — Database & Core Learning Engine (P0)

Everything depends on persistent storage. This phase builds the data layer and SRS engine that all other features require.

### 1.1 SQLite Database Schema & Data Layer

Create the persistent storage layer for all user data, vocabulary, and progress.

**New files:**
- `src/db/schema.sql` — DDL for all tables
- `src/db/connection.py` — Async SQLite connection pool (aiosqlite), migrations runner
- `src/db/models.py` — Dataclasses for User, VocabCard, LessonRecord, etc.
- `src/db/queries.py` — Query functions (CRUD for each model)

**Tables:**
```sql
users (id, telegram_id, display_name, cefr_level, daily_goal_minutes,
       preferred_lesson_time, interests, streak_days, streak_last_date,
       german_ratio, onboarding_complete, created_at, updated_at)

vocab_cards (id, user_id, word_de, word_en, gender, example_sentence,
             theme, cefr_level, interval_days, ease_factor, next_review,
             correct_count, incorrect_count, created_at)

lesson_records (id, user_id, date, block, story_type, theme, grammar_topic,
                cefr_level, duration_minutes, completed, notes)

error_patterns (id, user_id, error_type, pattern_description, occurrences,
                last_seen, example_wrong, example_correct)

user_progress (id, user_id, cefr_level, theme_index, grammar_index,
               phase, week_number, words_learned, words_target)
```

**Dependency:** None (foundation for everything)

### 1.2 SRS Engine

Implement the spaced repetition system specified in SKILL.md.

**New files:**
- `src/srs/engine.py` — Core SRS logic: schedule reviews, process answers, advance/reset intervals
- `src/srs/tool.py` — NanoBot Tool subclass `SRSTool` exposing `review_next`, `record_answer`, `add_card`, `get_stats` to the LLM
- `tests/test_srs.py` — Unit tests

**Logic (from SKILL.md):**
- Intervals: 1d → 3d → 7d → 14d → 30d (SM-2 inspired fixed)
- Correct: advance to next interval
- Incorrect: reset to 1d
- Daily cap: 20 review items
- Cards enter queue on first encounter in a lesson

**Modified files:**
- `config.example.json` — Add database path config
- `skills/deutsch-meister/SKILL.md` — Reference the tool names the LLM should call

### 1.3 Progress Tracking Tool

Give the LLM access to read/write the student's curriculum position and stats.

**New files:**
- `src/progress/tracker.py` — Functions: advance_theme, advance_grammar, get_current_position, weekly_report
- `src/progress/tool.py` — NanoBot Tool: `progress_tool` with actions (get_status, advance, report, set_level)
- `tests/test_progress.py`

**What it enables:** `/status`, `/report` slash commands become data-backed instead of LLM-hallucinated.

### 1.4 Student Profile Tool

Persist onboarding answers and preferences so the LLM can query them.

**New files:**
- `src/profile/tool.py` — NanoBot Tool: `profile_tool` with actions (get_profile, update_profile, complete_onboarding)
- `tests/test_profile.py`

**Modified files:**
- `skills/deutsch-meister/SKILL.md` — Instruct LLM to save onboarding answers via profile_tool

---

## Phase 2: Real Teacher Intelligence (P1)

With data persistence in place, build the features that make the bot feel like a real teacher who *knows* you.

### 2.1 Error Pattern Recognition

Track systematic mistakes so the bot can address recurring weaknesses.

**New files:**
- `src/errors/analyzer.py` — Parse correction events, detect patterns (e.g., "consistently confuses dative/accusative"), store in `error_patterns` table
- `src/errors/tool.py` — NanoBot Tool: `error_tracker` with actions (log_error, get_patterns, get_weak_areas)
- `tests/test_errors.py`

**Modified files:**
- `skills/deutsch-meister/SKILL.md` — Add instruction: "After every correction, call error_tracker to log the mistake type. Before planning lessons, check weak areas."

**Teacher behavior:** "I've noticed you keep mixing up 'dem' and 'den' — let's do some extra practice on dative vs accusative today."

### 2.2 Adaptive Difficulty & Pacing

Dynamically adjust lesson difficulty based on performance data.

**New files:**
- `src/adaptive/engine.py` — Compute difficulty score from: SRS accuracy (last 7d), error frequency, lesson completion rate. Output: suggested difficulty adjustment (-1, 0, +1)
- `src/adaptive/tool.py` — NanoBot Tool: `difficulty_advisor` returning current difficulty assessment and recommendation

**Modified files:**
- `skills/deutsch-meister/SKILL.md` — Add instruction: "At start of each lesson, call difficulty_advisor. If student is struggling (accuracy < 60%), simplify. If coasting (accuracy > 90%), increase challenge."

**Teacher behavior:** Instead of `/harder`/`/easier` being manual, the bot proactively says "You've been crushing these vocabulary reviews — let's try some more complex sentences today."

### 2.3 Contextual Memory Enhancement

Leverage NanoBot's existing MEMORY.md system but add structured student context.

**New files:**
- `src/context/builder.py` — Before each lesson, compile a "teacher's notebook" from: student profile, current curriculum position, weak areas, upcoming SRS reviews, streak data, recent lesson summaries. Format as markdown for the LLM context window.

**Modified files:**
- `workspace/SOUL.md` — Add section: "Before each lesson, review the student context provided. Reference their interests, recent struggles, and progress naturally."

**Teacher behavior:** "Last week you mentioned you're going to Munich — perfect timing, today's lesson is about ordering at a Biergarten!" (Interest from profile + curriculum topic alignment)

### 2.4 Conversational Practice Mode

Free-form dialogue practice with structured feedback.

**New files:**
- `src/conversation/tool.py` — NanoBot Tool: `conversation_mode` with actions (start_scenario, end_scenario, rate_performance)
- Scenarios: ordering food, asking directions, job interview, doctor visit, etc.

**Modified files:**
- `skills/deutsch-meister/SKILL.md` — Add `/practice [scenario]` command. Thursday (Gespräch day) automatically enters conversation mode.

**Teacher behavior:** Sets up a role-play scenario, stays in character, then breaks character to give feedback: "Great job! You used 'möchte' correctly. One thing: 'Ich will' sounds a bit demanding — try 'Ich hätte gerne' next time."

### 2.5 Curriculum Expansion: A2 & B1

Fill the missing curriculum levels.

**New files:**
- `curriculum/a2.md` — ~1500 words target, 15 themes, 15 grammar topics (Perfekt with sein, Nebensätze, Wechselpräpositionen, Konjunktiv II, etc.)
- `curriculum/b1.md` — ~3000 words target, 15 themes, 15 grammar topics (Passiv, Relativsätze, Konjunktiv I, Plusquamperfekt, etc.)

---

## Phase 3: Engagement & Gamification (P1)

### 3.1 Streak & Motivation System

Track daily engagement and celebrate consistency.

**Implementation in:** `src/progress/tracker.py` (extend existing)
- Daily streak counter (reset if no lesson for 48h — generous window)
- Weekly streak milestones (7, 30, 90, 365 days)
- Words-learned milestones (100, 250, 500, 800)

**Modified files:**
- `skills/deutsch-meister/SKILL.md` — "Celebrate streak milestones naturally: 'Day 30! Du bist unaufhaltsam!'"
- `src/heartbeat_context.py` — Include streak data so heartbeat reminders can say "Don't break your 15-day streak!"

### 3.2 Quiz & Assessment Tool

Data-backed quizzes instead of LLM-generated-on-the-fly.

**New files:**
- `src/quiz/generator.py` — Pull from vocab_cards + error_patterns to generate targeted quizzes: multiple choice, fill-in-blank, translation, sentence reordering
- `src/quiz/tool.py` — NanoBot Tool: `quiz_tool` with actions (generate_quiz, submit_answer, get_results)
- `tests/test_quiz.py`

**What it enables:** `/quiz` and `/review` commands become structured assessments that update SRS data.

### 3.3 Weekly Progress Reports

Automated end-of-week summaries.

**Implementation in:** `src/progress/tracker.py` (extend)
- Words learned this week vs target
- SRS accuracy trend
- Weak areas identified
- Streak status
- Suggested focus for next week

**Modified files:**
- `skills/deutsch-meister/SKILL.md` — Sunday Rückblick lessons auto-include the data report

---

## Phase 4: Monetization & Multi-User (P1-P2)

### 4.1 Multi-User Support

Refactor from single-user to multi-user. This requires solving two isolation problems: **session/memory isolation** and **data isolation**.

#### Problem: Shared Memory

NanoBot's `MemoryStore` (`nanobot/nanobot/agent/memory.py`) currently writes to a single shared location:
```
workspace/memory/MEMORY.md      ← one file for ALL users
workspace/memory/HISTORY.md     ← one file for ALL users
```

This means one student's facts ("Maria likes cooking, struggles with dative") would bleed into another student's context. The LLM would confuse students' interests, progress, and personal details.

#### Solution: Two-Layer Per-User Isolation

**Layer 1 — Per-user MemoryStore directories** (NanoBot vendored change):

Modify `MemoryStore.__init__()` to accept a `session_key` parameter and use it as a subdirectory:
```
workspace/memory/telegram_123456/MEMORY.md   ← Maria's facts
workspace/memory/telegram_123456/HISTORY.md  ← Maria's history
workspace/memory/telegram_789012/MEMORY.md   ← Thomas's facts
workspace/memory/telegram_789012/HISTORY.md  ← Thomas's history
```

**Modified NanoBot files (vendored fork):**
- `nanobot/nanobot/agent/memory.py` — `MemoryStore.__init__(workspace, session_key)` uses `workspace / "memory" / safe_filename(session_key)` instead of `workspace / "memory"`
- `nanobot/nanobot/agent/context.py` — Pass `session_key` when constructing `MemoryStore`
- `nanobot/nanobot/agent/loop.py` — Pass `session_key` to `MemoryStore()` in the consolidation call

This is a minimal, clean change — NanoBot already has the session key available in all these call sites via `session.key` (format: `channel:chat_id`, e.g., `telegram:123456`).

**Layer 2 — SQLite as primary per-user data store** (no NanoBot changes):

All structured student data (SRS cards, progress, error patterns, profile) lives in the SQLite database from Phase 1, already designed with `user_id` on every table. The LLM accesses this via tools (`srs_tool`, `progress_tool`, `profile_tool`, `error_tracker`), which derive `user_id` from the `sender_id` in the inbound message.

This means MEMORY.md handles soft context (personal anecdotes, conversation style notes) while SQLite handles structured learning data (vocabulary, scores, curriculum position). Both are fully isolated per user.

#### Sessions (Already Per-User)

NanoBot's `SessionManager` (`nanobot/nanobot/session/manager.py`) already isolates conversations by `channel:chat_id`. Each user gets their own JSONL file in `workspace/sessions/`. No changes needed here.

#### Other Changes

**Modified files:**
- `config.example.json` — Remove `allowFrom` restriction or make it optional (currently limits to specific Telegram user IDs)
- `src/db/connection.py` — All queries scoped by `user_id` (already designed in schema)
- All tools in `src/` — Accept `user_id` parameter derived from `sender_id` in InboundMessage

### 4.2 Subscription Tiers & Feature Gating

**New files:**
- `src/billing/plans.py` — Define tiers:
  - **Free**: 3 lessons/week, 10 SRS reviews/day, A1 only, no conversation practice
  - **Basic ($9/mo)**: Daily lessons, full SRS, A1-A2, conversation practice
  - **Premium ($19/mo)**: Everything + B1, priority support, weekly progress reports, pronunciation coaching, mock exams
- `src/billing/gate.py` — `check_access(user_id, feature) -> bool` called by tools before executing
- `src/billing/tool.py` — NanoBot Tool: `subscription_tool` with actions (check_plan, upgrade_url, usage_stats)

**Modified files:**
- All tools in `src/` — Add feature gate checks
- `skills/deutsch-meister/SKILL.md` — Handle upgrade prompts gracefully: "This feature is available on the Basic plan. Type /upgrade to learn more."

### 4.3 Stripe Payment Integration

**New files:**
- `src/billing/stripe_webhook.py` — FastAPI/Starlette webhook handler for Stripe events (checkout.session.completed, customer.subscription.updated/deleted)
- `src/billing/checkout.py` — Generate Stripe Checkout Session URLs for each tier

**Modified files:**
- `docker-compose.yml` — Add webhook endpoint exposure
- `requirements.txt` — Add `stripe`, `starlette`
- `config.example.json` — Add Stripe API key, webhook secret, price IDs

**Flow:** User types `/upgrade` → bot sends Stripe Checkout link → user pays → Stripe webhook updates DB → bot confirms: "Willkommen zum Premium-Plan!"

### 4.4 Landing Page & Onboarding Funnel

**New files:**
- `website/index.html` — Simple landing page (static HTML/CSS)
  - Hero: "Learn German with AI — Like Having a Private Tutor on Telegram"
  - Pricing cards (Free / Basic / Premium)
  - "Start for Free" button → Telegram deep link (`t.me/DeutschMeisterBot?start=web`)
  - Testimonials, feature comparison, FAQ
- `website/styles.css`

**No framework needed** — static HTML served via GitHub Pages or Cloudflare Pages.

### 4.5 Admin Dashboard (P2)

**New files:**
- `src/admin/dashboard.py` — Simple web dashboard (Starlette)
  - Active users, subscription breakdown, daily active learners
  - Revenue metrics (MRR, churn)
  - User progress overview
  - Error pattern analytics (what grammar trips up most users)

---

## Phase 5: Polish & Advanced Features (P2)

### 5.1 Placement Test

New users skip onboarding level question — take a 5-minute adaptive test instead.

**New files:**
- `src/assessment/placement.py` — 10-15 question adaptive test spanning A1-B1 topics
- `src/assessment/tool.py` — NanoBot Tool: `placement_test`

### 5.2 Mock Exams (Goethe-Zertifikat)

Simulate official exam format for A1/A2/B1.

**New files:**
- `src/assessment/mock_exam.py` — Timed sections: Hören, Lesen, Schreiben, Sprechen
- `curriculum/exams/a1_mock.md` — Sample exam content

### 5.3 Homework Assignments

Asynchronous practice between lessons.

**Modified files:**
- `skills/deutsch-meister/SKILL.md` — Block 3 evening recap optionally assigns homework (write 3 sentences using today's grammar, translate a paragraph, etc.)
- `src/progress/tracker.py` — Track homework completion

### 5.4 Multi-Channel Expansion

Leverage NanoBot's built-in channel support.

**Modified files:**
- `config.example.json` — Add WhatsApp, Discord channel configs
- No code changes needed — NanoBot handles channel routing

---

## Implementation Priority Summary

| Priority | Component | Effort | Impact |
|----------|-----------|--------|--------|
| **P0** | SQLite database + data layer | Medium | Enables everything |
| **P0** | SRS engine + tool | Medium | Core learning feature |
| **P0** | Progress tracking tool | Small | Data-backed /status, /report |
| **P0** | Student profile tool | Small | Persistent onboarding |
| **P1** | Error pattern recognition | Medium | Real-teacher behavior |
| **P1** | Adaptive difficulty | Small | Smarter pacing |
| **P1** | Contextual memory | Small | Personalized lessons |
| **P1** | Conversational practice | Medium | Speaking skills |
| **P1** | A2 + B1 curricula | Medium | Content expansion |
| **P1** | Streak & gamification | Small | Retention |
| **P1** | Quiz/assessment tool | Medium | Structured practice |
| **P1** | Multi-user support | Small | Scale prerequisite |
| **P1** | Subscription tiers + gating | Medium | Revenue model |
| **P1** | Stripe integration | Medium | Payment processing |
| **P2** | Landing page | Small | User acquisition |
| **P2** | Admin dashboard | Medium | Operations |
| **P2** | Placement test | Medium | Better onboarding |
| **P2** | Mock exams | Medium | Exam prep value |
| **P2** | Multi-channel | Small | Reach expansion |

---

## Key Files to Modify (Existing)

| File | Changes |
|------|---------|
| `skills/deutsch-meister/SKILL.md` | Reference new tools, add /practice and /upgrade commands, tool calling instructions |
| `workspace/SOUL.md` | Add student context awareness section |
| `src/heartbeat_context.py` | Include streak, SRS due count, last lesson data |
| `config.example.json` | Database path, Stripe keys, multi-user config |
| `requirements.txt` | aiosqlite, stripe, starlette |
| `docker-compose.yml` | Webhook port, data volume for SQLite |
| `nanobot/nanobot/agent/memory.py` | Per-user memory directories (accept session_key) |
| `nanobot/nanobot/agent/context.py` | Pass session_key to MemoryStore |
| `nanobot/nanobot/agent/loop.py` | Pass session_key to MemoryStore in consolidation |

## Verification Plan

1. **Unit tests:** Each new module gets pytest tests (SRS logic, quiz generator, billing gates)
2. **Integration test:** Full lesson flow — onboarding → first lesson → SRS review → progress check
3. **Manual test:** Run `python -m nanobot agent -m "test"` to verify tools register and respond
4. **Telegram test:** Send messages through actual Telegram to verify end-to-end
5. **Lint:** `ruff check nanobot/` and `ruff check src/` pass clean
