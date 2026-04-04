"""
db_service.py — SQLite replacement for firebase_service.py + stats_service.py.

All Firestore-backed functions are reimplemented using sqlite3 with WAL mode.
The get_user() return value reconstructs the same nested dict structure that
the original handlers expect (user["stats"]["himmat_points"], etc.).
"""

import hashlib
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional

import pytz

from config import LOCAL_TZ

logger = logging.getLogger(__name__)

TZ = pytz.timezone(LOCAL_TZ)

# ── DB path ───────────────────────────────────────────────────────────────────

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("DB_PATH", os.path.join(_REPO_ROOT, "hifz.db"))

# Module-level connection (thread-safe with check_same_thread=False + WAL)
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode = WAL")
        _conn.execute("PRAGMA foreign_keys = ON")
        _conn.commit()
    return _conn


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(TZ)


def _now_str() -> str:
    return _now().isoformat()


def _today_str() -> str:
    return _now().strftime("%Y-%m-%d")


def _week_str() -> str:
    n = _now()
    return f"{n.year}-W{n.strftime('%W')}"


def _month_str() -> str:
    return _now().strftime("%Y-%m")


def _year_str() -> str:
    return str(_now().year)


def _generate_referral_code(telegram_id: int) -> str:
    raw = hashlib.md5(str(telegram_id).encode()).hexdigest()[:8].upper()
    return raw


def _row_to_dict(row) -> Optional[dict]:
    if row is None:
        return None
    return dict(row)


def _json_loads(val, default=None):
    if val is None:
        return default
    try:
        return json.loads(val)
    except Exception:
        return default


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db():
    """Creates all tables if they don't exist. Call once on startup."""
    conn = _get_conn()
    conn.executescript("""
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL DEFAULT '',
    full_name TEXT NOT NULL DEFAULT '',
    registration_date TEXT NOT NULL,
    onboarding_complete INTEGER NOT NULL DEFAULT 0,
    location TEXT NOT NULL DEFAULT '',
    memorization_goal TEXT NOT NULL DEFAULT '',
    daily_time_minutes INTEGER NOT NULL DEFAULT 30,
    known_juz_count INTEGER NOT NULL DEFAULT 0,
    known_surahs TEXT NOT NULL DEFAULT '[]',
    premium_is_active INTEGER NOT NULL DEFAULT 0,
    premium_expires_at TEXT DEFAULT NULL,
    premium_trial_used INTEGER NOT NULL DEFAULT 0,
    premium_trial_started_at TEXT DEFAULT NULL,
    stats_total_verses_read INTEGER NOT NULL DEFAULT 0,
    stats_total_repetitions INTEGER NOT NULL DEFAULT 0,
    stats_total_minutes INTEGER NOT NULL DEFAULT 0,
    stats_himmat_points INTEGER NOT NULL DEFAULT 0,
    stats_current_streak_days INTEGER NOT NULL DEFAULT 0,
    stats_longest_streak_days INTEGER NOT NULL DEFAULT 0,
    stats_last_activity_date TEXT DEFAULT NULL,
    memo_current_juz INTEGER DEFAULT NULL,
    memo_current_surah INTEGER DEFAULT NULL,
    memo_current_surah_name TEXT NOT NULL DEFAULT '',
    memo_current_ayah INTEGER NOT NULL DEFAULT 1,
    memo_completed_surahs TEXT NOT NULL DEFAULT '[]',
    memo_completed_juz TEXT NOT NULL DEFAULT '[]',
    memo_direction TEXT NOT NULL DEFAULT 'forward',
    notif_enabled INTEGER NOT NULL DEFAULT 1,
    notif_daily_count INTEGER NOT NULL DEFAULT 1,
    notif_time TEXT NOT NULL DEFAULT '08:00',
    notif_timezone TEXT NOT NULL DEFAULT 'Asia/Tashkent',
    referral_code TEXT UNIQUE DEFAULT NULL,
    referred_by TEXT DEFAULT NULL,
    referral_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id),
    started_at TEXT NOT NULL,
    juz_number INTEGER NOT NULL DEFAULT 1,
    surah_number INTEGER NOT NULL,
    surah_name TEXT NOT NULL DEFAULT '',
    direction TEXT NOT NULL DEFAULT 'forward',
    reciter TEXT NOT NULL DEFAULT 'husary',
    start_ayah INTEGER NOT NULL DEFAULT 1,
    current_ayah_index INTEGER NOT NULL DEFAULT 0,
    stage TEXT NOT NULL DEFAULT 'new_ayah',
    repetitions_done INTEGER NOT NULL DEFAULT 0,
    target_repetitions INTEGER NOT NULL DEFAULT 3,
    session_ayahs_count INTEGER NOT NULL DEFAULT 0,
    session_minutes INTEGER NOT NULL DEFAULT 0,
    daily_ayahs_count INTEGER NOT NULL DEFAULT 0,
    current_ayah_data TEXT NOT NULL DEFAULT '{}',
    accumulated_ayahs TEXT NOT NULL DEFAULT '[]',
    is_active INTEGER NOT NULL DEFAULT 1,
    ayah_started_at TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS activity_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id),
    period_type TEXT NOT NULL CHECK(period_type IN ('day','week','month','year')),
    period_key TEXT NOT NULL,
    verses_read INTEGER NOT NULL DEFAULT 0,
    repetitions INTEGER NOT NULL DEFAULT 0,
    minutes INTEGER NOT NULL DEFAULT 0,
    himmat_earned INTEGER NOT NULL DEFAULT 0,
    surahs_worked TEXT NOT NULL DEFAULT '[]',
    UNIQUE(user_id, period_type, period_key)
);

CREATE TABLE IF NOT EXISTS leaderboard (
    user_id INTEGER PRIMARY KEY REFERENCES users(telegram_id),
    full_name TEXT NOT NULL DEFAULT '',
    username TEXT NOT NULL DEFAULT '',
    total_verses INTEGER NOT NULL DEFAULT 0,
    himmat_points INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS premium_requests (
    request_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id),
    username TEXT NOT NULL DEFAULT '',
    full_name TEXT NOT NULL DEFAULT '',
    receipt_file_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
    requested_at TEXT NOT NULL,
    processed_at TEXT DEFAULT NULL,
    rejection_reason TEXT DEFAULT NULL,
    admin_message_id INTEGER DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS ayah_photos (
    surah_number INTEGER NOT NULL,
    ayah_number INTEGER NOT NULL,
    file_id TEXT NOT NULL,
    added_by INTEGER NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY(surah_number, ayah_number)
);

CREATE TABLE IF NOT EXISTS notifications_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id),
    sent_at TEXT NOT NULL,
    notif_type TEXT NOT NULL,
    message_preview TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS bot_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS group_xatms (
    xatm_id TEXT PRIMARY KEY,
    xatm_number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'recruiting' CHECK(status IN ('recruiting','active','completed')),
    creator_id INTEGER DEFAULT NULL,
    created_at TEXT NOT NULL,
    active_at TEXT DEFAULT NULL,
    completed_at TEXT DEFAULT NULL,
    is_private INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS group_xatm_juzs (
    xatm_id TEXT NOT NULL REFERENCES group_xatms(xatm_id),
    juz_number INTEGER NOT NULL CHECK(juz_number BETWEEN 1 AND 30),
    user_id INTEGER NOT NULL REFERENCES users(telegram_id),
    status TEXT NOT NULL DEFAULT 'assigned' CHECK(status IN ('assigned','completed')),
    assigned_at TEXT NOT NULL,
    completed_at TEXT DEFAULT NULL,
    is_hidden INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(xatm_id, juz_number)
);

CREATE TABLE IF NOT EXISTS achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id),
    achievement_key TEXT NOT NULL,
    title TEXT NOT NULL,
    icon TEXT NOT NULL DEFAULT '🏅',
    himmat_bonus INTEGER NOT NULL DEFAULT 0,
    unlocked_at TEXT NOT NULL,
    notified INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, achievement_key)
);

CREATE TABLE IF NOT EXISTS congrats_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    achiever_id INTEGER NOT NULL,
    recipient_id INTEGER NOT NULL,
    achievement_key TEXT NOT NULL,
    achievement_title TEXT NOT NULL,
    achievement_icon TEXT NOT NULL DEFAULT '🏅',
    sent INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
""")
    conn.commit()
    logger.info(f"DB initialised at {DB_PATH}")


# ── Nested-dict reconstruction ────────────────────────────────────────────────

def _row_to_user(row) -> Optional[dict]:
    """Convert a flat users row into the nested dict the handlers expect."""
    if row is None:
        return None
    r = dict(row)
    return {
        "telegram_id":         r["telegram_id"],
        "username":            r["username"],
        "full_name":           r["full_name"],
        "registration_date":   r["registration_date"],
        "onboarding_complete": bool(r["onboarding_complete"]),
        "location":            r["location"],
        "memorization_goal":   r["memorization_goal"],
        "daily_time_minutes":  r["daily_time_minutes"],
        "known_juz_count":     r["known_juz_count"],
        "known_surahs":        _json_loads(r["known_surahs"], []),
        "premium": {
            "is_active":        bool(r["premium_is_active"]),
            "expires_at":       r["premium_expires_at"],
            "trial_used":       bool(r["premium_trial_used"]),
            "trial_started_at": r["premium_trial_started_at"],
        },
        "stats": {
            "total_verses_read":   r["stats_total_verses_read"],
            "total_repetitions":   r["stats_total_repetitions"],
            "total_minutes":       r["stats_total_minutes"],
            "himmat_points":       r["stats_himmat_points"],
            "current_streak_days": r["stats_current_streak_days"],
            "longest_streak_days": r["stats_longest_streak_days"],
            "last_activity_date":  r["stats_last_activity_date"],
        },
        "memorization_progress": {
            "current_juz":      r["memo_current_juz"],
            "current_surah":    r["memo_current_surah"],
            "current_surah_name": r["memo_current_surah_name"],
            "current_ayah":     r["memo_current_ayah"],
            "completed_surahs": _json_loads(r["memo_completed_surahs"], []),
            "completed_juz":    _json_loads(r["memo_completed_juz"], []),
            "direction":        r["memo_direction"],
        },
        "notification_settings": {
            "enabled":     bool(r["notif_enabled"]),
            "daily_count": r["notif_daily_count"],
            "time":        r["notif_time"],
            "timezone":    r["notif_timezone"],
        },
        "referral_code":  r["referral_code"],
        "referred_by":    r["referred_by"],
        "referral_count": r["referral_count"],
    }


def _row_to_session(row) -> Optional[dict]:
    if row is None:
        return None
    r = dict(row)
    r["is_active"] = bool(r["is_active"])
    r["current_ayah_data"] = _json_loads(r.get("current_ayah_data"), {})
    r["accumulated_ayahs"] = _json_loads(r.get("accumulated_ayahs"), [])
    return r


# ── Dot-notation update helper ────────────────────────────────────────────────

# Mapping from dot-notation field paths (as used by handlers) to flat column names
_DOT_TO_COL = {
    # premium
    "premium.is_active":        "premium_is_active",
    "premium.expires_at":       "premium_expires_at",
    "premium.trial_used":       "premium_trial_used",
    "premium.trial_started_at": "premium_trial_started_at",
    # stats
    "stats.total_verses_read":   "stats_total_verses_read",
    "stats.total_repetitions":   "stats_total_repetitions",
    "stats.total_minutes":       "stats_total_minutes",
    "stats.himmat_points":       "stats_himmat_points",
    "stats.current_streak_days": "stats_current_streak_days",
    "stats.longest_streak_days": "stats_longest_streak_days",
    "stats.last_activity_date":  "stats_last_activity_date",
    # memorization_progress
    "memorization_progress.current_juz":       "memo_current_juz",
    "memorization_progress.current_surah":     "memo_current_surah",
    "memorization_progress.current_surah_name":"memo_current_surah_name",
    "memorization_progress.current_ayah":      "memo_current_ayah",
    "memorization_progress.completed_surahs":  "memo_completed_surahs",
    "memorization_progress.completed_juz":     "memo_completed_juz",
    "memorization_progress.direction":         "memo_direction",
    # notification_settings
    "notification_settings.enabled":     "notif_enabled",
    "notification_settings.daily_count": "notif_daily_count",
    "notification_settings.time":        "notif_time",
    "notification_settings.timezone":    "notif_timezone",
}

# Columns whose values should be JSON-serialised (lists/dicts)
_JSON_COLS = {
    "known_surahs", "memo_completed_surahs", "memo_completed_juz",
}

# Boolean columns stored as INTEGER 0/1
_BOOL_COLS = {
    "onboarding_complete", "premium_is_active", "premium_trial_used",
    "notif_enabled",
}


def _flatten_data(data: dict) -> dict:
    """
    Converts a dict that may use dot-notation keys (e.g. 'stats.himmat_points')
    or nested dicts into flat column names for the users table.
    """
    flat = {}
    for key, val in data.items():
        if key in _DOT_TO_COL:
            col = _DOT_TO_COL[key]
        elif "." not in key:
            col = key
        else:
            # unknown dot path — skip
            logger.warning(f"_flatten_data: unknown key '{key}', skipping")
            continue

        if col in _JSON_COLS and isinstance(val, (list, dict)):
            val = json.dumps(val, ensure_ascii=False)
        elif col in _BOOL_COLS:
            val = 1 if val else 0

        flat[col] = val
    return flat


# ═══════════════════════════════════════════════════════════════════════════════
# USER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_user(telegram_id: int) -> Optional[dict]:
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return _row_to_user(row)
    except Exception as e:
        logger.error(f"get_user error: {e}")
        return None


def create_user(telegram_id: int, username: str, full_name: str,
                referred_by: Optional[str] = None) -> dict:
    ref_code = _generate_referral_code(telegram_id)
    now_str = _now_str()
    try:
        conn = _get_conn()
        conn.execute("""
            INSERT OR IGNORE INTO users (
                telegram_id, username, full_name, registration_date,
                onboarding_complete, referral_code, referred_by, referral_count,
                notif_timezone
            ) VALUES (?, ?, ?, ?, 0, ?, ?, 0, ?)
        """, (
            telegram_id,
            username or "",
            full_name or "",
            now_str,
            ref_code,
            referred_by,
            LOCAL_TZ,
        ))
        conn.commit()
    except Exception as e:
        logger.error(f"create_user error: {e}")
    return get_user(telegram_id) or {}


def update_user(telegram_id: int, data: dict):
    """Update user fields. Keys may use dot-notation (e.g. 'stats.himmat_points')."""
    flat = _flatten_data(data)
    if not flat:
        return
    try:
        conn = _get_conn()
        set_clause = ", ".join(f"{col} = ?" for col in flat)
        values = list(flat.values()) + [telegram_id]
        conn.execute(
            f"UPDATE users SET {set_clause} WHERE telegram_id = ?", values
        )
        conn.commit()
    except Exception as e:
        logger.error(f"update_user error: {e}")


def set_onboarding_complete(telegram_id: int, full_name: str, location: str,
                            goal: str, daily_time: int, level_info: dict):
    update_user(telegram_id, {
        "onboarding_complete": True,
        "full_name":           full_name,
        "location":            location,
        "memorization_goal":   goal,
        "daily_time_minutes":  daily_time,
        "known_juz_count":     level_info.get("juz_count", 0),
        "known_surahs":        json.dumps(level_info.get("surahs", []), ensure_ascii=False),
    })


def find_user_by_referral_code(code: str) -> Optional[dict]:
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM users WHERE referral_code = ? LIMIT 1", (code,)
        ).fetchone()
        return _row_to_user(row)
    except Exception as e:
        logger.error(f"find_user_by_referral_code error: {e}")
        return None


def increment_referral_count(telegram_id: int):
    try:
        conn = _get_conn()
        conn.execute(
            "UPDATE users SET referral_count = referral_count + 1 WHERE telegram_id = ?",
            (telegram_id,)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"increment_referral_count error: {e}")


def get_all_users() -> list:
    try:
        conn = _get_conn()
        rows = conn.execute("SELECT * FROM users").fetchall()
        return [_row_to_user(r) for r in rows]
    except Exception as e:
        logger.error(f"get_all_users error: {e}")
        return []


def get_total_users() -> int:
    try:
        conn = _get_conn()
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    except Exception as e:
        logger.error(f"get_total_users error: {e}")
        return 0


def get_new_users_today() -> int:
    today = _today_str()
    try:
        conn = _get_conn()
        return conn.execute(
            "SELECT COUNT(*) FROM users WHERE registration_date LIKE ?",
            (f"{today}%",)
        ).fetchone()[0]
    except Exception as e:
        logger.error(f"get_new_users_today error: {e}")
        return 0


def get_active_users_today() -> int:
    today = _today_str()
    try:
        conn = _get_conn()
        return conn.execute(
            "SELECT COUNT(*) FROM users WHERE stats_last_activity_date LIKE ?",
            (f"{today}%",)
        ).fetchone()[0]
    except Exception as e:
        logger.error(f"get_active_users_today error: {e}")
        return 0


def get_active_users_7days() -> int:
    cutoff = (_now() - timedelta(days=7)).isoformat()
    try:
        conn = _get_conn()
        return conn.execute(
            "SELECT COUNT(*) FROM users WHERE stats_last_activity_date >= ?",
            (cutoff,)
        ).fetchone()[0]
    except Exception as e:
        logger.error(f"get_active_users_7days error: {e}")
        return 0


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_active_session(user_id: int) -> Optional[dict]:
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? AND is_active = 1 LIMIT 1",
            (user_id,)
        ).fetchone()
        return _row_to_session(row)
    except Exception as e:
        logger.error(f"get_active_session error: {e}")
        return None


def create_session(user_id: int, juz: int, surah_number: int, surah_name: str,
                   direction: str, reciter: str, start_ayah: int = 1) -> dict:
    session_id = str(uuid.uuid4())
    now_str = _now_str()
    try:
        conn = _get_conn()
        conn.execute("""
            INSERT INTO sessions (
                session_id, user_id, started_at, juz_number, surah_number,
                surah_name, direction, reciter, start_ayah,
                current_ayah_index, stage, repetitions_done, target_repetitions,
                session_ayahs_count, session_minutes, daily_ayahs_count,
                current_ayah_data, accumulated_ayahs, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'new_ayah', 0, 3, 0, 0, 0, '{}', '[]', 1)
        """, (
            session_id, user_id, now_str, juz, surah_number,
            surah_name, direction, reciter, start_ayah,
        ))
        conn.commit()
    except Exception as e:
        logger.error(f"create_session error: {e}")
    return get_active_session(user_id) or {}


def update_session(session_id: str, data: dict):
    if not data:
        return
    try:
        conn = _get_conn()
        # Serialise any list/dict values
        flat = {}
        for k, v in data.items():
            if isinstance(v, (list, dict)):
                flat[k] = json.dumps(v, ensure_ascii=False)
            elif isinstance(v, bool):
                flat[k] = 1 if v else 0
            else:
                flat[k] = v
        set_clause = ", ".join(f"{col} = ?" for col in flat)
        values = list(flat.values()) + [session_id]
        conn.execute(
            f"UPDATE sessions SET {set_clause} WHERE session_id = ?", values
        )
        conn.commit()
    except Exception as e:
        logger.error(f"update_session error: {e}")


def close_session(session_id: str):
    update_session(session_id, {"is_active": 0})


def get_daily_ayah_count(user_id: int) -> int:
    today = _today_str()
    try:
        conn = _get_conn()
        row = conn.execute("""
            SELECT verses_read FROM activity_stats
            WHERE user_id = ? AND period_type = 'day' AND period_key = ?
        """, (user_id, today)).fetchone()
        return row[0] if row else 0
    except Exception as e:
        logger.error(f"get_daily_ayah_count error: {e}")
        return 0


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVITY / STATS FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def add_activity_to_period_safe(user_id: int, verses: int = 0,
                                repetitions: int = 0, minutes: int = 0,
                                himmat: int = 0, surah_number: int = None):
    """
    Atomically increment stats for all four periods (day/week/month/year)
    and update the user's rolling totals.
    """
    periods = [
        ("day",   _today_str()),
        ("week",  _week_str()),
        ("month", _month_str()),
        ("year",  _year_str()),
    ]
    # Build surahs JSON update
    surahs_json = json.dumps([surah_number] if surah_number else [], ensure_ascii=False)

    try:
        conn = _get_conn()
        for period_type, period_key in periods:
            # Upsert row
            conn.execute("""
                INSERT INTO activity_stats
                    (user_id, period_type, period_key, verses_read, repetitions,
                     minutes, himmat_earned, surahs_worked)
                VALUES (?, ?, ?, 0, 0, 0, 0, '[]')
                ON CONFLICT(user_id, period_type, period_key) DO NOTHING
            """, (user_id, period_type, period_key))

            # Increment numerics
            conn.execute("""
                UPDATE activity_stats
                SET verses_read  = verses_read  + ?,
                    repetitions  = repetitions  + ?,
                    minutes      = minutes      + ?,
                    himmat_earned= himmat_earned + ?
                WHERE user_id = ? AND period_type = ? AND period_key = ?
            """, (verses, repetitions, minutes, himmat, user_id, period_type, period_key))

            # Merge surah into surahs_worked JSON list (deduplicated)
            if surah_number is not None:
                row = conn.execute("""
                    SELECT surahs_worked FROM activity_stats
                    WHERE user_id = ? AND period_type = ? AND period_key = ?
                """, (user_id, period_type, period_key)).fetchone()
                if row:
                    existing = _json_loads(row[0], [])
                    if surah_number not in existing:
                        existing.append(surah_number)
                    conn.execute("""
                        UPDATE activity_stats SET surahs_worked = ?
                        WHERE user_id = ? AND period_type = ? AND period_key = ?
                    """, (json.dumps(existing, ensure_ascii=False), user_id, period_type, period_key))

        # Update user totals
        conn.execute("""
            UPDATE users SET
                stats_total_verses_read = stats_total_verses_read + ?,
                stats_total_repetitions = stats_total_repetitions + ?,
                stats_total_minutes     = stats_total_minutes     + ?,
                stats_himmat_points     = stats_himmat_points     + ?,
                stats_last_activity_date = ?
            WHERE telegram_id = ?
        """, (verses, repetitions, minutes, himmat, _now_str(), user_id))
        conn.commit()
    except Exception as e:
        logger.error(f"add_activity_to_period_safe error: {e}")


def get_period_stats(user_id: int, period_type: str,
                     period_key: str = None) -> dict:
    """
    Returns the activity_stats row for the given period as a plain dict.
    period_type: 'day' | 'week' | 'month' | 'year'
    period_key: auto-computed from current time when omitted.
    """
    if period_key is None:
        period_key = {
            "day":   _today_str,
            "week":  _week_str,
            "month": _month_str,
            "year":  _year_str,
        }.get(period_type, _today_str)()
    try:
        conn = _get_conn()
        row = conn.execute("""
            SELECT * FROM activity_stats
            WHERE user_id = ? AND period_type = ? AND period_key = ?
        """, (user_id, period_type, period_key)).fetchone()
        if row:
            d = dict(row)
            d["surahs_worked"] = _json_loads(d.get("surahs_worked"), [])
            return d
        return {}
    except Exception as e:
        logger.error(f"get_period_stats error: {e}")
        return {}


def get_daily_stats(user_id: int, date_str: str = None) -> dict:
    return get_period_stats(user_id, "day", date_str or _today_str())


def get_user_rank(user_id: int) -> int:
    """Returns 1-indexed rank by himmat_points in leaderboard table."""
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT user_id FROM leaderboard ORDER BY himmat_points DESC"
        ).fetchall()
        for i, row in enumerate(rows, 1):
            if row[0] == user_id:
                return i
        return 0
    except Exception as e:
        logger.error(f"get_user_rank error: {e}")
        return 0


# ── Profile data (from stats_service.py) ──────────────────────────────────────

def get_profile_data(user_id: int) -> Optional[dict]:
    """Returns all data needed for the profile page."""
    from services.gamification import get_level
    from services.premium_service import is_premium, get_premium_expiry_str

    user = get_user(user_id)
    if not user:
        return None

    stats    = user.get("stats", {})
    progress = user.get("memorization_progress", {})

    total_verses = stats.get("total_verses_read", 0)
    total_reps   = stats.get("total_repetitions", 0)
    total_mins   = stats.get("total_minutes", 0)
    himmat       = stats.get("himmat_points", 0)
    streak       = stats.get("current_streak_days", 0)
    longest      = stats.get("longest_streak_days", 0)

    level_num, level_name = get_level(himmat)
    rank = get_user_rank(user_id)

    today_stats = get_daily_stats(user_id)
    week_stats  = get_period_stats(user_id, "week")
    month_stats = get_period_stats(user_id, "month")
    year_stats  = get_period_stats(user_id, "year")

    completed_surahs  = progress.get("completed_surahs", [])
    completed_juz     = progress.get("completed_juz", [])
    current_surah_num = progress.get("current_surah")
    current_ayah      = progress.get("current_ayah", 1)

    total_quran_ayahs  = 6236
    percent_complete   = round(total_verses / total_quran_ayahs * 100, 1) if total_verses else 0

    def _build_progress_bar(current: int, total: int, length: int = 20) -> str:
        if total <= 0:
            return "░" * length
        filled = int(length * current / total)
        return "█" * filled + "░" * (length - filled)

    def _format_time(minutes: int) -> str:
        if minutes < 60:
            return f"{minutes} daqiqa"
        hours = minutes // 60
        mins  = minutes % 60
        if mins == 0:
            return f"{hours} soat"
        return f"{hours} soat {mins} daqiqa"

    return {
        "user":              user,
        "full_name":         user.get("full_name", "Foydalanuvchi"),
        "total_verses":      total_verses,
        "total_reps":        total_reps,
        "total_time":        _format_time(total_mins),
        "himmat":            himmat,
        "himmat_fmt":        f"{himmat:,}",
        "streak":            streak,
        "longest_streak":    longest,
        "level_num":         level_num,
        "level_name":        level_name,
        "rank":              rank,
        "today_stats":       today_stats,
        "week_stats":        week_stats,
        "month_stats":       month_stats,
        "year_stats":        year_stats,
        "completed_surahs":  completed_surahs,
        "completed_juz":     completed_juz,
        "current_surah":     current_surah_num,
        "current_ayah":      current_ayah,
        "percent_complete":  percent_complete,
        "quran_progress_bar": _build_progress_bar(total_verses, total_quran_ayahs),
        "is_premium":        is_premium(user),
        "premium_expiry":    get_premium_expiry_str(user),
        "referral_code":     user.get("referral_code", ""),
        "referral_count":    user.get("referral_count", 0),
    }


def get_bot_wide_stats() -> dict:
    """Admin: global bot statistics."""
    try:
        total      = get_total_users()
        users      = get_all_users()
        premium    = [u for u in users if u.get("premium", {}).get("is_active")]
        new_today  = get_new_users_today()
        active_today = get_active_users_today()
        active_7d  = get_active_users_7days()
        pending    = get_pending_premium_requests()
        return {
            "total_users":    total,
            "premium_users":  len(premium),
            "new_today":      new_today,
            "active_today":   active_today,
            "active_7d":      active_7d,
            "pending_premium":len(pending),
        }
    except Exception as e:
        logger.error(f"get_bot_wide_stats error: {e}")
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
# LEADERBOARD FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def update_leaderboard_entry(user_id: int, full_name: str, username: str,
                             total_verses: int, himmat_points: int):
    try:
        conn = _get_conn()
        conn.execute("""
            INSERT INTO leaderboard (user_id, full_name, username, total_verses, himmat_points, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                full_name    = excluded.full_name,
                username     = excluded.username,
                total_verses = excluded.total_verses,
                himmat_points= excluded.himmat_points,
                updated_at   = excluded.updated_at
        """, (user_id, full_name or "", username or "", total_verses, himmat_points, _now_str()))
        conn.commit()
    except Exception as e:
        logger.error(f"update_leaderboard_entry error: {e}")


def get_leaderboard(period: str = "month", limit: int = 50) -> list:
    """
    'all'   — sort leaderboard table by himmat_points DESC.
    others  — pull activity_stats for the given period and sort by himmat_earned.
    """
    try:
        conn = _get_conn()
        if period == "all":
            rows = conn.execute(
                "SELECT * FROM leaderboard ORDER BY himmat_points DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        else:
            period_key = {
                "day":   _today_str,
                "week":  _week_str,
                "month": _month_str,
                "year":  _year_str,
            }.get(period, _month_str)()
            rows = conn.execute("""
                SELECT a.user_id, u.full_name, u.username,
                       a.verses_read AS total_verses,
                       a.himmat_earned AS himmat_points,
                       a.minutes
                FROM activity_stats a
                JOIN users u ON u.telegram_id = a.user_id
                WHERE a.period_type = ? AND a.period_key = ?
                ORDER BY a.himmat_earned DESC
                LIMIT ?
            """, (period, period_key, limit)).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_leaderboard error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# PREMIUM REQUEST FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_pending_premium_requests() -> list:
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM premium_requests WHERE status = 'pending'"
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_pending_premium_requests error: {e}")
        return []


def create_premium_request(user_id: int, username: str, full_name: str,
                           receipt_file_id: str) -> str:
    req_id = str(uuid.uuid4())
    try:
        conn = _get_conn()
        conn.execute("""
            INSERT INTO premium_requests
                (request_id, user_id, username, full_name, receipt_file_id,
                 status, requested_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """, (req_id, user_id, username or "", full_name or "",
              receipt_file_id, _now_str()))
        conn.commit()
    except Exception as e:
        logger.error(f"create_premium_request error: {e}")
    return req_id


def update_premium_request(request_id: str, status: str,
                           rejection_reason: str = None):
    try:
        conn = _get_conn()
        conn.execute("""
            UPDATE premium_requests
            SET status = ?, processed_at = ?, rejection_reason = ?
            WHERE request_id = ?
        """, (status, _now_str(), rejection_reason, request_id))
        conn.commit()
    except Exception as e:
        logger.error(f"update_premium_request error: {e}")


def get_premium_request(request_id: str) -> Optional[dict]:
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM premium_requests WHERE request_id = ?",
            (request_id,)
        ).fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"get_premium_request error: {e}")
        return None


def set_admin_message_id(request_id: str, message_id: int):
    try:
        conn = _get_conn()
        conn.execute(
            "UPDATE premium_requests SET admin_message_id = ? WHERE request_id = ?",
            (message_id, request_id)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"set_admin_message_id error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# AYAH PHOTO FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_ayah_photo(surah_number: int, ayah_number: int) -> Optional[dict]:
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM ayah_photos WHERE surah_number = ? AND ayah_number = ?",
            (surah_number, ayah_number)
        ).fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"get_ayah_photo error: {e}")
        return None


def save_ayah_photo(surah_number: int, ayah_number: int,
                    file_id: str, added_by: int):
    try:
        conn = _get_conn()
        conn.execute("""
            INSERT INTO ayah_photos (surah_number, ayah_number, file_id, added_by, added_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(surah_number, ayah_number) DO UPDATE SET
                file_id  = excluded.file_id,
                added_by = excluded.added_by,
                added_at = excluded.added_at
        """, (surah_number, ayah_number, file_id, added_by, _now_str()))
        conn.commit()
    except Exception as e:
        logger.error(f"save_ayah_photo error: {e}")


def delete_ayah_photo(surah_number: int, ayah_number: int):
    try:
        conn = _get_conn()
        conn.execute(
            "DELETE FROM ayah_photos WHERE surah_number = ? AND ayah_number = ?",
            (surah_number, ayah_number)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"delete_ayah_photo error: {e}")


def get_all_photo_keys() -> set:
    """Returns a set of (surah_number, ayah_number) tuples."""
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT surah_number, ayah_number FROM ayah_photos"
        ).fetchall()
        return {(r[0], r[1]) for r in rows}
    except Exception as e:
        logger.error(f"get_all_photo_keys error: {e}")
        return set()


def get_photo_progress() -> dict:
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT value_json FROM bot_settings WHERE key = 'photo_progress'"
        ).fetchone()
        return _json_loads(row[0], {}) if row else {}
    except Exception as e:
        logger.error(f"get_photo_progress error: {e}")
        return {}


def save_photo_progress(surah_number: int, ayah_number: int):
    val = json.dumps({"surah_number": surah_number, "ayah_number": ayah_number},
                     ensure_ascii=False)
    try:
        conn = _get_conn()
        conn.execute("""
            INSERT INTO bot_settings (key, value_json) VALUES ('photo_progress', ?)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json
        """, (val,))
        conn.commit()
    except Exception as e:
        logger.error(f"save_photo_progress error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION SETTINGS (global bot settings, not per-user)
# ═══════════════════════════════════════════════════════════════════════════════

def _get_notif_settings_json() -> dict:
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT value_json FROM bot_settings WHERE key = 'notifications'"
        ).fetchone()
        return _json_loads(row[0], {}) if row else {}
    except Exception as e:
        logger.error(f"_get_notif_settings_json error: {e}")
        return {}


def _save_notif_settings_json(data: dict):
    val = json.dumps(data, ensure_ascii=False)
    try:
        conn = _get_conn()
        conn.execute("""
            INSERT INTO bot_settings (key, value_json) VALUES ('notifications', ?)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json
        """, (val,))
        conn.commit()
    except Exception as e:
        logger.error(f"_save_notif_settings_json error: {e}")


def get_notification_settings() -> tuple:
    """Returns (hour, minute, count). Default: (8, 0, 1)."""
    data = _get_notif_settings_json()
    return (
        int(data.get("hour", 8)),
        int(data.get("minute", 0)),
        int(data.get("count", 1)),
    )


def get_notification_times_list() -> list:
    """Returns list of (hour, minute) tuples for each scheduled notification."""
    data  = _get_notif_settings_json()
    times = data.get("times", [])
    count = int(data.get("count", 1))
    if times and len(times) == count:
        result = []
        for t in times:
            parts = str(t).split(":")
            result.append((int(parts[0]), int(parts[1])))
        return result
    # Auto-space from base time
    base_h = int(data.get("hour", 8))
    base_m = int(data.get("minute", 0))
    intervals = {1: 0, 2: 8, 3: 6, 4: 4, 5: 3}
    gap = intervals.get(count, 0)
    return [((base_h + i * gap) % 24, base_m) for i in range(count)]


def set_notification_time(hour: int, minute: int, count: int = None):
    data = _get_notif_settings_json()
    data["hour"]   = hour
    data["minute"] = minute
    data["times"]  = []   # clear explicit times
    if count is not None:
        data["count"] = count
    _save_notif_settings_json(data)


def set_notification_count(count: int):
    data = _get_notif_settings_json()
    data["count"] = count
    data["times"] = []   # clear explicit times on count change
    _save_notif_settings_json(data)


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP XATM FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_xatm_count() -> int:
    try:
        conn = _get_conn()
        return conn.execute("SELECT COUNT(*) FROM group_xatms").fetchone()[0]
    except Exception as e:
        logger.error(f"get_xatm_count error: {e}")
        return 0


def create_xatm(creator_id: int = None) -> str:
    xatm_id = str(uuid.uuid4())
    try:
        conn = _get_conn()
        xatm_number = get_xatm_count() + 1
        conn.execute("""
            INSERT INTO group_xatms (xatm_id, xatm_number, status, creator_id, created_at)
            VALUES (?, ?, 'recruiting', ?, ?)
        """, (xatm_id, xatm_number, creator_id, _now_str()))
        conn.commit()
    except Exception as e:
        logger.error(f"create_xatm error: {e}")
    return xatm_id


def get_xatm(xatm_id: str) -> Optional[dict]:
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM group_xatms WHERE xatm_id = ?", (xatm_id,)
        ).fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"get_xatm error: {e}")
        return None


def get_xatm_by_number(xatm_number: int) -> Optional[dict]:
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM group_xatms WHERE xatm_number = ?", (xatm_number,)
        ).fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"get_xatm_by_number error: {e}")
        return None


def get_latest_xatm() -> Optional[dict]:
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM group_xatms ORDER BY xatm_number DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"get_latest_xatm error: {e}")
        return None


def get_xatm_juzs(xatm_id: str) -> list:
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM group_xatm_juzs WHERE xatm_id = ?", (xatm_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_xatm_juzs error: {e}")
        return []


def assign_xatm_juz(xatm_id: str, juz_number: int, user_id: int) -> bool:
    try:
        conn = _get_conn()
        existing = conn.execute(
            "SELECT 1 FROM group_xatm_juzs WHERE xatm_id = ? AND juz_number = ?",
            (xatm_id, juz_number)
        ).fetchone()
        if existing:
            return False
        conn.execute("""
            INSERT INTO group_xatm_juzs (xatm_id, juz_number, user_id, status, assigned_at)
            VALUES (?, ?, ?, 'assigned', ?)
        """, (xatm_id, juz_number, user_id, _now_str()))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"assign_xatm_juz error: {e}")
        return False


def complete_xatm_juz(xatm_id: str, juz_number: int, user_id: int):
    try:
        conn = _get_conn()
        conn.execute("""
            UPDATE group_xatm_juzs
            SET status = 'completed', completed_at = ?
            WHERE xatm_id = ? AND juz_number = ? AND user_id = ?
        """, (_now_str(), xatm_id, juz_number, user_id))
        conn.commit()
    except Exception as e:
        logger.error(f"complete_xatm_juz error: {e}")


def check_and_update_xatm_status(xatm_id: str) -> Optional[str]:
    try:
        conn = _get_conn()
        juzs = get_xatm_juzs(xatm_id)
        assigned_count  = len(juzs)
        completed_count = sum(1 for j in juzs if j["status"] == "completed")

        xatm = get_xatm(xatm_id)
        if not xatm:
            return None

        current_status = xatm["status"]
        new_status = None

        if current_status == "recruiting" and assigned_count == 30:
            new_status = "active"
        elif current_status == "active" and completed_count == 30:
            new_status = "completed"

        if new_status:
            col = f"{new_status}_at"
            conn.execute(
                f"UPDATE group_xatms SET status = ?, {col} = ? WHERE xatm_id = ?",
                (new_status, _now_str(), xatm_id)
            )
            conn.commit()
            return new_status
    except Exception as e:
        logger.error(f"check_and_update_xatm_status error: {e}")
    return None


def get_xatm_ranking(xatm_id: str) -> list:
    """Returns per-user ranking sorted by completed juzs then speed."""
    try:
        juzs = get_xatm_juzs(xatm_id)
        by_user: dict = {}
        for j in juzs:
            uid = j["user_id"]
            by_user.setdefault(uid, []).append(j)

        ranking = []
        for uid, user_juzs in by_user.items():
            user = get_user(uid)
            name = user.get("full_name", str(uid)) if user else str(uid)
            completed = [j for j in user_juzs if j["status"] == "completed"]
            total_secs = 0
            for j in completed:
                a_str = j.get("assigned_at")
                d_str = j.get("completed_at")
                if a_str and d_str:
                    try:
                        a_dt = datetime.fromisoformat(a_str)
                        d_dt = datetime.fromisoformat(d_str)
                        total_secs += int((d_dt - a_dt).total_seconds())
                    except Exception:
                        pass
            ranking.append({
                "user_id":       uid,
                "name":          name,
                "completed":     len(completed),
                "total":         len(user_juzs),
                "total_seconds": total_secs,
            })

        ranking.sort(key=lambda x: (-x["completed"], x["total_seconds"]))
        return ranking
    except Exception as e:
        logger.error(f"get_xatm_ranking error: {e}")
        return []


def unassign_xatm_juz(xatm_id: str, juz_number: int, user_id: int):
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT user_id, status FROM group_xatm_juzs WHERE xatm_id = ? AND juz_number = ?",
            (xatm_id, juz_number)
        ).fetchone()
        if row and row["user_id"] == user_id and row["status"] != "completed":
            conn.execute(
                "DELETE FROM group_xatm_juzs WHERE xatm_id = ? AND juz_number = ?",
                (xatm_id, juz_number)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"unassign_xatm_juz error: {e}")


def uncomplete_xatm_juz(xatm_id: str, juz_number: int, user_id: int):
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT user_id FROM group_xatm_juzs WHERE xatm_id = ? AND juz_number = ?",
            (xatm_id, juz_number)
        ).fetchone()
        if row and row["user_id"] == user_id:
            conn.execute("""
                UPDATE group_xatm_juzs
                SET status = 'assigned', completed_at = NULL
                WHERE xatm_id = ? AND juz_number = ?
            """, (xatm_id, juz_number))
            # Revert xatm status from completed back to active if needed
            xatm = get_xatm(xatm_id)
            if xatm and xatm.get("status") == "completed":
                conn.execute(
                    "UPDATE group_xatms SET status = 'active', completed_at = NULL WHERE xatm_id = ?",
                    (xatm_id,)
                )
            conn.commit()
    except Exception as e:
        logger.error(f"uncomplete_xatm_juz error: {e}")


def get_user_xatms(user_id: int) -> list:
    """Returns list of {xatm, juzs} dicts for all xatms the user participated in."""
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT DISTINCT xatm_id FROM group_xatm_juzs WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        result = []
        for row in rows:
            xatm_id = row[0]
            xatm = get_xatm(xatm_id)
            juzs = get_xatm_juzs(xatm_id)
            user_juzs = [j for j in juzs if j["user_id"] == user_id]
            if xatm:
                result.append({"xatm": xatm, "juzs": user_juzs})
        result.sort(key=lambda x: x["xatm"].get("xatm_number", 0))
        return result
    except Exception as e:
        logger.error(f"get_user_xatms error: {e}")
        return []


def get_xatms_for_user(user_id: int) -> list:
    """Alias: same as get_user_xatms but returns flat list of xatm dicts."""
    try:
        conn = _get_conn()
        rows = conn.execute("""
            SELECT DISTINCT g.*
            FROM group_xatms g
            JOIN group_xatm_juzs j ON j.xatm_id = g.xatm_id
            WHERE j.user_id = ?
            ORDER BY g.xatm_number
        """, (user_id,)).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_xatms_for_user error: {e}")
        return []


def set_xatm_privacy(xatm_id: str, is_private: bool):
    try:
        conn = _get_conn()
        conn.execute(
            "UPDATE group_xatms SET is_private = ? WHERE xatm_id = ?",
            (1 if is_private else 0, xatm_id)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"set_xatm_privacy error: {e}")


def set_juz_hidden(xatm_id: str, juz_number: int, is_hidden: bool):
    try:
        conn = _get_conn()
        conn.execute(
            "UPDATE group_xatm_juzs SET is_hidden = ? WHERE xatm_id = ? AND juz_number = ?",
            (1 if is_hidden else 0, xatm_id, juz_number)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"set_juz_hidden error: {e}")


def backfill_xatm_numbers():
    """No-op: SQLite already has sequential xatm_number assigned at creation."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# ACHIEVEMENTS + CONGRATS
# ═══════════════════════════════════════════════════════════════════════════════

def unlock_achievement(user_id: int, achievement_key: str, title: str,
                       icon: str, himmat_bonus: int) -> bool:
    """
    Inserts the achievement if not already present.
    Returns True if newly unlocked, False if already had it.
    """
    try:
        conn = _get_conn()
        existing = conn.execute(
            "SELECT 1 FROM achievements WHERE user_id = ? AND achievement_key = ?",
            (user_id, achievement_key)
        ).fetchone()
        if existing:
            return False
        conn.execute("""
            INSERT OR IGNORE INTO achievements
                (user_id, achievement_key, title, icon, himmat_bonus, unlocked_at, notified)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (user_id, achievement_key, title, icon, himmat_bonus, _now_str()))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"unlock_achievement error: {e}")
        return False


def get_user_achievements(user_id: int) -> list:
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM achievements WHERE user_id = ? ORDER BY unlocked_at",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_user_achievements error: {e}")
        return []


def has_achievement(user_id: int, achievement_key: str) -> bool:
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT 1 FROM achievements WHERE user_id = ? AND achievement_key = ?",
            (user_id, achievement_key)
        ).fetchone()
        return row is not None
    except Exception as e:
        logger.error(f"has_achievement error: {e}")
        return False


def enqueue_congrats(achiever_id: int, achievement_key: str,
                     achievement_title: str, achievement_icon: str):
    """
    Queues a congrats message to all other registered users (max 50 recipients).
    """
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT telegram_id FROM users WHERE telegram_id != ? LIMIT 50",
            (achiever_id,)
        ).fetchall()
        now_str = _now_str()
        for row in rows:
            conn.execute("""
                INSERT INTO congrats_queue
                    (achiever_id, recipient_id, achievement_key, achievement_title,
                     achievement_icon, sent, created_at)
                VALUES (?, ?, ?, ?, ?, 0, ?)
            """, (achiever_id, row[0], achievement_key, achievement_title,
                  achievement_icon, now_str))
        conn.commit()
    except Exception as e:
        logger.error(f"enqueue_congrats error: {e}")


def get_pending_congrats(recipient_id: int, limit: int = 5) -> list:
    try:
        conn = _get_conn()
        rows = conn.execute("""
            SELECT * FROM congrats_queue
            WHERE recipient_id = ? AND sent = 0
            ORDER BY created_at
            LIMIT ?
        """, (recipient_id, limit)).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_pending_congrats error: {e}")
        return []


def mark_congrats_sent(congrats_ids: list):
    if not congrats_ids:
        return
    try:
        conn = _get_conn()
        placeholders = ",".join("?" * len(congrats_ids))
        conn.execute(
            f"UPDATE congrats_queue SET sent = 1 WHERE id IN ({placeholders})",
            congrats_ids
        )
        conn.commit()
    except Exception as e:
        logger.error(f"mark_congrats_sent error: {e}")


def get_congrats_sent_today(recipient_id: int) -> int:
    today = _today_str()
    try:
        conn = _get_conn()
        row = conn.execute("""
            SELECT COUNT(*) FROM congrats_queue
            WHERE recipient_id = ? AND sent = 1 AND created_at LIKE ?
        """, (recipient_id, f"{today}%")).fetchone()
        return row[0] if row else 0
    except Exception as e:
        logger.error(f"get_congrats_sent_today error: {e}")
        return 0


# ═══════════════════════════════════════════════════════════════════════════════
# MISC / COMPAT HELPERS (kept for callers that still reference old names)
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_notification_enabled_users() -> list:
    """Returns users who have notifications enabled."""
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM users WHERE notif_enabled = 1"
        ).fetchall()
        return [_row_to_user(r) for r in rows]
    except Exception as e:
        logger.error(f"get_all_notification_enabled_users error: {e}")
        return []


def log_notification(user_id: int, notif_type: str, preview: str):
    try:
        conn = _get_conn()
        conn.execute("""
            INSERT INTO notifications_log (user_id, sent_at, notif_type, message_preview)
            VALUES (?, ?, ?, ?)
        """, (user_id, _now_str(), notif_type, (preview or "")[:100]))
        conn.commit()
    except Exception as e:
        logger.error(f"log_notification error: {e}")


def save_memorization_progress(user_id: int, surah_number: int,
                               surah_name: str, next_ayah: int):
    update_user(user_id, {
        "memorization_progress.current_surah":      surah_number,
        "memorization_progress.current_surah_name": surah_name,
        "memorization_progress.current_ayah":       next_ayah,
    })


def get_memorization_progress(user_id: int) -> dict:
    user = get_user(user_id)
    if not user:
        return {}
    return user.get("memorization_progress", {})


def get_user_percentile(user_id: int) -> int:
    users = get_all_users()
    if len(users) <= 1:
        return 0
    user_himmat = 0
    all_himmats = []
    for u in users:
        h = u.get("stats", {}).get("himmat_points", 0)
        all_himmats.append(h)
        if u.get("telegram_id") == user_id:
            user_himmat = h
    below = sum(1 for h in all_himmats if h < user_himmat)
    return int((below / len(all_himmats)) * 100)
