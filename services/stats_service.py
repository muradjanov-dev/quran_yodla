"""
stats_service.py — Aggregated statistics for user profile display.
"""

import logging
from typing import Optional
from services.firebase_service import (
    get_user, get_daily_stats, get_period_stats, get_user_rank
)
from services.gamification import get_level
from services.premium_service import is_premium, get_premium_expiry_str

logger = logging.getLogger(__name__)


def format_time(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} daqiqa"
    hours = minutes // 60
    mins  = minutes % 60
    if mins == 0:
        return f"{hours} soat"
    return f"{hours} soat {mins} daqiqa"


def build_progress_bar(current: int, total: int, length: int = 12) -> str:
    if total <= 0:
        return "░" * length
    filled = int(length * current / total)
    return "█" * filled + "░" * (length - filled)


def get_profile_data(user_id: int) -> Optional[dict]:
    """Returns all data needed for the profile page."""
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

    completed_surahs   = progress.get("completed_surahs", [])
    completed_juz      = progress.get("completed_juz", [])
    current_surah_num  = progress.get("current_surah")
    current_ayah       = progress.get("current_ayah", 1)

    # 6236 total ayahs in Quran
    total_quran_ayahs  = 6236
    percent_complete   = round(total_verses / total_quran_ayahs * 100, 1) if total_verses else 0
    quran_progress_bar = build_progress_bar(total_verses, total_quran_ayahs, 20)

    return {
        "user":              user,
        "full_name":         user.get("full_name", "Foydalanuvchi"),
        "total_verses":      total_verses,
        "total_reps":        total_reps,
        "total_time":        format_time(total_mins),
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
        "quran_progress_bar":quran_progress_bar,
        "is_premium":        is_premium(user),
        "premium_expiry":    get_premium_expiry_str(user),
        "referral_code":     user.get("referral_code", ""),
        "referral_count":    user.get("referral_count", 0),
    }


def get_bot_wide_stats() -> dict:
    """Admin: global bot statistics."""
    from services.firebase_service import get_all_users, get_pending_premium_requests
    users = get_all_users()
    premium_users = [u for u in users if u.get("premium", {}).get("is_active")]
    from datetime import datetime, timedelta
    import pytz
    from config import LOCAL_TZ
    TZ = pytz.timezone(LOCAL_TZ)
    now = datetime.now(TZ)
    week_ago = now - timedelta(days=7)
    today_str = now.strftime("%Y-%m-%d")
    new_today = [u for u in users
                 if u.get("registration_date") and
                 (hasattr(u["registration_date"], "astimezone") and
                  u["registration_date"].astimezone(TZ).strftime("%Y-%m-%d") == today_str)]
    active_7d = [u for u in users
                 if u.get("stats", {}).get("last_activity_date") and
                 hasattr(u["stats"]["last_activity_date"], "astimezone") and
                 u["stats"]["last_activity_date"].astimezone(TZ) >= week_ago]
    active_today = [u for u in users
                    if u.get("stats", {}).get("last_activity_date") and
                    hasattr(u["stats"]["last_activity_date"], "astimezone") and
                    u["stats"]["last_activity_date"].astimezone(TZ).strftime("%Y-%m-%d") == today_str]
    pending_premium = get_pending_premium_requests()
    return {
        "total_users":    len(users),
        "premium_users":  len(premium_users),
        "new_today":      len(new_today),
        "active_today":   len(active_today),
        "active_7d":      len(active_7d),
        "pending_premium":len(pending_premium),
    }
