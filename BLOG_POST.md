# I Built a Personal German Tutor in a Weekend for $0/Month

What if you could have a patient, always-available German tutor that follows an actual curriculum, remembers every word you've struggled with, and costs you nothing? I built one in a weekend.

**DeutschMeister** is a personal German language tutor that lives in Telegram, follows the CEFR framework from A1 to B1, uses spaced repetition to drill vocabulary, and runs on a GitHub Copilot subscription I already pay for. No API keys, no usage-based billing, no vendor lock-in surprises.

Here's how I put it together.

---

## The Problem with Language Apps

I wanted to learn German. Properly. Not "learn 5 words a day and feel good about yourself" — I wanted structured CEFR-aligned lessons, grammar drills, vocabulary tracking with spaced repetition, and a tutor that adapts to my schedule and interests.

Duolingo is gamified to the point of distraction. Private tutors cost €30+/hour. ChatGPT can help, but it doesn't remember your progress, doesn't follow a curriculum, and you have to drive the conversation yourself.

I wanted something in between: a personal tutor that's structured like a real course but lives in the app I already check 50 times a day — Telegram.

---

## The Architecture: Markdown All the Way Down

DeutschMeister is built on [NanoBot](https://github.com/nano-bot), a Python agent framework I vendored into the project. NanoBot handles the hard parts: the agent loop, LLM provider abstraction (via litellm), channel adapters (Telegram, Slack, etc.), tool system, cron scheduling, and skill loading.

The project structure looks like this:

```
deutsch-meister/
├── nanobot/          # Vendored agent framework
├── workspace/
│   ├── SOUL.md       # Agent personality & teaching philosophy
│   └── HEARTBEAT.md  # Daily check-in nudge rules
├── skills/
│   └── deutsch-meister/
│       └── SKILL.md  # Lesson structure, SRS logic, slash commands
├── curriculum/
│   └── a1.md         # CEFR A1 reference: themes, grammar, word targets
├── src/              # Custom Python modules (SRS engine, progress tracking)
├── config.json       # LLM provider, Telegram token, allowed users
└── docker-compose.yml
```

The key insight: **the entire teaching persona is defined in markdown files**, not code.

- **SOUL.md** defines *who* the tutor is — patient, encouraging, structured, gently corrective. It sets the teaching philosophy: one concept at a time, celebrate small wins, mix grammar with practical exercises.

- **SKILL.md** is the operational brain. It defines a full daily lesson structure (warm-up → core lesson → evening recap), a weekly rotation (Monday: vocabulary, Tuesday: grammar, Wednesday: reading, etc.), slash commands (`/status`, `/review`, `/quiz`, `/vocab`), SRS review logic, and communication style rules (message length, German/English ratio, correction format).

- **HEARTBEAT.md** handles the nudge. If the user hasn't messaged in 24 hours, the bot sends a gentle reminder referencing whatever topic was last covered. No guilt-tripping — just a warm *"Hey! Ready to practice? We left off on ordering food — Ich möchte einen Kaffee, bitte!"*

This "personality as markdown" approach means I can iterate on the tutor's behavior by editing text files. No redeployment, no code changes. Want to adjust the German/English ratio? Edit a line in SKILL.md. Want to change how corrections are formatted? Same file. The LLM interprets the markdown instructions on every interaction.

---

## The $0/Month Trick: GitHub Copilot as Your LLM

Here's the part that makes this practically free to run.

NanoBot uses litellm for LLM provider abstraction. Instead of paying for OpenAI API calls or Anthropic credits, I pointed it at **GitHub Copilot** — which I already have through my GitHub subscription.

The `config.json` is minimal:

```json
{
  "providers": {
    "github_copilot": {}
  },
  "agents": {
    "defaults": {
      "model": "github_copilot/gpt-4o",
      "provider": "github_copilot"
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_TELEGRAM_USER_ID"]
    }
  }
}
```

GitHub Copilot authenticates via OAuth — no API key to manage, no usage meter ticking up. The first time you run the agent (`python -m nanobot agent -m "test"`), it triggers the Copilot OAuth flow, and after that it just works.

The `allowFrom` field in the Telegram config is the access control — only my Telegram user ID can talk to the bot. Simple, effective, no auth middleware needed.

---

## The Curriculum: Actually Structured Learning

I didn't want a chatbot that answers German questions when you ask. I wanted a **curriculum**.

The `curriculum/a1.md` file is a comprehensive CEFR A1 reference aligned to the Goethe-Zertifikat A1 exam. It contains:

- **15 vocabulary themes** ordered by difficulty: Greetings → Numbers → Days/Months → Colors → Family → Food → Daily Routines → Home → Clothing → Weather → Directions → Hobbies → Body/Health → Shopping → Time Expressions

- **15 grammar topics** in pedagogical progression: Personal Pronouns → Regular Verbs → Irregular Verbs (sein/haben/werden) → Articles & Gender → Negation → Word Order → Questions → Accusative Case → Modal Verbs → Separable Verbs → Accusative Prepositions → Dative Case → Possessives → Perfekt Tense → Imperative

- **800-word target** over 8–12 weeks at one hour per day, with clear milestones: ~160 words by week 3, ~400 by week 6, ~640 by week 9, ~800 by week 12

The SKILL.md file tells the agent *how* to use this curriculum — rotate through themes, introduce grammar in order, track which words are new and which need review.

---

## Spaced Repetition Without a Database (Yet)

The SRS logic is defined right in SKILL.md:

- New words enter the review queue after first encounter
- Review intervals follow an SM-2-inspired pattern: 1 day → 3 days → 7 days → 14 days → 30 days
- Correct answer: advance to next interval. Incorrect: reset to 1 day
- Daily cap of 20 review items to prevent overload

Right now this relies on the LLM's context and conversation history to track what's been reviewed. The next step is building a proper SRS engine in Python (in `src/`) backed by SQLite — queryable, persistent, with real interval calculations. But the markdown-defined logic already gives the agent a clear framework for *how* to space reviews, which is the hard part to get right from a pedagogical standpoint.

---

## Claude Code as Pair Programmer

I didn't build this alone — I built it with Claude Code.

The development workflow was: I'd describe what I wanted, Claude Code would implement it, and we'd iterate. The GitHub Actions workflow (`.github/workflows/claude.yml`) integrates Claude Code directly into the repo — mention `@claude` in an issue or PR comment and it spins up to help.

Claude Code wrote the curriculum reference, drafted the SOUL.md persona, structured the SKILL.md lesson logic, and helped debug the NanoBot integration. PRs were reviewed by both me and Claude. It's a genuine pair programming workflow where the AI handles the boilerplate and domain research (CEFR standards, Goethe exam alignment, SM-2 algorithm details) while I focus on architecture decisions and what I actually want the tutor to *feel* like.

The restricted tool access in CI (`allowed_tools: "Bash(git clone*),Bash(git subtree*)"`) keeps the automation safe — Claude can research and draft but can't run arbitrary commands in the pipeline.

---

## What's Next

DeutschMeister works today as a conversational tutor, but there's more to build:

- **SRS engine in Python** — Move spaced repetition from "LLM following instructions" to a proper Python module with SQLite persistence. Real interval calculations, progress queries, exportable stats.

- **A2 and B1 curricula** — The A1 curriculum exists; A2 and B1 need the same treatment (vocabulary themes, grammar topics, word targets, exam alignment).

- **Progress tracking** — SQLite database for vocabulary state, lesson history, streak tracking. The `/status` and `/report` commands exist in the skill definition but need a backend to be truly useful.

- **Exercise generators** — Programmatic generation of fill-in-the-blank, word reordering, and translation exercises instead of relying entirely on the LLM.

---

## The Takeaway

You don't need a massive budget or a complex tech stack to build a sophisticated AI application. DeutschMeister is:

- A vendored Python framework (NanoBot)
- Three markdown files defining the entire teaching persona
- A curriculum reference document
- A JSON config file
- A GitHub Copilot subscription you probably already have

The architecture decisions that made this work in a weekend:

1. **Personality as markdown** — Don't hardcode behavior. Write it in natural language and let the LLM interpret it. Iterate by editing text files.

2. **Leverage existing subscriptions** — GitHub Copilot via OAuth means no API key management and no per-token billing.

3. **Vendor the framework** — NanoBot gives you the agent loop, channel adapters, and tool system. Don't rebuild infrastructure.

4. **Start with the curriculum, not the code** — The most valuable part of DeutschMeister isn't the Python — it's the A1 curriculum reference with 15 themes, 15 grammar topics, and clear progression targets. Get the content right first.

5. **Use AI to build AI** — Claude Code as pair programmer accelerated everything. The AI researched CEFR standards, drafted exam-aligned content, and reviewed its own PRs.

The best part? I'm actually learning German. *Jeden Tag ein bisschen besser.*

---

*DeutschMeister is open source. The project runs on NanoBot + GitHub Copilot + Telegram. If you want to build your own language tutor — or any AI-powered personal tool — the approach generalizes: find a framework, define behavior in markdown, point it at an LLM you already have access to, and ship it to a channel you already use.*
