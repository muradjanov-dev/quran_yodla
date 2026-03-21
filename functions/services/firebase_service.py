"""
firebase_service.py — All Firestore CRUD operations.
"""

import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Optional
import pytz

from firebase_config import db
from config import LOCAL_TZ

logger = logging.getLogger(__name__)
TZ = pytz.timezone(LOCAL_TZ)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(TZ)


def _today_str() -> str:
    return _now().strftime("%Y-%m-%d")


def _week_str() -> str:
    n = _now()
    return f"{n.year}-W{n.strftime('%W')}"


def _month_str() -> str:
    return _now().strftime("%Y-%m")


def _year_str() -> str:
    return str(_now().year)


# ─── USER ─────────────────────────────────────────────────────────────────────

def get_user(telegram_id: int) -> Optional[dict]:
    if not db:
        return None
    try:
        doc = db.collection("users").document(str(telegram_id)).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        logger.error(f"get_user error: {e}")
        return None


def create_user(telegram_id: int, username: str, full_name: str,
                referred_by: Optional[str] = None) -> dict:
    """Creates a new user document with default values."""
    ref_code = _generate_referral_code(telegram_id)
    now = _now()
    user = {
        "telegram_id":         telegram_id,
        "username":            username or "",
        "full_name":           full_name or "",
        "registration_date":   now,
        "onboarding_complete": False,
        "location":            "",
        "memorization_goal":   "",
        "daily_time_minutes":  30,
        "known_surahs":        [],
        "known_juz_count":     0,
        "premium": {
            "is_active":      False,
            "expires_at":     None,
            "trial_used":     False,
            "trial_started_at": None,
        },
        "referral_code":  ref_code,
        "referred_by":    referred_by,
        "referral_count": 0,
        "stats": {
            "total_verses_read":   0,
            "total_repetitions":   0,
            "total_minutes":       0,
            "himmat_points":       0,
            "current_streak_days": 0,
            "longest_streak_days": 0,
            "last_activity_date":  None,
        },
        "memorization_progress": {
            "current_juz":      None,
            "current_surah":    None,
            "current_ayah":     1,
            "completed_surahs": [],
            "completed_juz":    [],
            "direction":        "forward",
        },
        "notification_settings": {
            "enabled":  True,
            "time":     "08:00",
            "timezone": LOCAL_TZ,
        },
    }
    try:
        db.collection("users").document(str(telegram_id)).set(user)
    except Exception as e:
        logger.error(f"create_user error: {e}")
    return user


def update_user(telegram_id: int, fields: dict):
    if not db:
        return
    try:
        db.collection("users").document(str(telegram_id)).update(fields)
    except Exception as e:
        logger.error(f"update_user error: {e}")


def set_onboarding_complete(telegram_id: int, full_name: str, location: str,
                            goal: str, daily_time: int, level_info: dict):
    update_user(telegram_id, {
        "onboarding_complete":  True,
        "full_name":            full_name,
        "location":             location,
        "memorization_goal":    goal,
        "daily_time_minutes":   daily_time,
        "known_juz_count":      level_info.get("juz_count", 0),
        "known_surahs":         level_info.get("surahs", []),
    })


# ─── SESSION ──────────────────────────────────────────────────────────────────

def create_session(user_id: int, juz_number: int, surah_number: int,
                   surah_name: str, direction: str, reciter: str,
                   start_ayah: int = 1) -> dict:
    session_id = str(uuid.uuid4())
    now = _now()
    session = {
        "user_id":            user_id,
        "session_id":         session_id,
        "started_at":         now,
        "juz_number":         juz_number,
        "surah_number":       surah_number,
        "surah_name":         surah_name,
        "direction":          direction,
        "reciter":            reciter,
        "current_ayah_index": 0,
        "accumulated_ayahs":  [],
        "stage":              "new_ayah",
        "repetitions_done":   0,
        "target_repetitions": 3,
        "session_ayahs_count":0,
        "session_minutes":    0,
        "is_active":          True,
        "daily_ayahs_count":  0,
        "start_ayah":         start_ayah,
    }
    try:
        db.collection("sessions").document(session_id).set(session)
    except Exception as e:
        logger.error(f"create_session error: {e}")
    return session


def get_active_session(user_id: int) -> Optional[dict]:
    if not db:
        return None
    try:
        docs = (
            db.collection("sessions")
            .where("user_id", "==", user_id)
            .where("is_active", "==", True)
            .limit(1)
            .stream()
        )
        for doc in docs:
            return doc.to_dict()
    except Exception as e:
        logger.error(f"get_active_session error: {e}")
    return None


def update_session(session_id: str, fields: dict):
    if not db:
        return
    try:
        db.collection("sessions").document(session_id).update(fields)
    except Exception as e:
        logger.error(f"update_session error: {e}")


def close_session(session_id: str):
    update_session(session_id, {"is_active": False})


# ─── STATS ────────────────────────────────────────────────────────────────────

def record_activity(user_id: int, verses: int, repetitions: int,
                    minutes: int, himmat: int, surahs_worked: list):
    """Increment daily/weekly/monthly/yearly stats and user totals."""
    if not db:
        return

    today   = _today_str()
    week    = _week_str()
    month   = _month_str()
    year    = _year_str()
    now     = _now()

    batch = db.batch()

    # Daily stats
    daily_ref = db.collection("daily_stats").document(f"{user_id}_{today}")
    _upsert_stats(batch, daily_ref, user_id, verses, repetitions,
                  minutes, himmat, surahs_worked, {"date": today})

    # Weekly stats
    weekly_ref = db.collection("weekly_stats").document(f"{user_id}_{week}")
    _upsert_stats(batch, weekly_ref, user_id, verses, repetitions,
                  minutes, himmat, surahs_worked, {"week": week})

    # Monthly stats
    monthly_ref = db.collection("monthly_stats").document(f"{user_id}_{month}")
    _upsert_stats(batch, monthly_ref, user_id, verses, repetitions,
                  minutes, himmat, surahs_worked, {"month": month})

    # Yearly stats
    yearly_ref = db.collection("yearly_stats").document(f"{user_id}_{year}")
    _upsert_stats(batch, yearly_ref, user_id, verses, repetitions,
                  minutes, himmat, surahs_worked, {"year": year})

    try:
        batch.commit()
    except Exception as e:
        logger.error(f"record_activity batch error: {e}")

    # Update user totals (not in batch because of increment)
    from google.cloud.firestore_v1 import Increment
    try:
        db.collection("users").document(str(user_id)).update({
            "stats.total_verses_read":   Increment(verses),
            "stats.total_repetitions":   Increment(repetitions),
            "stats.total_minutes":       Increment(minutes),
            "stats.himmat_points":       Increment(himmat),
            "stats.last_activity_date":  now,
        })
    except Exception as e:
        logger.error(f"record_activity user update error: {e}")


def _upsert_stats(batch, ref, user_id, verses, repetitions, minutes, himmat, surahs, extra):
    from google.cloud.firestore_v1 import Increment
    # We use set with merge=True + Increment; however batch.set doesn't support Increment.
    # Use manual update path with try/create pattern.
    # Batch SET (create if not exists):
    base = {
        "user_id":        user_id,
        "verses_read":    0,
        "repetitions":    0,
        "minutes":        0,
        "himmat_earned":  0,
        "surahs_worked":  [],
    }
    base.update(extra)
    batch.set(ref, base, merge=True)
    # Batched increments via update — done outside batch per Firestore limitation:
    # We do a simpler approach: accumulate after batch commit.


def add_activity_to_period_safe(user_id: int, verses: int, repetitions: int,
                                minutes: int, himmat: int, surahs_worked: list):
    """Safe increment using Firestore atomic Increment (non-batch)."""
    from google.cloud.firestore_v1 import Increment as Inc, ArrayUnion
    today = _today_str()
    week  = _week_str()
    month = _month_str()
    year  = _year_str()
    updates = {
        "verses_read":   Inc(verses),
        "repetitions":   Inc(repetitions),
        "minutes":       Inc(minutes),
        "himmat_earned": Inc(himmat),
        "surahs_worked": ArrayUnion(surahs_worked),
    }
    for coll, doc_id in [
        ("daily_stats",   f"{user_id}_{today}"),
        ("weekly_stats",  f"{user_id}_{week}"),
        ("monthly_stats", f"{user_id}_{month}"),
        ("yearly_stats",  f"{user_id}_{year}"),
    ]:
        try:
            db.collection(coll).document(doc_id).set(
                {"user_id": user_id, **{k: 0 for k in ["verses_read","repetitions","minutes","himmat_earned"]},
                 "surahs_worked": []}, merge=True
            )
            db.collection(coll).document(doc_id).update(updates)
        except Exception as e:
            logger.error(f"stats increment error {coll}: {e}")


def get_daily_stats(user_id: int, date_str: Optional[str] = None) -> dict:
    if not db:
        return {}
    date_str = date_str or _today_str()
    try:
        doc = db.collection("daily_stats").document(f"{user_id}_{date_str}").get()
        return doc.to_dict() or {}
    except Exception as e:
        logger.error(f"get_daily_stats error: {e}")
        return {}


def get_period_stats(user_id: int, period: str) -> dict:
    """period: 'week', 'month', 'year'"""
    if not db:
        return {}
    mapping = {"week": (_week_str, "weekly_stats"),
               "month": (_month_str, "monthly_stats"),
               "year": (_year_str, "yearly_stats")}
    fn, coll = mapping.get(period, (_today_str, "daily_stats"))
    doc_id = f"{user_id}_{fn()}"
    try:
        doc = db.collection(coll).document(doc_id).get()
        return doc.to_dict() or {}
    except Exception as e:
        logger.error(f"get_period_stats error: {e}")
        return {}


# ─── LEADERBOARD ──────────────────────────────────────────────────────────────

def update_leaderboard_entry(user_id: int, full_name: str, username: str,
                              total_verses: int, himmat_points: int):
    if not db:
        return
    try:
        db.collection("leaderboard").document(str(user_id)).set({
            "user_id":      user_id,
            "full_name":    full_name,
            "username":     username,
            "total_verses": total_verses,
            "himmat_points":himmat_points,
            "updated_at":   _now(),
        })
    except Exception as e:
        logger.error(f"update_leaderboard error: {e}")


def get_leaderboard(period: str = "all", limit: int = 50) -> list:
    """Returns top users sorted by himmat_points."""
    if not db:
        return []
    try:
        docs = (
            db.collection("leaderboard")
            .order_by("himmat_points", direction="DESCENDING")
            .limit(limit)
            .stream()
        )
        return [d.to_dict() for d in docs]
    except Exception as e:
        logger.error(f"get_leaderboard error: {e}")
        return []


def get_user_rank(user_id: int) -> int:
    """Returns user's rank in leaderboard (1-indexed)."""
    board = get_leaderboard(limit=1000)
    for i, entry in enumerate(board, 1):
        if entry["user_id"] == user_id:
            return i
    return 0


# ─── PREMIUM REQUESTS ─────────────────────────────────────────────────────────

def create_premium_request(user_id: int, username: str, full_name: str,
                           receipt_file_id: str) -> str:
    req_id = str(uuid.uuid4())
    if not db:
        return req_id
    try:
        db.collection("premium_requests").document(req_id).set({
            "request_id":      req_id,
            "user_id":         user_id,
            "username":        username,
            "full_name":       full_name,
            "receipt_file_id": receipt_file_id,
            "status":          "pending",
            "requested_at":    _now(),
            "processed_at":    None,
            "rejection_reason":None,
            "admin_message_id":None,
        })
    except Exception as e:
        logger.error(f"create_premium_request error: {e}")
    return req_id


def get_pending_premium_requests() -> list:
    if not db:
        return []
    try:
        docs = (
            db.collection("premium_requests")
            .where("status", "==", "pending")
            .stream()
        )
        return [d.to_dict() for d in docs]
    except Exception as e:
        logger.error(f"get_pending_premium_requests error: {e}")
        return []


def get_premium_request(req_id: str) -> Optional[dict]:
    if not db:
        return None
    try:
        doc = db.collection("premium_requests").document(req_id).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        logger.error(f"get_premium_request error: {e}")
        return None


def update_premium_request(req_id: str, fields: dict):
    if not db:
        return
    try:
        db.collection("premium_requests").document(req_id).update(fields)
    except Exception as e:
        logger.error(f"update_premium_request error: {e}")


# ─── REFERRAL ─────────────────────────────────────────────────────────────────

def find_user_by_referral_code(code: str) -> Optional[dict]:
    if not db:
        return None
    try:
        docs = (
            db.collection("users")
            .where("referral_code", "==", code)
            .limit(1)
            .stream()
        )
        for doc in docs:
            return doc.to_dict()
    except Exception as e:
        logger.error(f"find_user_by_referral_code error: {e}")
    return None


def increment_referral_count(referrer_id: int):
    from google.cloud.firestore_v1 import Increment
    if not db:
        return
    try:
        db.collection("users").document(str(referrer_id)).update({
            "referral_count": Increment(1)
        })
    except Exception as e:
        logger.error(f"increment_referral_count error: {e}")


# ─── NOTIFICATIONS ────────────────────────────────────────────────────────────

def get_all_notification_enabled_users() -> list:
    if not db:
        return []
    try:
        docs = (
            db.collection("users")
            .where("notification_settings.enabled", "==", True)
            .stream()
        )
        return [d.to_dict() for d in docs]
    except Exception as e:
        logger.error(f"get_all_notification_enabled_users error: {e}")
        return []


def log_notification(user_id: int, notif_type: str, preview: str):
    if not db:
        return
    try:
        db.collection("notifications_log").add({
            "user_id":       user_id,
            "sent_at":       _now(),
            "type":          notif_type,
            "message_preview": preview[:100],
        })
    except Exception as e:
        logger.error(f"log_notification error: {e}")


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _generate_referral_code(telegram_id: int) -> str:
    import hashlib
    raw = hashlib.md5(str(telegram_id).encode()).hexdigest()[:8].upper()
    return raw


def get_daily_ayah_count(user_id: int) -> int:
    """Returns how many new ayahs the user has memorized today."""
    stats = get_daily_stats(user_id)
    return stats.get("verses_read", 0)


def get_all_users() -> list:
    if not db:
        return []
    try:
        docs = db.collection("users").stream()
        return [d.to_dict() for d in docs]
    except Exception as e:
        logger.error(f"get_all_users error: {e}")
        return []
