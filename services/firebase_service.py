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

    # Also update user document totals (needed for leaderboard + profile global stats)
    try:
        db.collection("users").document(str(user_id)).update({
            "stats.total_verses_read": Inc(verses),
            "stats.total_repetitions": Inc(repetitions),
            "stats.total_minutes":     Inc(minutes),
            "stats.himmat_points":     Inc(himmat),
            "stats.last_activity_date": _now(),
        })
    except Exception as e:
        logger.error(f"add_activity user totals error: {e}")


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


# ─── AYAH PHOTOS ──────────────────────────────────────────────────────────────

def get_ayah_photo(surah_number: int, ayah_number: int) -> Optional[str]:
    """Returns Telegram file_id for an ayah photo, or None."""
    if not db:
        return None
    try:
        doc = db.collection("ayah_photos").document(f"{surah_number}_{ayah_number}").get()
        if doc.exists:
            return doc.to_dict().get("file_id")
    except Exception as e:
        logger.error(f"get_ayah_photo error: {e}")
    return None


def set_ayah_photo(surah_number: int, ayah_number: int, file_id: str, admin_id: int):
    """Stores a Telegram photo file_id for a specific ayah."""
    if not db:
        return
    try:
        db.collection("ayah_photos").document(f"{surah_number}_{ayah_number}").set({
            "surah_number": surah_number,
            "ayah_number":  ayah_number,
            "file_id":      file_id,
            "added_by":     admin_id,
            "added_at":     _now(),
        })
    except Exception as e:
        logger.error(f"set_ayah_photo error: {e}")


def delete_ayah_photo(surah_number: int, ayah_number: int):
    if not db:
        return
    try:
        db.collection("ayah_photos").document(f"{surah_number}_{ayah_number}").delete()
    except Exception as e:
        logger.error(f"delete_ayah_photo error: {e}")


# ─── GLOBAL SETTINGS ──────────────────────────────────────────────────────────

def get_notification_settings() -> tuple:
    """Returns (hour, minute, count). Default: (8, 0, 1)."""
    if not db:
        return (8, 0, 1)
    try:
        doc = db.collection("settings").document("notifications").get()
        if doc.exists:
            data = doc.to_dict()
            return (
                int(data.get("hour", 8)),
                int(data.get("minute", 0)),
                int(data.get("count", 1)),
            )
    except Exception as e:
        logger.error(f"get_notification_settings error: {e}")
    return (8, 0, 1)


def get_notification_times_list() -> list:
    """Returns list of (hour, minute) tuples for each scheduled notification.
    Uses explicit 'times' list if saved, otherwise auto-spaces from base time."""
    if not db:
        return [(8, 0)]
    try:
        doc = db.collection("settings").document("notifications").get()
        if doc.exists:
            data  = doc.to_dict()
            times = data.get("times", [])
            count = int(data.get("count", 1))
            if times and len(times) == count:
                result = []
                for t in times:
                    parts = str(t).split(":")
                    result.append((int(parts[0]), int(parts[1])))
                return result
            # fallback: auto-space from base time
            base_h  = int(data.get("hour", 8))
            base_m  = int(data.get("minute", 0))
            intervals = {1: 0, 2: 8, 3: 6, 4: 4, 5: 3}
            gap = intervals.get(count, 0)
            return [((base_h + i * gap) % 24, base_m) for i in range(count)]
    except Exception as e:
        logger.error(f"get_notification_times_list error: {e}")
    return [(8, 0)]


def get_notification_time() -> tuple:
    """Backward-compat wrapper. Returns (hour, minute)."""
    h, m, _ = get_notification_settings()
    return (h, m)


def set_notification_times(times: list):
    """Saves explicit list of 'HH:MM' time strings and updates base time + count."""
    if not db or not times:
        return
    try:
        first = times[0].split(":")
        db.collection("settings").document("notifications").set({
            "hour":   int(first[0]),
            "minute": int(first[1]),
            "count":  len(times),
            "times":  times,
        }, merge=True)
    except Exception as e:
        logger.error(f"set_notification_times error: {e}")


def set_notification_time(hour: int, minute: int, count: int = None):
    """Saves notification time (and optionally count) to Firestore."""
    if not db:
        return
    try:
        data = {"hour": hour, "minute": minute, "times": []}  # clear explicit times
        if count is not None:
            data["count"] = count
        db.collection("settings").document("notifications").set(data, merge=True)
    except Exception as e:
        logger.error(f"set_notification_time error: {e}")


def set_notification_count(count: int):
    """Saves notification daily count to Firestore."""
    if not db:
        return
    try:
        db.collection("settings").document("notifications").set(
            {"count": count, "times": []}, merge=True  # clear explicit times on count change
        )
    except Exception as e:
        logger.error(f"set_notification_count error: {e}")


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


# ─── JAMOAVIY XATM ────────────────────────────────────────────────────────────

def get_or_create_recruiting_xatm() -> Optional[str]:
    """Returns the ID of an existing 'recruiting' xatm, or None if none exist."""
    if not db:
        return None
    try:
        docs = (
            db.collection("group_xatms")
            .where("status", "==", "recruiting")
            .limit(1)
            .stream()
        )
        for doc in docs:
            return doc.id
    except Exception as e:
        logger.error(f"get_or_create_recruiting_xatm query error: {e}")
    return None


def get_xatm_count() -> int:
    """Returns total number of xatms ever created (for auto-numbering)."""
    if not db:
        return 0
    try:
        docs = list(db.collection("group_xatms").stream())
        return len(docs)
    except Exception as e:
        logger.error(f"get_xatm_count error: {e}")
        return 0


def create_xatm(creator_id: int = None) -> str:
    """Creates a new numbered group xatm and returns its ID."""
    if not db:
        return "offline"
    try:
        xatm_number = get_xatm_count() + 1
        ref = db.collection("group_xatms").document()
        ref.set({
            "xatm_id":     ref.id,
            "xatm_number": xatm_number,
            "status":      "recruiting",
            "creator_id":  creator_id,
            "created_at":  _now(),
        })
        return ref.id
    except Exception as e:
        logger.error(f"create_xatm error: {e}")
        return "offline"


def get_xatm(xatm_id: str) -> Optional[dict]:
    if not db:
        return None
    try:
        doc = db.collection("group_xatms").document(xatm_id).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        logger.error(f"get_xatm error: {e}")
        return None


def get_xatm_juzs(xatm_id: str) -> list:
    """Returns list of assigned juz dicts for a given xatm."""
    if not db:
        return []
    try:
        docs = db.collection("group_xatm_juzs").where("xatm_id", "==", xatm_id).stream()
        return [d.to_dict() for d in docs]
    except Exception as e:
        logger.error(f"get_xatm_juzs error: {e}")
        return []


def assign_xatm_juz(xatm_id: str, juz_number: int, user_id: int) -> bool:
    """Assigns a juz to a user. Returns False if already taken."""
    if not db:
        return False
    doc_id = f"{xatm_id}_{juz_number}"
    ref = db.collection("group_xatm_juzs").document(doc_id)
    try:
        snap = ref.get()
        if snap.exists:
            return False
        ref.set({
            "xatm_id":     xatm_id,
            "juz_number":  juz_number,
            "user_id":     user_id,
            "status":      "assigned",
            "assigned_at": _now(),
            "completed_at": None,
        })
        return True
    except Exception as e:
        logger.error(f"assign_xatm_juz error: {e}")
        return False


def complete_xatm_juz(xatm_id: str, juz_number: int, user_id: int):
    """Marks a juz as completed by the user."""
    if not db:
        return
    doc_id = f"{xatm_id}_{juz_number}"
    try:
        db.collection("group_xatm_juzs").document(doc_id).update({
            "status":       "completed",
            "completed_at": _now(),
        })
    except Exception as e:
        logger.error(f"complete_xatm_juz error: {e}")


def check_and_update_xatm_status(xatm_id: str) -> Optional[str]:
    """
    Checks juz assignments and progresses xatm status if thresholds are met.
    Returns new status if it changed, else None.
    """
    if not db:
        return None
    try:
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
            db.collection("group_xatms").document(xatm_id).update({
                "status": new_status,
                f"{new_status}_at": _now(),
            })
            return new_status
    except Exception as e:
        logger.error(f"check_and_update_xatm_status error: {e}")
    return None


def get_xatm_stats() -> dict:
    """Aggregates global stats across all completed xatms."""
    if not db:
        return {}
    try:
        xatms = [d.to_dict() for d in db.collection("group_xatms").stream()]
        completed = [x for x in xatms if x.get("status") == "completed"]
        total_xatms = len(completed)

        # Count unique participants
        all_juzs = [d.to_dict() for d in db.collection("group_xatm_juzs").stream()]
        participants = set(j["user_id"] for j in all_juzs)

        # Duration stats
        durations = []
        for x in completed:
            created  = x.get("created_at")
            finished = x.get("completed_at")
            if created and finished:
                delta = (finished - created).total_seconds()
                if delta > 0:
                    durations.append(delta)

        avg     = int(sum(durations) / len(durations)) if durations else 0
        fastest = int(min(durations)) if durations else 0
        longest = int(max(durations)) if durations else 0

        return {
            "total_xatms":        total_xatms,
            "total_participants": len(participants),
            "avg_seconds":        avg,
            "fastest_seconds":    fastest,
            "longest_seconds":    longest,
        }
    except Exception as e:
        logger.error(f"get_xatm_stats error: {e}")
        return {}


def get_xatm_ranking(xatm_id: str) -> list:
    """Returns per-user ranking for a xatm sorted by completed juzs then speed."""
    if not db:
        return []
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
                assigned  = j.get("assigned_at")
                done      = j.get("completed_at")
                if assigned and done:
                    total_secs += int((done - assigned).total_seconds())
            ranking.append({
                "user_id":      uid,
                "name":         name,
                "completed":    len(completed),
                "total":        len(user_juzs),
                "total_seconds": total_secs,
            })

        ranking.sort(key=lambda x: (-x["completed"], x["total_seconds"]))
        return ranking
    except Exception as e:
        logger.error(f"get_xatm_ranking error: {e}")
        return []


def unassign_xatm_juz(xatm_id: str, juz_number: int, user_id: int):
    """Removes a juz assignment (only if owned by user and not completed)."""
    if not db:
        return
    doc_id = f"{xatm_id}_{juz_number}"
    try:
        snap = db.collection("group_xatm_juzs").document(doc_id).get()
        if snap.exists:
            data = snap.to_dict()
            if data.get("user_id") == user_id and data.get("status") != "completed":
                db.collection("group_xatm_juzs").document(doc_id).delete()
    except Exception as e:
        logger.error(f"unassign_xatm_juz error: {e}")


def uncomplete_xatm_juz(xatm_id: str, juz_number: int, user_id: int):
    """Reverts a completed juz back to assigned status."""
    if not db:
        return
    doc_id = f"{xatm_id}_{juz_number}"
    try:
        snap = db.collection("group_xatm_juzs").document(doc_id).get()
        if snap.exists and snap.to_dict().get("user_id") == user_id:
            db.collection("group_xatm_juzs").document(doc_id).update({
                "status":       "assigned",
                "completed_at": None,
            })
            # Revert xatm status from completed back to active if needed
            xatm = get_xatm(xatm_id)
            if xatm and xatm.get("status") == "completed":
                db.collection("group_xatms").document(xatm_id).update({
                    "status": "active",
                    "completed_at": None,
                })
    except Exception as e:
        logger.error(f"uncomplete_xatm_juz error: {e}")


def get_user_xatms(user_id: int) -> list:
    """Returns list of {xatm, juzs} dicts for all xatms the user participated in."""
    if not db:
        return []
    try:
        juz_docs = (
            db.collection("group_xatm_juzs")
            .where("user_id", "==", user_id)
            .stream()
        )
        # Group by xatm_id
        by_xatm: dict = {}
        for doc in juz_docs:
            j = doc.to_dict()
            by_xatm.setdefault(j["xatm_id"], []).append(j)

        result = []
        for xatm_id, juzs in by_xatm.items():
            xatm = get_xatm(xatm_id)
            if xatm:
                result.append({"xatm": xatm, "juzs": juzs})

        # Sort by xatm_number
        result.sort(key=lambda x: x["xatm"].get("xatm_number", 0))
        return result
    except Exception as e:
        logger.error(f"get_user_xatms error: {e}")
        return []


def backfill_xatm_numbers():
    """One-time migration: assign xatm_number to any xatm missing it, ordered by created_at."""
    if not db:
        return
    try:
        docs = list(db.collection("group_xatms").stream())
        missing = [d for d in docs if "xatm_number" not in (d.to_dict() or {})]
        if not missing:
            return
        # Sort missing by created_at so numbering is chronological
        missing.sort(key=lambda d: d.to_dict().get("created_at") or _now())
        # Find highest existing number
        existing_nums = [
            d.to_dict().get("xatm_number", 0)
            for d in docs
            if "xatm_number" in (d.to_dict() or {})
        ]
        next_num = max(existing_nums, default=0) + 1
        for doc in missing:
            db.collection("group_xatms").document(doc.id).update({"xatm_number": next_num})
            logger.info(f"Backfilled xatm {doc.id} → #{next_num}")
            next_num += 1
    except Exception as e:
        logger.error(f"backfill_xatm_numbers error: {e}")
