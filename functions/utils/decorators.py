"""
decorators.py — Auth, premium, admin, and rate-limit decorators.
"""

import logging
import functools
from datetime import datetime
from typing import Callable
from telegram import Update
from telegram.ext import ContextTypes
import pytz

from config import ADMIN_ID, DAILY_FREE_LIMIT, LOCAL_TZ

logger = logging.getLogger(__name__)

# Simple in-memory rate limiter: {user_id: [timestamps]}
_rate_store: dict = {}
RATE_LIMIT = 30      # max requests per window
RATE_WINDOW = 60     # seconds


def rate_limit(func: Callable) -> Callable:
    """Blocks users exceeding 30 messages/minute."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return
        uid = user.id
        now = datetime.utcnow().timestamp()
        history = _rate_store.get(uid, [])
        history = [t for t in history if now - t < RATE_WINDOW]
        if len(history) >= RATE_LIMIT:
            logger.warning(f"Rate limit hit: user {uid}")
            return
        history.append(now)
        _rate_store[uid] = history
        return await func(update, context, *args, **kwargs)
    return wrapper


def require_user(func: Callable) -> Callable:
    """Ensures user exists in Firestore; creates if missing."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        tg_user = update.effective_user
        if not tg_user:
            return
        from services.firebase_service import get_user, create_user
        user = get_user(tg_user.id)
        if not user:
            user = create_user(
                tg_user.id,
                f"@{tg_user.username}" if tg_user.username else "",
                tg_user.full_name or ""
            )
        context.user_data["db_user"] = user
        return await func(update, context, *args, **kwargs)
    return wrapper


def admin_only(func: Callable) -> Callable:
    """Silently ignores non-admin users."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or user.id != ADMIN_ID:
            return  # silent ignore
        return await func(update, context, *args, **kwargs)
    return wrapper


def check_premium_or_limit(func: Callable) -> Callable:
    """
    Checks daily free limit for non-premium users.
    If limit reached, shows upgrade message and aborts.
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        tg_user = update.effective_user
        if not tg_user:
            return
        from services.firebase_service import get_user, get_daily_ayah_count
        from services.premium_service import is_premium

        user = get_user(tg_user.id)
        if not user:
            return await func(update, context, *args, **kwargs)

        if is_premium(user):
            return await func(update, context, *args, **kwargs)

        # Free user — check limit
        count = get_daily_ayah_count(tg_user.id)
        if count >= DAILY_FREE_LIMIT:
            from utils.messages import limit_reached_message
            from utils.keyboards import limit_reached_keyboard
            msg = update.callback_query or update.message
            if update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.message.reply_text(
                    limit_reached_message(),
                    reply_markup=limit_reached_keyboard()
                )
            else:
                await update.message.reply_text(
                    limit_reached_message(),
                    reply_markup=limit_reached_keyboard()
                )
            return  # Abort handler

        return await func(update, context, *args, **kwargs)
    return wrapper
