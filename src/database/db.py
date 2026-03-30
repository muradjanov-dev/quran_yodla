"""Database layer — full v3 with premium, payment, free-tier helpers."""
import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime, date, timedelta

DB_PATH = Path(__file__).resolve().parents[2] / "hifz.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

ADMIN_ID = 917456291
FREE_QUIZ_DAILY = 10      # free questions per day
FREE_FLOW_DAILY = 5       # free ayahs per day
FREE_REMINDERS  = 2       # max reminders on free plan
FREE_LB_ROWS    = 10      # leaderboard rows visible

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_conn() as conn:
        conn.executescript(schema)
    print(f"[DB] Initialized at {DB_PATH}")

# ── Users ──────────────────────────────────────────────────────────────────
def get_user(user_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()

def upsert_user(user_id: int, name: str, language: str = "en"):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users(id,name,language) VALUES(?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name",
            (user_id, name, language),
        )

def set_user_language(user_id: int, language: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET language=? WHERE id=?", (language, user_id))

def get_total_users() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

def get_active_today() -> int:
    today = date.today().isoformat()
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM gamification WHERE last_activity=?", (today,)
        ).fetchone()[0]

def get_total_memorized() -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM progress WHERE memorized=1"
        ).fetchone()[0]

def get_inactive_users() -> list[sqlite3.Row]:
    """Users with no goals set or no memorization at all — for daily motivation."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT u.id, u.name, u.language FROM users u "
            "LEFT JOIN settings s ON s.user_id=u.id "
            "LEFT JOIN progress p ON p.user_id=u.id AND p.memorized=1 "
            "WHERE s.daily_goal_ayahs IS NULL OR s.daily_goal_ayahs=3 AND p.id IS NULL "
            "GROUP BY u.id"
        ).fetchall()

# ── Settings ───────────────────────────────────────────────────────────────
def get_settings(user_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM settings WHERE user_id=?", (user_id,)).fetchone()

def ensure_settings(user_id: int):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO settings(user_id) VALUES(?)", (user_id,))

def update_settings(user_id: int, **kwargs):
    ensure_settings(user_id)
    allowed = {"daily_goal_ayahs","study_plan","custom_plan_ayahs","awaiting_input","preferred_reciter"}
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    if not filtered:
        return
    sets = ", ".join(f"{k}=?" for k in filtered)
    vals = list(filtered.values()) + [user_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE settings SET {sets} WHERE user_id=?", vals)

# ── Reminders ─────────────────────────────────────────────────────────────
def get_reminders(user_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM reminders WHERE user_id=? ORDER BY reminder_time",
            (user_id,),
        ).fetchall()

def add_reminder(user_id: int, reminder_time: str, premium: bool = False) -> tuple[bool, str]:
    """Returns (success, reason). Max depends on plan."""
    existing = get_reminders(user_id)
    max_allowed = 10 if premium else FREE_REMINDERS
    if len(existing) >= max_allowed:
        return False, "max"
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO reminders(user_id, reminder_time) VALUES(?,?)",
                (user_id, reminder_time),
            )
        return True, "ok"
    except sqlite3.IntegrityError:
        return False, "exists"

def remove_reminder(user_id: int, reminder_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM reminders WHERE id=? AND user_id=?", (reminder_id, user_id))

def get_all_users_for_reminder(current_time: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT u.id, u.name, u.language, s.daily_goal_ayahs "
            "FROM reminders r "
            "JOIN users u ON u.id=r.user_id "
            "JOIN settings s ON s.user_id=r.user_id "
            "WHERE r.reminder_time=? AND r.enabled=1",
            (current_time,),
        ).fetchall()

# ── Progress ───────────────────────────────────────────────────────────────
def get_progress(user_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM progress WHERE user_id=? ORDER BY surah_number, ayah_number",
            (user_id,),
        ).fetchall()

def mark_ayah(user_id: int, surah_number: int, ayah_number: int, memorized: bool = True):
    ts = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO progress(user_id,surah_number,ayah_number,memorized,last_reviewed) "
            "VALUES(?,?,?,?,?) "
            "ON CONFLICT(user_id,surah_number,ayah_number) "
            "DO UPDATE SET memorized=excluded.memorized, last_reviewed=excluded.last_reviewed",
            (user_id, surah_number, ayah_number, int(memorized), ts),
        )

def count_memorized_in_surah(user_id: int, surah_number: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM progress WHERE user_id=? AND surah_number=? AND memorized=1",
            (user_id, surah_number),
        ).fetchone()
    return row[0] if row else 0

def get_current_surah(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT surah_number FROM progress WHERE user_id=? ORDER BY surah_number DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    return row["surah_number"] if row else 1

def set_active_surah(user_id: int, surah_number: int):
    """Set the single active surah shared by Flow and Quiz sections."""
    with get_conn() as conn:
        conn.execute("UPDATE users SET active_surah=? WHERE id=?", (surah_number, user_id))

def get_active_surah(user_id: int) -> int:
    """Get the active surah (defaults to 1 = Al-Fatiha)."""
    with get_conn() as conn:
        row = conn.execute("SELECT active_surah FROM users WHERE id=?", (user_id,)).fetchone()
    if row:
        return dict(row).get("active_surah") or 1
    return 1

# ── Gamification ───────────────────────────────────────────────────────────
def get_gamification(user_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM gamification WHERE user_id=?", (user_id,)).fetchone()

def ensure_gamification(user_id: int):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO gamification(user_id) VALUES(?)", (user_id,))

def add_xp(user_id: int, amount: int) -> tuple[int, str, str | None]:
    ensure_gamification(user_id)
    LEAGUES = [("bronze",0),("silver",500),("gold",1500),("diamond",3000)]
    with get_conn() as conn:
        row = conn.execute("SELECT total_xp, league FROM gamification WHERE user_id=?", (user_id,)).fetchone()
        old_xp, old_league = row["total_xp"], row["league"]
        new_xp = old_xp + amount
        new_league = next((n for n, t in reversed(LEAGUES) if new_xp >= t), "bronze")
        conn.execute("UPDATE gamification SET total_xp=?, league=? WHERE user_id=?",
                     (new_xp, new_league, user_id))
    return new_xp, new_league, (new_league if new_league != old_league else None)

def update_streak(user_id: int) -> tuple[int, bool]:
    ensure_gamification(user_id)
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT current_streak, longest_streak, last_activity FROM gamification WHERE user_id=?",
            (user_id,),
        ).fetchone()
        last, streak, longest = row["last_activity"], row["current_streak"], row["longest_streak"]
        reset = False
        if last == today:
            pass
        elif last == (date.today() - timedelta(days=1)).isoformat():
            streak += 1
        else:
            reset = streak > 0
            streak = 1
        longest = max(longest, streak)
        conn.execute("UPDATE gamification SET current_streak=?, longest_streak=?, last_activity=? WHERE user_id=?",
                     (streak, longest, today, user_id))
    return streak, reset

def unlock_badge(user_id: int, badge: str) -> bool:
    ensure_gamification(user_id)
    with get_conn() as conn:
        row = conn.execute("SELECT badges FROM gamification WHERE user_id=?", (user_id,)).fetchone()
        badges = json.loads(row["badges"])
        if badge in badges:
            return False
        badges.append(badge)
        conn.execute("UPDATE gamification SET badges=? WHERE user_id=?", (json.dumps(badges), user_id))
    return True

def get_leaderboard(limit: int = 50) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT u.id, u.name, g.total_xp, g.current_streak, g.league "
            "FROM gamification g JOIN users u ON u.id=g.user_id "
            "ORDER BY g.total_xp DESC LIMIT ?", (limit,),
        ).fetchall()

# ── Quiz Sessions ──────────────────────────────────────────────────────────
def get_quiz_session(user_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM quiz_sessions WHERE user_id=?", (user_id,)).fetchone()

def init_quiz_session(user_id: int, mode: str, surah_filter: int | None = None, total: int = 20):
    today = date.today().isoformat()
    with get_conn() as conn:
        existing = conn.execute("SELECT daily_count, last_quiz_date FROM quiz_sessions WHERE user_id=?",
                                (user_id,)).fetchone()
        daily = 0
        if existing:
            daily = existing["daily_count"] if existing["last_quiz_date"] == today else 0
        conn.execute(
            "INSERT INTO quiz_sessions(user_id,mode,surah_filter,question_num,correct_count,"
            "total_count,asked_ids,active,msg_id,daily_count,last_quiz_date) "
            "VALUES(?,?,?,0,0,?,'[]',1,NULL,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET mode=excluded.mode,surah_filter=excluded.surah_filter,"
            "question_num=0,correct_count=0,total_count=excluded.total_count,asked_ids='[]',active=1,"
            "msg_id=NULL,daily_count=excluded.daily_count,last_quiz_date=excluded.last_quiz_date",
            (user_id, mode, surah_filter, total, daily, today),
        )

def update_quiz_session(user_id: int, **kwargs):
    allowed = {"question_num","correct_count","asked_ids","active","msg_id","daily_count","last_quiz_date"}
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    if not filtered:
        return
    sets = ", ".join(f"{k}=?" for k in filtered)
    with get_conn() as conn:
        conn.execute(f"UPDATE quiz_sessions SET {sets} WHERE user_id=?",
                     list(filtered.values()) + [user_id])

def get_quiz_daily_count(user_id: int) -> int:
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute("SELECT daily_count, last_quiz_date FROM quiz_sessions WHERE user_id=?",
                           (user_id,)).fetchone()
    if not row or row["last_quiz_date"] != today:
        return 0
    return row["daily_count"]

# ── Learning Sessions ─────────────────────────────────────────────────────
def get_learning_session(user_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM learning_sessions WHERE user_id=?", (user_id,)).fetchone()

def init_learning_session(user_id: int, surah_number: int, start_ayah: int):
    today = date.today().isoformat()
    with get_conn() as conn:
        existing = conn.execute("SELECT daily_ayahs, last_flow_date FROM learning_sessions WHERE user_id=?",
                                (user_id,)).fetchone()
        daily = 0
        if existing:
            daily = existing["daily_ayahs"] if existing["last_flow_date"] == today else 0
        conn.execute(
            "INSERT INTO learning_sessions(user_id,surah_number,current_ayah,ayah_in_cycle,"
            "prev_ayah,state,active,msg_id,daily_ayahs,last_flow_date) "
            "VALUES(?,?,?,0,NULL,'READ_3',1,NULL,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET surah_number=excluded.surah_number,"
            "current_ayah=excluded.current_ayah,ayah_in_cycle=0,prev_ayah=NULL,"
            "state='READ_3',active=1,msg_id=NULL,daily_ayahs=excluded.daily_ayahs,last_flow_date=excluded.last_flow_date",
            (user_id, surah_number, start_ayah, daily, today),
        )

def update_learning_session(user_id: int, **kwargs):
    allowed = {"surah_number","current_ayah","ayah_in_cycle","prev_ayah","state","active","msg_id",
               "daily_ayahs","last_flow_date"}
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    if not filtered:
        return
    sets = ", ".join(f"{k}=?" for k in filtered)
    with get_conn() as conn:
        conn.execute(f"UPDATE learning_sessions SET {sets} WHERE user_id=?",
                     list(filtered.values()) + [user_id])

def get_flow_daily_count(user_id: int) -> int:
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute("SELECT daily_ayahs, last_flow_date FROM learning_sessions WHERE user_id=?",
                           (user_id,)).fetchone()
    if not row or row["last_flow_date"] != today:
        return 0
    return row["daily_ayahs"]

def increment_flow_daily(user_id: int):
    today = date.today().isoformat()
    current = get_flow_daily_count(user_id)
    update_learning_session(user_id, daily_ayahs=current + 1, last_flow_date=today)

# ── Premium ───────────────────────────────────────────────────────────────
def is_premium(user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT active, expires_at FROM premium WHERE user_id=?", (user_id,)).fetchone()
    if not row or not row["active"]:
        return False
    if row["expires_at"] and row["expires_at"] < datetime.utcnow().isoformat():
        # Expired — deactivate
        with get_conn() as conn:
            conn.execute("UPDATE premium SET active=0 WHERE user_id=?", (user_id,))
        return False
    return True

def grant_premium(user_id: int, months: int = 1):
    now = datetime.utcnow()
    expires = (now + timedelta(days=30 * months)).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO premium(user_id,active,expires_at,granted_at) VALUES(?,1,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET active=1,expires_at=excluded.expires_at,granted_at=excluded.granted_at",
            (user_id, expires, now.isoformat()),
        )

def revoke_premium(user_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE premium SET active=0 WHERE user_id=?", (user_id,))

def get_premium_info(user_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM premium WHERE user_id=?", (user_id,)).fetchone()

# ── Payment Requests ──────────────────────────────────────────────────────
def create_payment_request(user_id: int, photo_file_id: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO payment_requests(user_id, photo_file_id) VALUES(?,?)",
            (user_id, photo_file_id),
        )
        return cur.lastrowid or 0

def get_payment_request(req_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM payment_requests WHERE id=?", (req_id,)).fetchone()

def update_payment_request(req_id: int, status: str, decline_reason: str | None = None,
                            admin_msg_id: int | None = None):
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE payment_requests SET status=?, decline_reason=?, reviewed_at=?, admin_msg_id=COALESCE(?,admin_msg_id) "
            "WHERE id=?",
            (status, decline_reason, now, admin_msg_id, req_id),
        )

def set_payment_admin_msg(req_id: int, msg_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE payment_requests SET admin_msg_id=? WHERE id=?", (msg_id, req_id))

def get_pending_payments() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT p.*, u.name, u.language FROM payment_requests p "
            "JOIN users u ON u.id=p.user_id WHERE p.status='pending'",
        ).fetchall()

# ── Ayah Image Cache (Telegram file_id) ────────────────────────────────────
def get_cached_ayah_image(surah_number: int, ayah_number: int) -> str | None:
    """Return cached Telegram file_id for ayah image, or None."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT telegram_file_id FROM ayah_images WHERE surah_number=? AND ayah_number=?",
            (surah_number, ayah_number),
        ).fetchone()
    return row["telegram_file_id"] if row else None

def save_ayah_image(surah_number: int, ayah_number: int, telegram_file_id: str):
    """Store Telegram file_id for ayah image."""
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO ayah_images(surah_number, ayah_number, telegram_file_id) "
            "VALUES(?,?,?)",
            (surah_number, ayah_number, telegram_file_id),
        )

def row_dict(row) -> dict:
    """Safely convert sqlite3.Row to dict (avoids .get() AttributeError)."""
    if row is None:
        return {}
    return dict(row)

# ── Preferred Qari (stored in users table) ──────────────────────────────────
def get_preferred_qari(user_id: int) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT preferred_qari FROM users WHERE id=?", (user_id,)).fetchone()
    return (row["preferred_qari"] if row and row["preferred_qari"] else "ar.alafasy")

def set_preferred_qari(user_id: int, edition: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET preferred_qari=? WHERE id=?", (edition, user_id))

# ── Resume Point ─────────────────────────────────────────────────────────────
def get_resume_point(user_id: int) -> dict | None:
    """Return {surah_number, ayah_number, state} of latest learning position."""
    with get_conn() as conn:
        # Active session first
        sess = conn.execute(
            "SELECT surah_number, current_ayah, state FROM learning_sessions "
            "WHERE user_id=? AND active=1",
            (user_id,)
        ).fetchone()
        if sess:
            return {"surah_number": sess["surah_number"],
                    "ayah_number": sess["current_ayah"],
                    "state": sess["state"]}
        # Fallback: last memorized ayah
        prog = conn.execute(
            "SELECT surah_number, MAX(ayah_number) AS ayah FROM progress "
            "WHERE user_id=? AND memorized=1 GROUP BY surah_number "
            "ORDER BY surah_number DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        if prog:
            return {"surah_number": prog["surah_number"],
                    "ayah_number":  prog["ayah"] + 1,
                    "state": "INTRO"}
    return None

# ── Ayah Interactions (quiz/recitation logging) ───────────────────────────────
def log_interaction(user_id: int, surah: int, ayah: int, kind: str):
    """kind: 'quiz_correct' | 'quiz_wrong' | 'recitation' | 'flow_memorized'"""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ayah_interactions(user_id,surah_number,ayah_number,interaction) "
            "VALUES(?,?,?,?)",
            (user_id, surah, ayah, kind),
        )
        # Also bump lifetime counters in gamification
        if kind == 'quiz_correct':
            conn.execute(
                "UPDATE gamification SET quiz_correct_count = quiz_correct_count + 1 WHERE user_id=?",
                (user_id,)
            )
        elif kind == 'recitation':
            conn.execute(
                "UPDATE gamification SET recitation_count = recitation_count + 1 WHERE user_id=?",
                (user_id,)
            )

def get_top_ayahs(user_id: int, n: int = 3) -> list[dict]:
    """Return top N ayahs by number of correct quiz answers."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT surah_number, ayah_number, COUNT(*) AS cnt "
            "FROM ayah_interactions WHERE user_id=? AND interaction='quiz_correct' "
            "GROUP BY surah_number, ayah_number ORDER BY cnt DESC LIMIT ?",
            (user_id, n)
        ).fetchall()
    return [dict(r) for r in rows]

def get_best_surah(user_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT surah_number, COUNT(*) AS cnt "
            "FROM ayah_interactions WHERE user_id=? AND interaction='quiz_correct' "
            "GROUP BY surah_number ORDER BY cnt DESC LIMIT 1",
            (user_id,)
        ).fetchone()
    return dict(row) if row else None

def get_quiz_accuracy(user_id: int) -> dict:
    with get_conn() as conn:
        correct = conn.execute(
            "SELECT COUNT(*) FROM ayah_interactions WHERE user_id=? AND interaction='quiz_correct'",
            (user_id,)
        ).fetchone()[0]
        wrong = conn.execute(
            "SELECT COUNT(*) FROM ayah_interactions WHERE user_id=? AND interaction='quiz_wrong'",
            (user_id,)
        ).fetchone()[0]
        recitations = conn.execute(
            "SELECT COUNT(*) FROM ayah_interactions WHERE user_id=? AND interaction='recitation'",
            (user_id,)
        ).fetchone()[0]
    total = correct + wrong
    return {"correct": correct, "wrong": wrong, "total": total,
            "recitations": recitations,
            "pct": int(correct / total * 100) if total > 0 else 0}

def get_memorized_ayahs(user_id: int) -> list[dict]:
    """Return all memorized ayahs for dynamic quiz generation."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT surah_number, ayah_number FROM progress "
            "WHERE user_id=? AND memorized=1 ORDER BY surah_number, ayah_number",
            (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]

# ── DB Migration (safe column additions) ─────────────────────────────────────
def migrate_db():
    """Add new columns / tables if they don't exist (idempotent)."""
    with get_conn() as conn:
        # preferred_qari in users
        _try_alter(conn, "ALTER TABLE users ADD COLUMN preferred_qari TEXT NOT NULL DEFAULT 'ar.alafasy'")
        # active_surah in users (unified surah shared by all sections)
        _try_alter(conn, "ALTER TABLE users ADD COLUMN active_surah INTEGER NOT NULL DEFAULT 1")
        # quiz_correct_count in gamification
        _try_alter(conn, "ALTER TABLE gamification ADD COLUMN quiz_correct_count INTEGER NOT NULL DEFAULT 0")
        # recitation_count in gamification
        _try_alter(conn, "ALTER TABLE gamification ADD COLUMN recitation_count INTEGER NOT NULL DEFAULT 0")
        # start_ayah in learning_sessions
        _try_alter(conn, "ALTER TABLE learning_sessions ADD COLUMN start_ayah INTEGER NOT NULL DEFAULT 1")
        # ayah_interactions table + index
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS ayah_interactions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                surah_number  INTEGER NOT NULL,
                ayah_number   INTEGER NOT NULL,
                interaction   TEXT    NOT NULL,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_ayah_inter_user ON ayah_interactions(user_id, interaction);
            
            CREATE TABLE IF NOT EXISTS group_xatms (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id    INTEGER REFERENCES users(id),
                status        TEXT    NOT NULL DEFAULT 'recruiting',
                created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                started_at    TEXT,
                completed_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS group_xatm_juzs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                xatm_id       INTEGER NOT NULL REFERENCES group_xatms(id),
                juz_number    INTEGER NOT NULL,
                user_id       INTEGER NOT NULL REFERENCES users(id),
                status        TEXT    NOT NULL DEFAULT 'assigned',
                assigned_at   TEXT    NOT NULL DEFAULT (datetime('now')),
                completed_at  TEXT,
                UNIQUE(xatm_id, juz_number)
            );
        """)

def _try_alter(conn, sql: str):
    try:
        conn.execute(sql)
    except Exception:
        pass

# ── Group Xatms ─────────────────────────────────────────────────────────────
def get_or_create_recruiting_xatm() -> int:
    """Returns the ID of the oldest recruiting Xatm, or creates a new one."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM group_xatms WHERE status='recruiting' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        if row:
            return row["id"]
        cur = conn.execute("INSERT INTO group_xatms(status) VALUES('recruiting')")
        return cur.lastrowid or 0

def create_custom_xatm(creator_id: int) -> int:
    with get_conn() as conn:
        cur = conn.execute("INSERT INTO group_xatms(creator_id, status) VALUES(?,'recruiting')", (creator_id,))
        return cur.lastrowid or 0

def get_xatm(xatm_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM group_xatms WHERE id=?", (xatm_id,)).fetchone()
    return dict(row) if row else None


def get_xatm_juzs(xatm_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM group_xatm_juzs WHERE xatm_id=? ORDER BY juz_number", (xatm_id,)).fetchall()
    return [dict(r) for r in rows]

def assign_xatm_juz(xatm_id: int, juz_number: int, user_id: int) -> bool:
    """Assigns a juz if available. Returns False if already taken."""
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO group_xatm_juzs(xatm_id, juz_number, user_id, status) VALUES(?,?,?,'assigned')",
                (xatm_id, juz_number, user_id)
            )
        return True
    except sqlite3.IntegrityError:
        return False

def complete_xatm_juz(xatm_id: int, juz_number: int, user_id: int) -> bool:
    """Marks juz as completed. Returns True if successfully updated."""
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE group_xatm_juzs SET status='completed', completed_at=? WHERE xatm_id=? AND juz_number=? AND user_id=?",
            (now, xatm_id, juz_number, user_id)
        )
        return cur.rowcount > 0

def check_and_update_xatm_status(xatm_id: int) -> str | None:
    """Checks if Xatm should become 'active' or 'completed' and updates it. Returns the new status if changed."""
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        xatm = conn.execute("SELECT status FROM group_xatms WHERE id=?", (xatm_id,)).fetchone()
        if not xatm: return None
        status = xatm["status"]
        
        juzs = conn.execute("SELECT juz_number, status FROM group_xatm_juzs WHERE xatm_id=?", (xatm_id,)).fetchall()
        
        if status == 'recruiting' and len(juzs) == 30:
            conn.execute("UPDATE group_xatms SET status='active', started_at=? WHERE id=?", (now, xatm_id))
            return 'active'
            
        if status == 'active' and len(juzs) == 30 and all(j["status"] == 'completed' for j in juzs):
            conn.execute("UPDATE group_xatms SET status='completed', completed_at=? WHERE id=?", (now, xatm_id))
            return 'completed'
            
    return None

def get_all_users() -> list:
    with get_conn() as conn:
        return conn.execute("SELECT id, name, language FROM users").fetchall()

def get_new_users_today() -> int:
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM users WHERE created_at >= ?", (today,)
        ).fetchone()
    return row[0] if row else 0

def get_premium_count() -> int:
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM premium WHERE active=1 AND (expires_at IS NULL OR expires_at > ?)",
            (now,)
        ).fetchone()
    return row[0] if row else 0

def get_user_xatm_participation(user_id: int) -> dict | None:
    """Returns active xatm participation info for a user, or None."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT j.xatm_id, x.status, "
            "  (SELECT COUNT(*) FROM group_xatm_juzs WHERE xatm_id=j.xatm_id) AS total_juzs, "
            "  (SELECT COUNT(*) FROM group_xatm_juzs WHERE xatm_id=j.xatm_id AND status='completed') AS completed_juzs "
            "FROM group_xatm_juzs j "
            "JOIN group_xatms x ON x.id=j.xatm_id "
            "WHERE j.user_id=? AND x.status IN ('recruiting','active') "
            "ORDER BY j.xatm_id DESC LIMIT 1",
            (user_id,)
        ).fetchone()
    return dict(row) if row else None

def get_xatm_stats() -> dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM group_xatms WHERE status='completed'").fetchone()[0]
        participants = conn.execute("SELECT COUNT(DISTINCT user_id) FROM group_xatm_juzs").fetchone()[0]
        times = conn.execute(
            "SELECT started_at, completed_at FROM group_xatms WHERE status='completed' AND started_at IS NOT NULL AND completed_at IS NOT NULL"
        ).fetchall()
        
    diffs = []
    for t in times:
        try:
            # handle formats properly
            start = datetime.fromisoformat(t["started_at"])
            end = datetime.fromisoformat(t["completed_at"])
            diffs.append((end - start).total_seconds())
        except Exception:
            pass
        
    avg = sum(diffs)/len(diffs) if diffs else 0
    fast = min(diffs) if diffs else 0
    long = max(diffs) if diffs else 0
    
    return {
        "total_xatms": total,
        "total_participants": participants,
        "avg_seconds": avg,
        "fastest_seconds": fast,
        "longest_seconds": long
    }
