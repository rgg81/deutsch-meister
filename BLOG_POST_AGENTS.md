# The Night I Watched Three AI Agents Build My App While I Drank Coffee

*This is Part 3 of the DeutschMeister series. [Part 1: building the bot for $0/month.] [Part 2: teaching it to listen and speak.]*

---

There's a moment in software engineering where you stop writing code and start conducting an orchestra.

I didn't plan for it. I was staring at a blank terminal, thinking about the five features DeutschMeister needed to become a *real* language tutor instead of a clever chatbot. SQLite database. Spaced repetition engine. Progress tracking. Student profiles. A context system that gives the AI teacher a "notebook" before every lesson.

Five features. Each one touching the database schema, the agent loop, the tool registry, the teaching persona files. Dependencies between them. A specific order of operations. The kind of work that normally means a week of focused coding, careful git branching, and at least one existential crisis about database migrations.

Instead, I typed a plan into Claude Code and watched three AI agents coordinate, implement, review, and merge all five features in a single session. Five pull requests. 153 new tests. Zero regressions. And the most fascinating software development experience I've ever had.

Let me tell you what happened.

---

## First, a Mission Statement That Made Me Stop Scrolling

Before we get to the agents, I need to tell you about the moment that reframed the entire project.

I'd been thinking about DeutschMeister as a personal tool -- *my* German tutor, built for *my* learning. A fun weekend project. A blog post or two.

Then Claude Code wrote this during a planning session, and I had to reread it three times:

> *DeutschMeister sits in a gap that no existing product fills well. Duolingo gamifies at the cost of depth. ChatGPT has depth but no memory, no curriculum, no structure. Private tutors have everything but cost EUR 30+/hour and don't scale to your schedule.*
>
> *DeutschMeister is the intersection: structured CEFR curriculum + persistent memory + spaced repetition + always available. This is real pedagogy, not a toy.*
>
> *This product can help thousands of people learn German who can't afford tutors or don't have time for classes. Every contribution should serve that mission: make the learning experience more effective, more personal, and more human.*

I didn't write that. Claude did. And it was right.

There are people who can't afford EUR 30/hour for a tutor. People whose schedules don't fit into a classroom. People who've opened Duolingo, earned their streak, and still can't order coffee in Berlin (I know because I was one of them -- see Part 2).

That paragraph turned DeutschMeister from "my weekend project" into something with a purpose. And it changed how I thought about the next phase of development. These weren't features I was building for fun. They were the foundation that makes the *teaching* real. Without persistent memory, the tutor forgets your name between sessions. Without SRS backed by a database, spaced repetition is just the LLM pretending to remember intervals. Without progress tracking, `/status` is a hallucination.

The mission was clear: make the bot *remember*. Make it *know* you. Make the pedagogy persistent.

Now I needed to build five interconnected systems to make it happen. And I had a wild idea about *how*.

---

## The Plan: GitHub Issues as an Orchestration Layer

Here's what I needed to build:

1. **SQLite database** (#32) -- the foundation. Users, vocab cards, lesson records, progress. WAL mode, migration runner, async queries.
2. **SRS engine** (#33) -- spaced repetition with real interval math. SM-2-inspired, configurable limits, separate new/review caps.
3. **Progress tracking** (#34) -- curriculum position, streak logic, lesson history.
4. **Student profile** (#35) -- persist onboarding answers so the LLM knows your name, timezone, and interests across sessions.
5. **Context builder** (#36) -- a "Teacher's Notebook" injected before every interaction. The LLM sees your profile, progress, SRS stats, and last lesson summary. This is the magic that makes it feel like a real teacher.

The dependency graph was clear: #32 was the foundation. #33, #34, #35 could run in parallel after #32 merged. #36 needed everything.

```
Wave 1: #32 (database)           -- sequential
Wave 2: #33, #34, #35            -- parallel
Wave 3: #36 (context builder)    -- sequential, after all
```

I created all five issues on GitHub with detailed specs. Acceptance criteria. Schema designs. References to existing code patterns. Then I told Claude Code to implement them using a three-role agent pipeline.

Three roles. Five issues. Three waves. Let me explain.

---

## The Three Agents: PO, Engineer, QA

Every issue flowed through the same pipeline:

**Product Owner** -- Reviews the issue, validates requirements against downstream dependencies, adds missing acceptance criteria, updates the GitHub issue.

**Staff Engineer** -- Implements in an isolated git worktree. Reads existing patterns (`SpeakTool`, `HeartbeatContext`), writes code, runs tests, creates a PR.

**QA Engineer** -- Reviews the PR diff for security (SQL injection), correctness (interval math), architecture (tool patterns), and testing (edge cases). Approves or requests changes.

These weren't three separate tools or three different AI models. They were three *prompts* -- three different lenses through which Claude Code examined the same codebase. The Product Owner thinks about requirements and downstream impacts. The Engineer thinks about implementation patterns and test coverage. The QA thinks about what could break.

Same brain. Different hats. Different output.

---

## Wave 1: The Foundation (And an Unexpected Detour)

Wave 1 was the SQLite database -- the table stakes for everything else.

The PO agent refined issue #32, adding a critical cross-cutting concern: every tool in the system needs to know *which user* is talking. In a Telegram bot, `sender_id` is your identity. Every database query needs to be scoped by user. The PO added this to the acceptance criteria:

- Add `set_user_context(sender_id)` to the Tool base class
- Propagate sender identity to all tools in the agent loop
- Data-layer tools override it to scope queries per user

This is the kind of requirement that's obvious in retrospect and catastrophic to miss. The PO caught it because its job was to think about downstream consumers, not just the current issue.

Then the Engineer agent went to work. Isolated worktree. New branch. Six new files:

```
src/db/
  __init__.py          # Factory function
  connection.py        # Async SQLite with WAL mode + migration runner
  models.py            # Dataclasses: User, VocabCard, LessonRecord, UserProgress
  queries.py           # Parameterized CRUD (no f-strings in SQL, ever)
  migrations/
    001_initial.sql    # Four tables, three indexes
```

Plus modifications to the NanoBot framework: `set_user_context()` on the Tool base class, `all_tools()` on the registry, sender_id propagation in the agent loop.

26 tests. WAL mode verified. Foreign keys enforced. Multi-user isolation tested (two users, verify they can't see each other's data).

The QA agent reviewed the PR, found zero blocking issues, noted four non-blocking observations for future improvement, and approved.

But here's where things got interesting. When I tried to run the tests, Python exploded:

```
ModuleNotFoundError: No module named '_sqlite3'
```

The project's Python (managed by asdf) had been compiled without SQLite support. The headers weren't installed when Python was built. This kicked off a 20-minute adventure involving conda's sqlite headers, Python rebuilds that broke SSL, and the eventual realization that the right answer was to throw away both conda and asdf entirely.

We switched to **uv** -- Astral's blazing-fast Python manager. One command:

```bash
uv venv --python 3.12 .venv
```

It downloaded a pre-built Python 3.12 with everything working -- sqlite3, ssl, the works. Installed all dependencies in seconds. No compilation. No header hunting. No conda environments polluting the system.

Sometimes the best engineering decision in a session isn't about the feature you're building. It's about the toolchain under your feet.

PR merged. Wave 1 complete.

---

## Wave 2: The Parallel Sprint

This is where the orchestration got beautiful.

With the database merged, I launched three Engineer agents simultaneously -- one for each remaining data-layer feature. Each got its own isolated git worktree, its own branch, its own slice of the problem.

**Agent 1** built the SRS engine: pure interval logic separated from the database, a NanoBot tool bridging them, 49 tests covering every interval transition (0->1, 1->3, 3->7, 7->14, 14->30, 30->30), incorrect resets, ease factor bounds, and the full SM-2 ladder.

**Agent 2** built progress tracking: curriculum position management for A1's 15 themes and 15 grammar topics, streak logic (consecutive days extend, gaps reset, longest streak updates), and a tool that makes `/status` return real data instead of hallucinations. 28 tests.

**Agent 3** built the student profile: onboarding persistence, partial updates, interests stored as JSON arrays, and SKILL.md instructions telling the LLM exactly how to save answers during onboarding. 14 tests.

Three agents. Three worktrees. Three branches. Running simultaneously.

They finished within minutes of each other. Three PRs appeared on GitHub. I launched three QA agents in parallel to review them. All three approved.

Merged in sequence: Progress -> Profile -> SRS. Total time from "launch Wave 2" to "all three merged": faster than I could have written the first one by hand.

---

## Wave 3: The Teacher's Notebook

The final piece was the context builder -- and it's the one that transforms DeutschMeister from "a bot with a database" into "a teacher who knows you."

Before every single interaction, the context builder compiles a "Teacher's Notebook" and injects it into the LLM's context. The LLM sees this before it sees your message:

```markdown
## Teacher's Notebook

### Student Profile
- Name: Roberto
- CEFR Level: A1
- Native Language: en
- Interests: tech, music, cooking
- Onboarding: complete

### Curriculum Position
- Theme: 4/15 (Food & Drink)
- Grammar: 3/15 (Irregular Verbs)
- Words Learned: 127
- Lessons Completed: 12

### Engagement
- Current Streak: 5 days
- Last Lesson: yesterday

### SRS Review Stats
- Total Cards: 89
- Due Today: 12 (3 new, 9 review)
- Overall Accuracy: 78%
- Mature Cards: 23

### Last Lesson
- [2026-03-24] Block 2 (Core): Type: kultur, Theme: Food, Grammar: Articles

### Difficulty Signal
- Performance: ON TRACK -- maintain current difficulty
```

The LLM doesn't have to ask "what's your name?" It already knows. It doesn't guess at your level -- it has the data. When it says "Welcome back! It's been 3 days -- let's do a quick review first," it's because it *calculated* 3 days from your last lesson date.

And when the SOUL.md says "Never mention the Teacher's Notebook to the student" -- the LLM uses the data naturally, like a real teacher glancing at their notes before class.

Every section degrades gracefully. New user with no data? "No progress data yet -- this is a new student." Database error? Silent fallback. The teacher's notebook is always there, always accurate, never crashes the conversation.

The QA agent verified: 36 tests. Multi-user isolation. Every section independent (one failure doesn't cascade). Graceful degradation on empty data.

PR merged. Wave 3 complete.

---

## The Numbers

Let me lay out what the agent pipeline produced:

| Wave | Issue | PR | Feature | Tests |
|------|-------|----|---------|-------|
| 1 | #32 | #55 | SQLite database + migrations | 26 |
| 2 | #33 | #58 | SRS engine + tool | 49 |
| 2 | #34 | #56 | Progress tracking + tool | 28 |
| 2 | #35 | #57 | Student profile + tool | 14 |
| 3 | #36 | #59 | Context builder | 36 |

**5 PRs. 153 new tests. 269 total tests passing. Zero regressions.**

Files created: 18 new Python modules across `src/db/`, `src/srs/`, `src/progress/`, `src/profile/`, `src/context/`.

Files modified: Tool base class, tool registry, agent loop, context builder, SKILL.md, SOUL.md, config, requirements.

The wiring step (connecting everything to the startup code) was one final commit -- 66 lines that create the database, register the tools, and inject the context provider. After that: just restart the bot.

---

## What Made This Work

I've been writing software for a long time. I've never seen anything like this. Here's what I think made it work:

### 1. GitHub Issues as the Single Source of Truth

Every agent -- PO, Engineer, QA -- worked from the same GitHub issue. The PO refined it. The Engineer implemented against it. The QA reviewed against it. No requirements drifted in Slack. No "what did we agree on?" The issue *was* the agreement.

### 2. Isolated Worktrees as Parallel Sandboxes

Each Engineer agent got its own git worktree -- a full copy of the repo on a separate branch. Three agents could write code simultaneously without merge conflicts. When they finished, each created a PR from its branch. The isolation meant they couldn't interfere with each other even if they tried.

### 3. Role Separation Forces Different Thinking

A single prompt that says "implement and review this feature" produces mediocre output. But splitting the work into three roles -- requirements analyst, implementer, reviewer -- forces three genuinely different perspectives on the same code. The PO caught the user-context propagation requirement. The QA caught edge cases in the interval math. The Engineer just built, fast and focused.

### 4. Wave Dependencies Prevent Chaos

Not everything can run in parallel. The database had to exist before tools could use it. The context builder needed all data sources. Respecting these dependencies meant each wave built on solid ground.

### 5. Existing Patterns as Templates

Every new tool followed the `SpeakTool` pattern. Every new context provider followed the `HeartbeatContext` pattern. Every new test file followed `test_speak_tool.py`. The agents weren't inventing architecture -- they were extending it. This is why consistent patterns in a codebase matter: they make the next feature predictable.

---

## The Moment It All Clicked

After everything merged, I ran the test suite one final time:

```
269 passed in 18.31s
```

Then I added the wiring code -- 66 lines connecting the database, tools, and context provider to the bot's startup sequence. Committed. Pushed.

Then I typed:

```bash
source .venv/bin/activate
python -m nanobot gateway --config config.json
```

And saw:

```
Database connected
Learning tools registered (srs, progress, profile, context)
```

That was it. The bot now remembers who you are. It tracks every word you learn. It knows where you are in the curriculum. It calculates your SRS intervals with real math instead of LLM guesswork. It compiles a teacher's notebook before every conversation.

And when you message it after three days away, it doesn't say "Hello! How can I help you?" It says "Welcome back! It's been a few days -- let's warm up with a quick review of those food vocabulary words from last time."

Because it *knows*. It has the data. And it uses it like a teacher, not a database.

---

## What This Means for the Mission

Remember that mission statement?

> *This product can help thousands of people learn German who can't afford tutors or don't have time for classes.*

With this session's work, DeutschMeister crossed a line. Before, it was a chatbot with a curriculum file. Smart, but stateless. It forgot you between sessions. It couldn't tell you how many words you'd learned because it didn't actually count them. The spaced repetition was theater -- the LLM *pretending* to track intervals.

Now it's real. The SRS engine uses actual SM-2 interval calculations. The progress tracker counts lessons and maintains streaks. The profile persists your timezone and interests. The context builder synthesizes all of this into a teaching document that makes every interaction feel personal.

This is the foundation that makes the pedagogy *work*. A tutor who remembers you, adapts to you, and tracks your growth -- for free, on your schedule, in your pocket.

We're not done. A2 and B1 curricula need writing. Error pattern tracking will make corrections smarter. Pronunciation scoring will close the feedback loop on speaking. But the data layer is here. The tools are registered. The teacher has her notebook.

The learning engine is alive.

---

## The Takeaway

You can orchestrate AI agents to build non-trivial software if you give them three things: **clear requirements** (GitHub issues with acceptance criteria), **isolation** (separate worktrees so they don't collide), and **role separation** (PO/Engineer/QA forces genuinely different perspectives).

The total session produced 5 merged PRs with 153 tests across 18 new files, modifying 8 existing framework files, with parallel execution in Waves 2 and 3. Every PR was reviewed by a QA agent before merge. Every test suite run was green.

I didn't write the code. I wrote the plan, created the issues, and conducted the orchestra. The agents read the existing patterns, implemented against the specs, reviewed each other's work, and merged clean PRs.

Is this the future of software development? I don't know. But I'll tell you this: I sat in my chair, drank my coffee, and watched five foundational features materialize from GitHub issues into tested, reviewed, merged code. And then I restarted my bot, and it remembered my name.

*Das ist erst der Anfang.*

*(This is just the beginning.)*

---

*DeutschMeister is open source at [github.com/rgg81/deutsch-meister](https://github.com/rgg81/deutsch-meister). Built with NanoBot + GitHub Copilot + Claude Code. The AI that orchestrated the AIs that built the learning engine that teaches me German. Turtles all the way down.*

*Previous posts: [Part 1: Building the bot for $0/month] | [Part 2: Teaching it to listen and speak]*
