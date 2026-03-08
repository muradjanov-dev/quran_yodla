"""
gamification.py — Himmat points, levels, and streak management.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, Tuple
import pytz

from config import (
    LEVELS, STREAK_BONUSES,
    HIMMAT_PER_3_REPS, HIMMAT_PER_7_REPS, HIMMAT_PER_11_REPS,
    HIMMAT_PER_ACCUMULATION, HIMMAT_PER_AYAH_COMPLETE,
    HIMMAT_PER_SURAH_COMPLETE_MULTIPLIER, HIMMAT_PER_JUZ_COMPLETE,
    ONBOARDING_BONUS, FIRST_AYAH_BONUS, DAILY_LOGIN_BONUS, LOCAL_TZ
)

logger = logging.getLogger(__name__)
TZ = pytz.timezone(LOCAL_TZ)


# ─── Level System ─────────────────────────────────────────────────────────────

def get_level(himmat_points: int) -> Tuple[int, str]:
    """Returns (level_number, level_name) based on himmat points."""
    level_num = 1
    level_name = LEVELS[0][1]
    for i, (threshold, name) in enumerate(LEVELS):
        if himmat_points >= threshold:
            level_num = i + 1
            level_name = name
    return level_num, level_name


def check_level_up(old_points: int, new_points: int) -> Optional[Tuple[int, str]]:
    """Returns new (level, name) if user leveled up, else None."""
    old_level = get_level(old_points)
    new_level = get_level(new_points)
    if new_level[0] > old_level[0]:
        return new_level
    return None


# ─── Streak Management ────────────────────────────────────────────────────────

def update_streak(user: dict) -> Tuple[int, int, bool, Optional[int]]:
    """
    Calculates updated streak values.
    Returns: (new_streak, longest_streak, streak_broken, streak_bonus)
    """
    stats = user.get("stats", {})
    current_streak = stats.get("current_streak_days", 0)
    longest_streak = stats.get("longest_streak_days", 0)
    last_activity  = stats.get("last_activity_date")

    today = datetime.now(TZ).date()

    if last_activity is None:
        # First ever activity
        new_streak      = 1
        streak_broken   = False
    else:
        if hasattr(last_activity, "date"):
            last_date = last_activity.date()
        elif isinstance(last_activity, str):
            last_date = datetime.fromisoformat(last_activity).date()
        else:
            last_date = today

        delta = (today - last_date).days

        if delta == 0:
            # Same day — streak unchanged
            new_streak    = current_streak
            streak_broken = False
        elif delta == 1:
            # Consecutive day — increment
            new_streak    = current_streak + 1
            streak_broken = False
        else:
            # Gap — broken
            new_streak    = 1
            streak_broken = True

    new_longest   = max(longest_streak, new_streak)
    streak_bonus  = STREAK_BONUSES.get(new_streak)  # None if no milestone

    return new_streak, new_longest, streak_broken, streak_bonus


# ─── Points Calculation ───────────────────────────────────────────────────────

def points_for_repetition(rep_count: int) -> int:
    """Returns himmat points for completing a repetition round."""
    if rep_count == 3:
        return HIMMAT_PER_3_REPS
    elif rep_count == 7:
        return HIMMAT_PER_7_REPS
    elif rep_count == 11:
        return HIMMAT_PER_11_REPS
    return 0


def points_for_accumulation(ayah_count: int) -> int:
    return ayah_count * HIMMAT_PER_ACCUMULATION


def points_for_ayah_complete() -> int:
    return HIMMAT_PER_AYAH_COMPLETE


def points_for_surah_complete(ayah_count: int) -> int:
    return ayah_count * HIMMAT_PER_SURAH_COMPLETE_MULTIPLIER


def points_for_juz_complete() -> int:
    return HIMMAT_PER_JUZ_COMPLETE


def points_for_onboarding() -> int:
    return ONBOARDING_BONUS


def points_for_first_ayah() -> int:
    return FIRST_AYAH_BONUS


def points_for_daily_login() -> int:
    return DAILY_LOGIN_BONUS


# ─── Apply Points ─────────────────────────────────────────────────────────────

def award_points(user_id: int, points: int, reason: str = ""):
    """Add himmat points to user and update leaderboard."""
    from services.firebase_service import get_user, update_user, update_leaderboard_entry
    from google.cloud.firestore_v1 import Increment

    if points <= 0:
        return

    user = get_user(user_id)
    if not user:
        return

    old_points = user.get("stats", {}).get("himmat_points", 0)
    new_points = old_points + points

    # Update user stats
    try:
        from firebase_config import db
        if db:
            db.collection("users").document(str(user_id)).update({
                "stats.himmat_points": Increment(points)
            })
    except Exception as e:
        logger.error(f"award_points error: {e}")

    # Update leaderboard
    try:
        update_leaderboard_entry(
            user_id,
            user.get("full_name", ""),
            user.get("username", ""),
            user.get("stats", {}).get("total_verses_read", 0),
            new_points
        )
    except Exception as e:
        logger.error(f"leaderboard update error: {e}")

    logger.info(f"User {user_id} earned {points} Himmat ({reason}). Total: {new_points}")
    return check_level_up(old_points, new_points)


def apply_streak_update(user_id: int) -> Tuple[int, bool, Optional[int]]:
    """
    Reads user from DB, calculates new streak, saves to Firebase.
    Returns (new_streak, streak_broken, streak_bonus_points).
    Also awards streak milestone bonus if applicable.
    """
    from services.firebase_service import get_user
    from firebase_config import db

    user = get_user(user_id)
    if not user:
        return 0, False, None

    new_streak, new_longest, streak_broken, streak_bonus = update_streak(user)

    try:
        if db:
            db.collection("users").document(str(user_id)).update({
                "stats.current_streak_days": new_streak,
                "stats.longest_streak_days": new_longest,
            })
    except Exception as e:
        logger.error(f"apply_streak_update Firebase error: {e}")

    if streak_bonus:
        award_points(user_id, streak_bonus, f"streak_milestone_{new_streak}d")
        logger.info(f"User {user_id} streak milestone: {new_streak} days, +{streak_bonus} Himmat")

    return new_streak, streak_broken, streak_bonus


def check_and_award_daily_login(user_id: int) -> bool:
    """
    Awards daily login bonus if this is the user's first activity today.
    Returns True if bonus was awarded.
    """
    from services.firebase_service import get_daily_ayah_count
    count = get_daily_ayah_count(user_id)
    if count == 0:
        award_points(user_id, points_for_daily_login(), "daily_login")
        logger.info(f"User {user_id} daily login bonus awarded")
        return True
    return False


def check_and_award_first_ayah(user_id: int) -> bool:
    """
    Awards first-ever ayah bonus if user's total_verses_read was 0.
    Returns True if bonus was awarded.
    """
    from services.firebase_service import get_user
    user = get_user(user_id)
    if user and user.get("stats", {}).get("total_verses_read", 0) == 0:
        award_points(user_id, points_for_first_ayah(), "first_ayah")
        logger.info(f"User {user_id} first ayah bonus awarded")
        return True
    return False


def format_himmat(points: int) -> str:
    """Format himmat points with commas."""
    return f"{points:,}"
