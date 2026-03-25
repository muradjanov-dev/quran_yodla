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

from telegram import Update
from services.firebase_service import (
    get_all_notification_enabled_users, get_user,
    get_daily_stats, get_period_stats, log_notification,
    get_user_percentile
)
from services.stats_service import format_time
from utils.keyboards import snooze_keyboard, open_memorize_keyboard

# Quran constants for calculations
TOTAL_AYAHS = 6236
AVG_LETTERS_PER_AYAH = 40   # approximate
HASANA_PER_LETTER = 10       # each letter = 10 hasana (reward)

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
TZ = pytz.timezone("Asia/Tashkent")


def _load_quotes() -> list:
    with open(DATA_DIR / "daily_quotes.json", encoding="utf-8") as f:
        return json.load(f)


def _calc_hafiz_projection(daily_ayahs: int) -> str:
    """Calculate how many months to become Hafiz at a given daily pace."""
    if daily_ayahs <= 0:
        return ""
    days_needed = TOTAL_AYAHS / daily_ayahs
    months = days_needed / 30
    if months < 1:
        return "1 oydan kam"
    return f"{int(months)} oy"


def _calc_daily_ajr(daily_ayahs: int) -> str:
    """Approximate daily hasana (ajr) from memorizing ayahs.
    Hadith: har bir harf uchun 10 ta savob."""
    if daily_ayahs <= 0:
        return "0"
    total = daily_ayahs * AVG_LETTERS_PER_AYAH * HASANA_PER_LETTER
    if total >= 1_000_000:
        return f"{total / 1_000_000:.1f} million"
    if total >= 1000:
        return f"{total:,}"
    return str(total)


def _build_motivation_text(user: dict) -> str:
    """Build personalized motivation text with Hafiz projection, ajr, and percentile."""
    name = user.get("full_name", "Do'stim")
    uid = user.get("telegram_id")
    stats = user.get("stats", {})
    total_verses = stats.get("total_verses_read", 0)
    remaining = max(TOTAL_AYAHS - total_verses, 0)

    # Calculate user's average daily pace
    reg_date = user.get("registration_date")
    now = datetime.now(TZ)
    if reg_date and hasattr(reg_date, "astimezone"):
        days_active = max((now - reg_date.astimezone(TZ)).days, 1)
    else:
        days_active = 1
    avg_daily = total_verses / days_active if days_active > 0 else 0

    percentile = get_user_percentile(uid) if uid else 0

    lines = [f"📊 {name}, sizning shaxsiy hisobingiz:\n"]

    if total_verses == 0:
        # New user — projection based on different commitments
        lines.append("Siz hali yodlashni boshlamadingiz.\n")
        lines.append("📌 Agar har kuni shuncha oyat yodlasangiz:\n")
        for daily in [3, 5, 10, 20]:
            proj = _calc_hafiz_projection(daily)
            ajr = _calc_daily_ajr(daily)
            lines.append(f"  • {daily} oyat/kun → Hofiz {proj}da | kunlik ~{ajr} savob")
        lines.append(f"\n📿 Hadis: \"Qur'on o'qigan kishiga har bir harf uchun "
                      f"10 ta savob yoziladi\" (Termiziy)")
        lines.append(f"\n💪 Birinchi qadamni qo'ying — 1 oyat ham katta boshlang'ich!")
    else:
        # Active user — personalized stats
        if avg_daily >= 1:
            proj = _calc_hafiz_projection(avg_daily)
            lines.append(f"📖 Jami yodlangan: {total_verses:,} / {TOTAL_AYAHS:,} oyat")
            lines.append(f"📈 O'rtacha tezlik: {avg_daily:.1f} oyat/kun")
            lines.append(f"🕌 Shu tezlikda Hofiz bo'lasiz: ~{proj}")
        else:
            lines.append(f"📖 Jami yodlangan: {total_verses:,} oyat")
            lines.append(f"⏳ Qolgan: {remaining:,} oyat")

        # Daily ajr calculation
        daily_pace = max(avg_daily, 1)
        ajr = _calc_daily_ajr(int(daily_pace))
        lines.append(f"\n📿 Kunlik taxminiy savob: ~{ajr} hasana")
        lines.append(f"   (har harf = 10 savob, Termiziy rivoyati)")

        # Percentile ranking
        if percentile > 0:
            lines.append(f"\n🏅 Siz foydalanuvchilarning {percentile}% dan oldinda!")

        # Faster projection
        if avg_daily < 10:
            faster_daily = min(int(avg_daily) + 5, 20)
            faster_proj = _calc_hafiz_projection(faster_daily)
            lines.append(f"\n💡 Agar kuniga {faster_daily} oyat yodlasangiz → Hofiz {faster_proj}da!")

    return "\n".join(lines)


def _build_notification(user: dict) -> tuple:
    """Returns (text, keyboard, notif_type) for the notification."""
    name    = user.get("full_name", "Do'stim")
    stats   = user.get("stats", {})
    streak  = stats.get("current_streak_days", 0)
    today   = get_daily_stats(user["telegram_id"])
    t_verses= today.get("verses_read", 0)

    quotes = _load_quotes()

    # Haftalik hisobot (Dushanba)
    now = datetime.now(TZ)
    if now.weekday() == 0 and now.hour < 10:
        notif_type = "weekly"
    elif streak >= 3 and random.random() < 0.4:
        notif_type = "streak"
    elif random.random() < 0.3:
        notif_type = "motivation"  # 30% chance for personalized stats
    else:
        notif_type = random.choice(["motivational", "quote", "hadith", "ayah", "reward"])

    if notif_type == "streak" and streak >= 1:
        text = (
            f"🌟 {name}, {streak}-kunlik streakingiz bor!\n\n"
            f"Bugun ham bir oyat yodlasangiz streak saqlanadi.\n"
            f"Uzmaslik uchun hoziroq 1 daqiqa vaqt ajrating!"
        )
        keyboard = snooze_keyboard()

    elif notif_type == "motivation":
        text = _build_motivation_text(user)
        keyboard = open_memorize_keyboard()

    elif notif_type == "quote":
        quote_items = [q for q in quotes if q["type"] == "quote"]
        q = random.choice(quote_items) if quote_items else quotes[0]
        text = (
            f"🌙 Assalomu alaykum, {name}!\n\n"
            f"💬 {q['author']}:\n\"{q['text']}\"\n\n"
            f"Bugungi progress: {t_verses} oyat yodladingiz"
        )
        keyboard = open_memorize_keyboard()

    elif notif_type == "hadith":
        hadith_items = [q for q in quotes if q["type"] == "hadith"]
        q = random.choice(hadith_items) if hadith_items else quotes[0]
        text = (
            f"📿 Assalomu alaykum, {name}!\n\n"
            f"Hadisi sharif — {q['author']}:\n\n"
            f"{q['text']}\n\n"
            f"Bugun ham Qur'on yodlashni davom eting! 🤲"
        )
        keyboard = open_memorize_keyboard()

    elif notif_type == "ayah":
        ayah_items = [q for q in quotes if q["type"] == "ayah"]
        q = random.choice(ayah_items) if ayah_items else quotes[0]
        text = (
            f"📖 Assalomu alaykum, {name}!\n\n"
            f"Qur'oni Karimdan — {q['author']}:\n\n"
            f"{q['text']}\n\n"
            f"Alloh bizni Qur'on ahllaridan qilsin! 🌟"
        )
        keyboard = open_memorize_keyboard()

    elif notif_type == "weekly":
        week_stats = get_period_stats(user["telegram_id"], "week")
        text = (
            f"📊 HAFTALIK HISOBOT, {name}!\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Bu hafta:\n"
            f"📖 Oyatlar: {week_stats.get('verses_read', 0)}\n"
            f"🔄 Takrorlar: {week_stats.get('repetitions', 0)}\n"
            f"⏱ Vaqt: {week_stats.get('minutes', 0)} daqiqa\n"
            f"💎 Himmat: +{week_stats.get('himmat_earned', 0)}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        keyboard = open_memorize_keyboard()

    elif notif_type == "reward":
        # Calculate personalized ajr
        total_v = stats.get("total_verses_read", 0)
        total_ajr = total_v * AVG_LETTERS_PER_AYAH * HASANA_PER_LETTER
        ajr_str = f"{total_ajr:,}" if total_ajr < 1_000_000 else f"{total_ajr/1_000_000:.1f} million"
        text = (
            f"⭐ Assalomu alaykum, {name}!\n\n"
            f"📿 Alloh taolo va'da qilgan:\n"
            f"\"Qur'on o'qigan kishiga har bir harf uchun "
            f"10 ta savob yoziladi\" (Termiziy)\n\n"
            f"📖 Siz {total_v:,} oyat yodladingiz\n"
            f"📿 Taxminiy savobingiz: ~{ajr_str} hasana!\n\n"
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

async def handle_memo_tomorrow(update, context):
    """User taps 'Ertaga davom etish' on limit_reached message."""
    query = update.callback_query
    await query.answer()
    try:
        await query.message.edit_text(
            "✅ Ertaga davom etamiz! In shaa ALLOH 🌙\n\n"
            "Qolgan oyatlaringiz sizni kutmoqda 📖"
        )
    except Exception:
        pass


def register_notification_handlers(app):
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(handle_snooze,        pattern="^snooze_2h$"))
    app.add_handler(CallbackQueryHandler(handle_memo_tomorrow, pattern="^memo_tomorrow$"))
