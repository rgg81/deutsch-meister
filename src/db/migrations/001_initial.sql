-- Initial schema: users, vocab_cards, lesson_records, user_progress

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id TEXT NOT NULL UNIQUE,
    display_name TEXT,
    cefr_level TEXT NOT NULL DEFAULT 'A1',
    timezone TEXT DEFAULT 'Europe/Berlin',
    native_language TEXT DEFAULT 'en',
    daily_goal_minutes INTEGER DEFAULT 60,
    preferred_lesson_time TEXT DEFAULT 'morning',
    interests TEXT,  -- JSON array
    onboarding_complete INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vocab_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    word_de TEXT NOT NULL,
    word_en TEXT NOT NULL,
    gender TEXT,  -- nullable: only nouns have gender (der/die/das)
    plural TEXT,
    part_of_speech TEXT,
    example_sentence TEXT,
    interval_days INTEGER NOT NULL DEFAULT 0,
    ease_factor REAL NOT NULL DEFAULT 2.5,
    next_review TEXT,  -- ISO date, NULL = new card
    review_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    audio_cached INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lesson_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_date TEXT NOT NULL,
    block INTEGER,  -- 1=warm-up, 2=core, 3=recap
    story_type TEXT,  -- alltag, abenteuer, kultur, gespraech, fortsetzung, schreibwerkstatt, rueckblick
    theme TEXT,
    grammar_topic TEXT,
    duration_minutes INTEGER,
    completed INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    cefr_level TEXT NOT NULL DEFAULT 'A1',
    theme_index INTEGER NOT NULL DEFAULT 0,
    grammar_index INTEGER NOT NULL DEFAULT 0,
    phase INTEGER NOT NULL DEFAULT 1,
    week_number INTEGER NOT NULL DEFAULT 1,
    words_learned INTEGER NOT NULL DEFAULT 0,
    lessons_completed INTEGER NOT NULL DEFAULT 0,
    current_streak INTEGER NOT NULL DEFAULT 0,
    longest_streak INTEGER NOT NULL DEFAULT 0,
    last_lesson_date TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_vocab_user_review ON vocab_cards(user_id, next_review);
CREATE INDEX IF NOT EXISTS idx_vocab_user_word ON vocab_cards(user_id, word_de);
CREATE INDEX IF NOT EXISTS idx_lessons_user_date ON lesson_records(user_id, lesson_date);
