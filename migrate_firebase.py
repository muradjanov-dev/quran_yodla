"""
migrate_firebase.py — One-time migration: Firebase Firestore → SQLite

Run on Railway (where FIREBASE_CREDENTIALS env var is set):
  python migrate_firebase.py

Or locally with credentials file:
  FIREBASE_CREDENTIALS_PATH=serviceAccount.json python migrate_firebase.py
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

print("[Migrate] Starting Firebase → SQLite migration...")

# ── Init SQLite ────────────────────────────────────────────────────────────────
_db_env = os.environ.get("DB_PATH")
DB_PATH = Path(_db_env) if _db_env else Path(__file__).resolve().parent / "hifz.db"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.database.db import init_db, migrate_db, get_conn
init_db()
migrate_db()
print(f"[Migrate] SQLite DB ready at {DB_PATH}")

# ── Init Firebase ──────────────────────────────────────────────────────────────
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    print("[Migrate] ERROR: firebase-admin not installed. Run: pip install firebase-admin")
    sys.exit(1)

cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
cred_json = os.getenv("FIREBASE_CREDENTIALS", "")

if cred_path and os.path.isfile(cred_path):
    cred = credentials.Certificate(cred_path)
elif cred_json:
    try:
        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
    except json.JSONDecodeError as e:
        print(f"[Migrate] ERROR: Invalid FIREBASE_CREDENTIALS JSON: {e}")
        sys.exit(1)
else:
    print("[Migrate] ERROR: No Firebase credentials found.")
    print("  Set FIREBASE_CREDENTIALS_PATH or FIREBASE_CREDENTIALS env var")
    sys.exit(1)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

fs = firestore.client()
print("[Migrate] Firebase connected.")

# ── Migration counters ─────────────────────────────────────────────────────────
stats = {
    "users": 0,
    "progress": 0,
    "skipped": 0,
    "errors": 0,
}

def _safe(d, *keys, default=None):
    """Safely get nested dict value."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
        if cur is None:
            return default
    return cur

def _parse_date(val) -> str | None:
    """Convert Firestore Timestamp, datetime, or string to ISO date string."""
    if val is None:
        return None
    if hasattr(val, "isoformat"):  # datetime or Timestamp
        return val.isoformat()[:10]
    if isinstance(val, str) and len(val) >= 10:
        return val[:10]
    return None

# ── Migrate users ──────────────────────────────────────────────────────────────
print("[Migrate] Reading users from Firestore...")
users_ref = fs.collection("users").stream()
firebase_users = [(doc.id, doc.to_dict()) for doc in users_ref]
print(f"[Migrate] Found {len(firebase_users)} users in Firebase.")

conn = get_conn()

for doc_id, u in firebase_users:
    try:
        telegram_id = int(doc_id)
    except ValueError:
        print(f"[Migrate] Skipping non-integer doc_id: {doc_id}")
        stats["skipped"] += 1
        continue

    full_name = u.get("full_name") or u.get("name") or "Foydalanuvchi"
    username  = u.get("username", "")
    language  = u.get("language", "uz")
    created_at_raw = u.get("created_at") or u.get("createdAt")
    created_at = None
    if created_at_raw and hasattr(created_at_raw, "isoformat"):
        created_at = created_at_raw.isoformat()
    elif isinstance(created_at_raw, str):
        created_at = created_at_raw

    # Stats
    fs_stats = u.get("stats", {})
    total_xp     = int(_safe(fs_stats, "himmat_points", default=0) or 0)
    streak       = int(_safe(fs_stats, "current_streak", default=0) or 0)
    longest_str  = int(_safe(fs_stats, "longest_streak", default=0) or 0)
    last_act_raw = _safe(fs_stats, "last_active_date")
    last_activity = _parse_date(last_act_raw)
    total_verses = int(_safe(fs_stats, "total_verses_read", default=0) or 0)

    # Premium
    prem = u.get("premium", {})
    prem_active  = bool(_safe(prem, "is_active", default=False))
    prem_expiry  = None
    prem_exp_raw = _safe(prem, "expiry_date") or _safe(prem, "expires_at")
    if prem_exp_raw:
        if hasattr(prem_exp_raw, "isoformat"):
            prem_expiry = prem_exp_raw.isoformat()
        elif isinstance(prem_exp_raw, str):
            prem_expiry = prem_exp_raw

    # Active surah — try to infer from memorization_progress
    memo_prog = u.get("memorization_progress", {})
    active_surah = 1
    if isinstance(memo_prog, dict):
        # Pick any surah they were working on
        started = memo_prog.get("started_surahs", [])
        if isinstance(started, list) and started:
            active_surah = int(started[-1]) if started else 1
        elif memo_prog:
            # Keys might be surah numbers
            try:
                nums = [int(k) for k in memo_prog.keys() if k.isdigit()]
                if nums:
                    active_surah = max(nums)
            except Exception:
                pass

    try:
        # Upsert user
        conn.execute(
            """INSERT INTO users(id, name, language, created_at, active_surah)
               VALUES(?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 name=excluded.name,
                 language=excluded.language,
                 active_surah=excluded.active_surah""",
            (telegram_id, full_name, language,
             created_at or datetime.utcnow().isoformat(), active_surah)
        )

        # Settings
        conn.execute(
            """INSERT INTO settings(user_id) VALUES(?)
               ON CONFLICT(user_id) DO NOTHING""",
            (telegram_id,)
        )

        # Gamification
        # Determine league from XP
        if total_xp >= 5000:
            league = "diamond"
        elif total_xp >= 2000:
            league = "gold"
        elif total_xp >= 500:
            league = "silver"
        else:
            league = "bronze"

        conn.execute(
            """INSERT INTO gamification(user_id, total_xp, current_streak, longest_streak,
                                        league, last_activity)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
                 total_xp=MAX(total_xp, excluded.total_xp),
                 current_streak=excluded.current_streak,
                 longest_streak=excluded.longest_streak,
                 league=excluded.league,
                 last_activity=COALESCE(excluded.last_activity, last_activity)""",
            (telegram_id, total_xp, streak, longest_str, league, last_activity)
        )

        # Premium
        if prem_active and prem_expiry:
            conn.execute(
                """INSERT INTO premium(user_id, active, expires_at, granted_at)
                   VALUES(?,1,?,?)
                   ON CONFLICT(user_id) DO UPDATE SET
                     active=1, expires_at=excluded.expires_at""",
                (telegram_id, prem_expiry, datetime.utcnow().isoformat())
            )

        stats["users"] += 1

        # ── Migrate memorized surahs as progress rows ──────────────────────────
        completed_surahs = _safe(memo_prog, "completed_surahs", default=[]) or []
        if isinstance(completed_surahs, list):
            for surah_num in completed_surahs:
                try:
                    surah_int = int(surah_num)
                    # Mark ayah 1 as memorized for each completed surah
                    # (we don't have per-ayah data in Firebase)
                    conn.execute(
                        """INSERT OR IGNORE INTO progress(user_id, surah_number, ayah_number, memorized)
                           VALUES(?,?,1,1)""",
                        (telegram_id, surah_int)
                    )
                    stats["progress"] += 1
                except Exception:
                    pass

        # Also check in_progress surahs
        in_progress = _safe(memo_prog, "in_progress_surahs", default=[]) or []
        if isinstance(in_progress, list):
            for surah_num in in_progress:
                try:
                    surah_int = int(surah_num)
                    conn.execute(
                        """INSERT OR IGNORE INTO progress(user_id, surah_number, ayah_number, memorized)
                           VALUES(?,?,1,0)""",
                        (telegram_id, surah_int)
                    )
                except Exception:
                    pass

        if stats["users"] % 10 == 0:
            print(f"[Migrate] Migrated {stats['users']} users...")

    except Exception as e:
        print(f"[Migrate] ERROR migrating user {telegram_id}: {e}")
        stats["errors"] += 1
        continue

# ── Migrate group_xatms ────────────────────────────────────────────────────────
try:
    print("[Migrate] Reading group xatms...")
    xatms_ref = fs.collection("group_xatms").stream()
    xatm_docs = [(doc.id, doc.to_dict()) for doc in xatms_ref]
    print(f"[Migrate] Found {len(xatm_docs)} xatms.")

    for xatm_id_str, xd in xatm_docs:
        try:
            status = xd.get("status", "active")
            created_raw = xd.get("created_at")
            created = created_raw.isoformat() if hasattr(created_raw, "isoformat") else str(created_raw or "")
            conn.execute(
                """INSERT OR IGNORE INTO group_xatms(id, status, created_at) VALUES(?,?,?)""",
                (xatm_id_str, status, created[:19] if created else None)
            )
            # Juz assignments
            juzs = xd.get("juz_assignments", {})
            if isinstance(juzs, dict):
                for juz_num_str, assignee_id in juzs.items():
                    try:
                        conn.execute(
                            """INSERT OR IGNORE INTO group_xatm_juzs(xatm_id, juz_number, user_id, status)
                               VALUES(?,?,?,?)""",
                            (xatm_id_str, int(juz_num_str), int(assignee_id), "assigned")
                        )
                    except Exception:
                        pass
        except Exception as e:
            print(f"[Migrate] Xatm {xatm_id_str} error: {e}")
except Exception as e:
    print(f"[Migrate] Xatms migration error: {e}")

# ── Commit ─────────────────────────────────────────────────────────────────────
conn.commit()
conn.close()

print(f"""
[Migrate] ✅ Migration complete!
  Users migrated:    {stats['users']}
  Progress rows:     {stats['progress']}
  Skipped:           {stats['skipped']}
  Errors:            {stats['errors']}
""")
