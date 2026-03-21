-- ╔════════════════════════════════════════════╗
-- ║  Hifz Bot — SQLite Schema v5 (full)       ║
-- ╚════════════════════════════════════════════╝

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL,
    language        TEXT    NOT NULL DEFAULT 'en',
    timezone        TEXT    NOT NULL DEFAULT 'Asia/Tashkent',
    preferred_qari  TEXT    NOT NULL DEFAULT 'ar.alafasy',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS progress (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    surah_number  INTEGER NOT NULL,
    ayah_number   INTEGER NOT NULL,
    memorized     INTEGER NOT NULL DEFAULT 0,
    last_reviewed TEXT,
    UNIQUE(user_id, surah_number, ayah_number)
);

CREATE TABLE IF NOT EXISTS settings (
    user_id           INTEGER PRIMARY KEY REFERENCES users(id),
    daily_goal_ayahs  INTEGER DEFAULT 3,
    study_plan        TEXT    DEFAULT 'standard',
    custom_plan_ayahs INTEGER DEFAULT 3,
    awaiting_input    TEXT    DEFAULT NULL,
    preferred_reciter TEXT    DEFAULT 'ar.alafasy'
);

CREATE TABLE IF NOT EXISTS reminders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    reminder_time TEXT    NOT NULL,
    enabled       INTEGER NOT NULL DEFAULT 1,
    UNIQUE(user_id, reminder_time)
);

CREATE TABLE IF NOT EXISTS gamification (
    user_id              INTEGER PRIMARY KEY REFERENCES users(id),
    total_xp             INTEGER NOT NULL DEFAULT 0,
    current_streak       INTEGER NOT NULL DEFAULT 0,
    longest_streak       INTEGER NOT NULL DEFAULT 0,
    league               TEXT    NOT NULL DEFAULT 'bronze',
    last_activity        TEXT,
    badges               TEXT    NOT NULL DEFAULT '[]',
    quiz_correct_count   INTEGER NOT NULL DEFAULT 0,
    recitation_count     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS quiz_sessions (
    user_id        INTEGER PRIMARY KEY REFERENCES users(id),
    mode           TEXT    NOT NULL DEFAULT 'surah_order',
    surah_filter   INTEGER DEFAULT NULL,
    question_num   INTEGER NOT NULL DEFAULT 0,
    correct_count  INTEGER NOT NULL DEFAULT 0,
    total_count    INTEGER NOT NULL DEFAULT 20,
    asked_ids      TEXT    NOT NULL DEFAULT '[]',
    active         INTEGER NOT NULL DEFAULT 0,
    msg_id         INTEGER DEFAULT NULL,
    daily_count    INTEGER NOT NULL DEFAULT 0,
    last_quiz_date TEXT    DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS learning_sessions (
    user_id        INTEGER PRIMARY KEY REFERENCES users(id),
    surah_number   INTEGER NOT NULL DEFAULT 2,
    current_ayah   INTEGER NOT NULL DEFAULT 1,
    ayah_in_cycle  INTEGER NOT NULL DEFAULT 0,
    prev_ayah      INTEGER DEFAULT NULL,
    state          TEXT    NOT NULL DEFAULT 'INTRO',
    active         INTEGER NOT NULL DEFAULT 0,
    msg_id         INTEGER DEFAULT NULL,
    daily_ayahs    INTEGER NOT NULL DEFAULT 0,
    last_flow_date TEXT    DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS premium (
    user_id    INTEGER PRIMARY KEY REFERENCES users(id),
    active     INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT    DEFAULT NULL,
    granted_at TEXT    DEFAULT NULL,
    granted_by TEXT    DEFAULT 'admin'
);

CREATE TABLE IF NOT EXISTS payment_requests (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL REFERENCES users(id),
    photo_file_id  TEXT    NOT NULL,
    status         TEXT    NOT NULL DEFAULT 'pending',
    decline_reason TEXT    DEFAULT NULL,
    requested_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    reviewed_at    TEXT    DEFAULT NULL,
    admin_msg_id   INTEGER DEFAULT NULL
);

-- Ayah image Telegram file_id cache (avoid re-uploading)
CREATE TABLE IF NOT EXISTS ayah_images (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    surah_number     INTEGER NOT NULL,
    ayah_number      INTEGER NOT NULL,
    telegram_file_id TEXT    NOT NULL,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(surah_number, ayah_number)
);

-- Per-ayah interaction log: quiz answers and recitations
CREATE TABLE IF NOT EXISTS ayah_interactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    surah_number  INTEGER NOT NULL,
    ayah_number   INTEGER NOT NULL,
    interaction   TEXT    NOT NULL,  -- 'quiz_correct','quiz_wrong','recitation','flow_memorized'
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ayah_inter_user ON ayah_interactions(user_id, interaction);

CREATE TABLE IF NOT EXISTS group_xatms (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id    INTEGER REFERENCES users(id),
    status        TEXT    NOT NULL DEFAULT 'recruiting', -- 'recruiting', 'active', 'completed'
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    started_at    TEXT,
    completed_at  TEXT
);

CREATE TABLE IF NOT EXISTS group_xatm_juzs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    xatm_id       INTEGER NOT NULL REFERENCES group_xatms(id),
    juz_number    INTEGER NOT NULL,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    status        TEXT    NOT NULL DEFAULT 'assigned', -- 'assigned', 'completed'
    assigned_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    completed_at  TEXT,
    UNIQUE(xatm_id, juz_number)
);
