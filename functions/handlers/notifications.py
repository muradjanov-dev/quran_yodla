"""
notifications.py — Daily notification sender (called by APScheduler).
"""

import logging
import random
import json
from pathlib import Path
from datetime import datetime, timedelta
import asyncio
import pytz

from services.firebase_service import (
    get_all_notification_enabled_users, get_user,
    get_daily_stats, get_period_stats, log_notification
)
from services.stats_service import format_time
from utils.keyboards import snooze_keyboard, open_memorize_keyboard

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
TZ = pytz.timezone("Asia/Tashkent")


def _load_quotes() -> list:
    with open(DATA_DIR / "daily_quotes.json", encoding="utf-8") as f:
        return json.load(f)


def _build_notification(user: dict) -> tuple[str, object]:
    """Returns (text, keyboard) for the notification."""
    name    = user.get("full_name", "Do'stim")
    stats   = user.get("stats", {})
    streak  = stats.get("current_streak_days", 0)
    today   = get_daily_stats(user["telegram_id"])
    t_verses= today.get("verses_read", 0)

    quotes = _load_quotes()
    notif_type = random.choice(["motivational", "quote", "reward", "streak"])

    if streak >= 3 and random.random() < 0.4:
        notif_type = "streak"

    # Haftalik hisobot (Dushanba)
    now = datetime.now(TZ)
    if now.weekday() == 0 and now.hour < 10:  # Monday morning
        notif_type = "weekly"

    if notif_type == "streak" and streak >= 1:
        text = (
            f"🔥 {name}, {streak}-kunlik streakingiz bor!\n\n"
            f"Bugun ham bir oyat yodlasangiz streak saqlanadi.\n"
            f"Uzmaslik uchun hoziroq 1 daqiqa vaqt ajrating!"
        )
        keyboard = snooze_keyboard()

    elif notif_type == "quote":
        quote_items = [q for q in quotes if q["type"] == "quote"]
        q = random.choice(quote_items) if quote_items else quotes[0]
        text = (
            f"🌙 Assalomu alaykum, {name}!\n\n"
            f"💬 {q['author']}:\n\"{q['text']}\"\n\n"
            f"Bugungi progress: {t_verses} oyat yodladingiz"
        )
        keyboard = open_memorize_keyboard()

    elif notif_type == "weekly":
        week_stats = get_period_stats(user["telegram_id"], "week")
        text = (
            f"📊 HAFTALIK HISOBOT, {name}!\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Bu hafta:\n"
            f"📖 Oyatlar: {week_stats.get('verses_read', 0)}\n"
            f"🔄 Takrorlar: {week_stats.get('repetitions', 0)}\n"
            f"⏱ Vaqt: {week_stats.get('minutes', 0)} daqiqa\n"
            f"💫 Himmat: +{week_stats.get('himmat_earned', 0)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        keyboard = open_memorize_keyboard()

    elif notif_type == "reward":
        text = (
            f"⭐ Assalomu alaykum, {name}!\n\n"
            f"📿 Alloh taolo va'da qilgan:\n"
            f"\"Qur'on qori qiyomatda ota-onasiga nur toji kiydirilur...\"\n\n"
            f"Bugun ham bir oyat yodlang — ajr bekor ketmaydi! 🤲"
        )
        keyboard = open_memorize_keyboard()

    else:  # motivational
        mot_items = [q for q in quotes if q["type"] == "motivational"]
        q = random.choice(mot_items) if mot_items else quotes[0]
        text = (
            f"🌅 Assalomu alaykum, {name}!\n\n"
            f"📖 {q['text']}\n\n"
            f"Bugun ham davom etamizmi? 💪"
        )
        keyboard = open_memorize_keyboard()

    return text, keyboard, notif_type


async def send_daily_notifications(bot=None):
    """Main scheduled job: send notifications to all enabled users."""
    if bot is None:
        logger.warning("send_daily_notifications called without bot instance")
        return

    users   = get_all_notification_enabled_users()
    sent    = 0
    failed  = 0

    for user in users:
        uid = user.get("telegram_id")
        if not uid:
            continue
        try:
            text, keyboard, notif_type = _build_notification(user)
            await bot.send_message(
                chat_id      = uid,
                text         = text,
                reply_markup = keyboard
            )
            log_notification(uid, notif_type, text[:80])
            sent += 1
        except Exception as e:
            logger.warning(f"Notification failed for {uid}: {e}")
            failed += 1

        await asyncio.sleep(0.05)  # avoid flood

    logger.info(f"Daily notifications: sent={sent}, failed={failed}")


async def handle_snooze(update: Update, context):
    """Handles '⏰ Keyinroq eslatish' (2h snooze)."""
    query = update.callback_query
    await query.answer("2 soatdan so'ng eslatiladi ✅")
    user_id = query.from_user.id
    user    = get_user(user_id)
    if not user:
        return
    name = user.get("full_name", "Do'stim")

    async def send_snooze():
        await asyncio.sleep(7200)  # 2 hours
        try:
            from utils.keyboards import open_memorize_keyboard
            await context.bot.send_message(
                chat_id      = user_id,
                text         = f"⏰ {name}, 2 soat o'tdi! Yodlashni davom ettirishingiz mumkin 📖",
                reply_markup = open_memorize_keyboard()
            )
        except Exception:
            pass

    asyncio.create_task(send_snooze())


# Prevent circular import — import Update lazily
from telegram import Update


def register_notification_handlers(app):
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(handle_snooze, pattern="^snooze_2h$"))
