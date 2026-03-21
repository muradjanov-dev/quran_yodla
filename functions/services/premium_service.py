"""
premium_service.py — Trial and premium subscription management.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
import pytz

from config import TRIAL_DAYS, LOCAL_TZ

logger = logging.getLogger(__name__)
TZ = pytz.timezone(LOCAL_TZ)


def _now() -> datetime:
    return datetime.now(TZ)


def activate_trial(user_id: int) -> bool:
    """Activates 3-day free trial. Returns False if already used."""
    from services.firebase_service import get_user, update_user
    user = get_user(user_id)
    if not user:
        return False

    premium = user.get("premium", {})
    if premium.get("trial_used"):
        return False  # Already used

    now = _now()
    expires = now + timedelta(days=TRIAL_DAYS)
    update_user(user_id, {
        "premium.is_active":      True,
        "premium.expires_at":     expires,
        "premium.trial_used":     True,
        "premium.trial_started_at": now,
    })
    logger.info(f"Trial activated for user {user_id}, expires {expires}")
    return True


def activate_premium(user_id: int, days: int = 30) -> datetime:
    """Grants premium for N days. Returns expiry datetime."""
    from services.firebase_service import get_user, update_user
    user = get_user(user_id)
    now = _now()

    # Extend existing premium if active
    if user:
        existing_expires = user.get("premium", {}).get("expires_at")
        if existing_expires and hasattr(existing_expires, "astimezone"):
            existing_expires = existing_expires.astimezone(TZ)
            if existing_expires > now:
                expires = existing_expires + timedelta(days=days)
            else:
                expires = now + timedelta(days=days)
        else:
            expires = now + timedelta(days=days)
    else:
        expires = now + timedelta(days=days)

    update_user(user_id, {
        "premium.is_active":  True,
        "premium.expires_at": expires,
    })
    logger.info(f"Premium activated for user {user_id}, expires {expires}")
    return expires


def deactivate_premium(user_id: int):
    from services.firebase_service import update_user
    update_user(user_id, {
        "premium.is_active":  False,
        "premium.expires_at": None,
    })


def is_premium(user: dict) -> bool:
    """Check if user has active premium (trial or paid)."""
    premium = user.get("premium", {})
    if not premium.get("is_active"):
        return False
    expires_at = premium.get("expires_at")
    if expires_at is None:
        return False
    now = _now()
    if hasattr(expires_at, "astimezone"):
        expires_at = expires_at.astimezone(TZ)
    return expires_at > now


def can_use_trial(user: dict) -> bool:
    return not user.get("premium", {}).get("trial_used", False)


def get_premium_expiry_str(user: dict) -> Optional[str]:
    expires_at = user.get("premium", {}).get("expires_at")
    if not expires_at:
        return None
    if hasattr(expires_at, "astimezone"):
        expires_at = expires_at.astimezone(TZ)
    return expires_at.strftime("%d %B %Y")


def check_and_expire_premiums():
    """Job: called periodically to expire overdue premiums."""
    from services.firebase_service import get_all_users, update_user
    now = _now()
    users = get_all_users()
    expired = 0
    for user in users:
        premium = user.get("premium", {})
        if not premium.get("is_active"):
            continue
        expires_at = premium.get("expires_at")
        if not expires_at:
            continue
        if hasattr(expires_at, "astimezone"):
            expires_at = expires_at.astimezone(TZ)
        if expires_at <= now:
            update_user(user["telegram_id"], {"premium.is_active": False})
            expired += 1
    logger.info(f"Premium expiry check: {expired} expired")
