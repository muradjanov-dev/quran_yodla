"""
achievements.py — Yutuq va Mukofotlar (Achievements & Rewards) system.

Achievements are stored in Firebase under users/{uid}/achievements/{achievement_id}
as { "unlocked_at": <timestamp>, "notified": bool }.

When an achievement is unlocked:
  1. Save it to Firebase
  2. Award bonus XP to the user
  3. Broadcast a notification to ALL other users with a "Tabriklash" button
  4. When any user taps Tabriklash, the achiever is notified with their name
"""

import logging
from datetime import datetime
from typing import Optional
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from config import LOCAL_TZ, ADMIN_ID

logger = logging.getLogger(__name__)
TZ = pytz.timezone(LOCAL_TZ)

# ─── Achievement Definitions ──────────────────────────────────────────────────
# Each achievement: id, emoji, title (uz), description, bonus_xp, condition_key
# condition_key is used when checking — maps to a check function below.

ACHIEVEMENTS = [
    # ── Oyat yodlash ──────────────────────────────────────────────────────────
    {
        "id": "first_ayah",
        "emoji": "🌱",
        "title": "Birinchi Qadam",
        "desc": "Birinchi oyatni yodladi",
        "bonus_xp": 50,
        "condition": lambda u, s: _total_verses(u) >= 1,
    },
    {
        "id": "verses_10",
        "emoji": "📖",
        "title": "10 Oyat",
        "desc": "10 ta oyat yodladi",
        "bonus_xp": 100,
        "condition": lambda u, s: _total_verses(u) >= 10,
    },
    {
        "id": "verses_50",
        "emoji": "📗",
        "title": "50 Oyat",
        "desc": "50 ta oyat yodladi",
        "bonus_xp": 250,
        "condition": lambda u, s: _total_verses(u) >= 50,
    },
    {
        "id": "verses_100",
        "emoji": "📘",
        "title": "100 Oyat — Yuz Xayr",
        "desc": "100 ta oyat yodladi",
        "bonus_xp": 500,
        "condition": lambda u, s: _total_verses(u) >= 100,
    },
    {
        "id": "verses_300",
        "emoji": "📙",
        "title": "300 Oyat",
        "desc": "300 ta oyat yodladi",
        "bonus_xp": 1000,
        "condition": lambda u, s: _total_verses(u) >= 300,
    },
    {
        "id": "verses_500",
        "emoji": "🌟",
        "title": "500 Oyat",
        "desc": "500 ta oyat yodladi",
        "bonus_xp": 2000,
        "condition": lambda u, s: _total_verses(u) >= 500,
    },
    {
        "id": "verses_1000",
        "emoji": "⭐",
        "title": "1000 Oyat — Ming Nur",
        "desc": "1000 ta oyat yodladi",
        "bonus_xp": 5000,
        "condition": lambda u, s: _total_verses(u) >= 1000,
    },
    {
        "id": "verses_3000",
        "emoji": "🌙",
        "title": "3000 Oyat",
        "desc": "3000 ta oyat yodladi",
        "bonus_xp": 10000,
        "condition": lambda u, s: _total_verses(u) >= 3000,
    },
    {
        "id": "full_quran",
        "emoji": "👑",
        "title": "Hofiz — To'liq Qur'on",
        "desc": "Butun Qur'onni yodladi (6236 oyat)",
        "bonus_xp": 50000,
        "condition": lambda u, s: _total_verses(u) >= 6236,
    },
    # ── Surah completions ─────────────────────────────────────────────────────
    {
        "id": "first_surah",
        "emoji": "✅",
        "title": "Birinchi Sura",
        "desc": "Birinchi surani to'liq yodladi",
        "bonus_xp": 200,
        "condition": lambda u, s: len(_completed_surahs(u)) >= 1,
    },
    {
        "id": "surahs_5",
        "emoji": "📜",
        "title": "5 Sura",
        "desc": "5 ta surani to'liq yodladi",
        "bonus_xp": 500,
        "condition": lambda u, s: len(_completed_surahs(u)) >= 5,
    },
    {
        "id": "surahs_10",
        "emoji": "📚",
        "title": "10 Sura",
        "desc": "10 ta surani to'liq yodladi",
        "bonus_xp": 1500,
        "condition": lambda u, s: len(_completed_surahs(u)) >= 10,
    },
    {
        "id": "surahs_20",
        "emoji": "🏛",
        "title": "20 Sura",
        "desc": "20 ta surani to'liq yodladi",
        "bonus_xp": 5000,
        "condition": lambda u, s: len(_completed_surahs(u)) >= 20,
    },
    # ── Juz completions ───────────────────────────────────────────────────────
    {
        "id": "first_juz",
        "emoji": "🔖",
        "title": "Birinchi Juz",
        "desc": "Birinchi juzni to'liq yodladi",
        "bonus_xp": 1000,
        "condition": lambda u, s: len(_completed_juz(u)) >= 1,
    },
    {
        "id": "juz_5",
        "emoji": "🔱",
        "title": "5 Juz",
        "desc": "5 ta juzni to'liq yodladi",
        "bonus_xp": 3000,
        "condition": lambda u, s: len(_completed_juz(u)) >= 5,
    },
    {
        "id": "juz_15",
        "emoji": "💫",
        "title": "15 Juz — Nisf Qur'on",
        "desc": "15 ta juzni yodladi — yarim Qur'on!",
        "bonus_xp": 10000,
        "condition": lambda u, s: len(_completed_juz(u)) >= 15,
    },
    {
        "id": "juz_30",
        "emoji": "🌟",
        "title": "30 Juz — Xatm",
        "desc": "30 juzni to'liq yodladi — Xatm!",
        "bonus_xp": 30000,
        "condition": lambda u, s: len(_completed_juz(u)) >= 30,
    },
    # ── Streak ────────────────────────────────────────────────────────────────
    {
        "id": "streak_3",
        "emoji": "🔥",
        "title": "3 Kunlik Olov",
        "desc": "3 kun ketma-ket yodladi",
        "bonus_xp": 50,
        "condition": lambda u, s: _streak(u) >= 3,
    },
    {
        "id": "streak_7",
        "emoji": "🔥",
        "title": "Haftalik Chempion",
        "desc": "7 kun ketma-ket yodladi",
        "bonus_xp": 150,
        "condition": lambda u, s: _streak(u) >= 7,
    },
    {
        "id": "streak_14",
        "emoji": "💪",
        "title": "Ikki Hafta",
        "desc": "14 kun ketma-ket yodladi",
        "bonus_xp": 400,
        "condition": lambda u, s: _streak(u) >= 14,
    },
    {
        "id": "streak_30",
        "emoji": "🏆",
        "title": "Bir Oylik Jasorat",
        "desc": "30 kun ketma-ket yodladi",
        "bonus_xp": 1000,
        "condition": lambda u, s: _streak(u) >= 30,
    },
    {
        "id": "streak_100",
        "emoji": "👑",
        "title": "100 Kunlik Sobitqadam",
        "desc": "100 kun ketma-ket yodladi",
        "bonus_xp": 5000,
        "condition": lambda u, s: _streak(u) >= 100,
    },
    # ── Himmat balls (XP) ─────────────────────────────────────────────────────
    {
        "id": "xp_500",
        "emoji": "💡",
        "title": "500 Himmat",
        "desc": "500 Himmat ball to'pladi",
        "bonus_xp": 0,
        "condition": lambda u, s: _himmat(u) >= 500,
    },
    {
        "id": "xp_2000",
        "emoji": "💎",
        "title": "2000 Himmat",
        "desc": "2000 Himmat ball to'pladi",
        "bonus_xp": 0,
        "condition": lambda u, s: _himmat(u) >= 2000,
    },
    {
        "id": "xp_5000",
        "emoji": "👑",
        "title": "5000 Himmat — Oltin",
        "desc": "5000 Himmat ball to'pladi",
        "bonus_xp": 0,
        "condition": lambda u, s: _himmat(u) >= 5000,
    },
    {
        "id": "xp_10000",
        "emoji": "🌟",
        "title": "10000 Himmat",
        "desc": "10000 Himmat ball to'pladi",
        "bonus_xp": 0,
        "condition": lambda u, s: _himmat(u) >= 10000,
    },
    # ── Repetitions ───────────────────────────────────────────────────────────
    {
        "id": "reps_100",
        "emoji": "🔄",
        "title": "100 Takror",
        "desc": "100 ta takror bajarildi",
        "bonus_xp": 100,
        "condition": lambda u, s: _total_reps(u) >= 100,
    },
    {
        "id": "reps_1000",
        "emoji": "🔄",
        "title": "1000 Takror",
        "desc": "1000 ta takror bajarildi",
        "bonus_xp": 500,
        "condition": lambda u, s: _total_reps(u) >= 1000,
    },
    {
        "id": "reps_10000",
        "emoji": "🔄",
        "title": "10000 Takror — Ustoz",
        "desc": "10000 ta takror bajarildi",
        "bonus_xp": 3000,
        "condition": lambda u, s: _total_reps(u) >= 10000,
    },
    # ── Time ──────────────────────────────────────────────────────────────────
    {
        "id": "time_1h",
        "emoji": "⏱",
        "title": "1 Soat Yodlash",
        "desc": "Jami 1 soat yodladi",
        "bonus_xp": 50,
        "condition": lambda u, s: _total_minutes(u) >= 60,
    },
    {
        "id": "time_10h",
        "emoji": "⏱",
        "title": "10 Soat Yodlash",
        "desc": "Jami 10 soat yodladi",
        "bonus_xp": 300,
        "condition": lambda u, s: _total_minutes(u) >= 600,
    },
    {
        "id": "time_100h",
        "emoji": "⌛",
        "title": "100 Soat — Mutaxassis",
        "desc": "Jami 100 soat yodladi",
        "bonus_xp": 2000,
        "condition": lambda u, s: _total_minutes(u) >= 6000,
    },
    # ── Social / Referral ─────────────────────────────────────────────────────
    {
        "id": "referral_1",
        "emoji": "🤝",
        "title": "Birinchi Do'st",
        "desc": "1 ta do'stni taklif qildi",
        "bonus_xp": 100,
        "condition": lambda u, s: u.get("referral_count", 0) >= 1,
    },
    {
        "id": "referral_5",
        "emoji": "👥",
        "title": "5 Do'st",
        "desc": "5 ta do'stni taklif qildi",
        "bonus_xp": 500,
        "condition": lambda u, s: u.get("referral_count", 0) >= 5,
    },
    {
        "id": "referral_10",
        "emoji": "🌐",
        "title": "10 Do'st — Da'vat Elchisi",
        "desc": "10 ta do'stni taklif qildi",
        "bonus_xp": 2000,
        "condition": lambda u, s: u.get("referral_count", 0) >= 10,
    },
    # ── Xatm ─────────────────────────────────────────────────────────────────
    {
        "id": "xatm_joined",
        "emoji": "👥",
        "title": "Jamoaviy Xatm",
        "desc": "Jamoaviy xatmga birinchi marta qo'shildi",
        "bonus_xp": 200,
        "condition": lambda u, s: s.get("xatm_joined", False),
    },
    {
        "id": "xatm_completed",
        "emoji": "🎊",
        "title": "Xatm Yakunlandi",
        "desc": "Jamoaviy xatmni muvaffaqiyatli yakunladi",
        "bonus_xp": 1000,
        "condition": lambda u, s: s.get("xatm_completed", False),
    },
    # ── Premium ───────────────────────────────────────────────────────────────
    {
        "id": "premium_user",
        "emoji": "💎",
        "title": "Premium A'zo",
        "desc": "Premium obunani faollashtirdi",
        "bonus_xp": 300,
        "condition": lambda u, s: u.get("premium", {}).get("is_active", False),
    },
]

# Build a lookup dict
ACHIEVEMENT_MAP = {a["id"]: a for a in ACHIEVEMENTS}


# ─── Helper field extractors ───────────────────────────────────────────────────

def _total_verses(u: dict) -> int:
    return u.get("stats", {}).get("total_verses_read", 0)

def _total_reps(u: dict) -> int:
    return u.get("stats", {}).get("total_repetitions", 0)

def _total_minutes(u: dict) -> int:
    return u.get("stats", {}).get("total_minutes", 0)

def _himmat(u: dict) -> int:
    return u.get("stats", {}).get("himmat_points", 0)

def _streak(u: dict) -> int:
    return u.get("stats", {}).get("current_streak_days", 0)

def _completed_surahs(u: dict) -> list:
    return u.get("memorization_progress", {}).get("completed_surahs", [])

def _completed_juz(u: dict) -> list:
    return u.get("memorization_progress", {}).get("completed_juz", [])


# ─── Firebase helpers ──────────────────────────────────────────────────────────

def get_user_achievements(user_id: int) -> dict:
    """Returns {achievement_id: {"unlocked_at": ..., "notified": bool}}."""
    from firebase_config import db
    if not db:
        return {}
    try:
        docs = db.collection("users").document(str(user_id)).collection("achievements").stream()
        return {doc.id: doc.to_dict() for doc in docs}
    except Exception as e:
        logger.error(f"get_user_achievements error: {e}")
        return {}


def save_achievement(user_id: int, achievement_id: str):
    """Mark an achievement as unlocked in Firebase."""
    from firebase_config import db
    if not db:
        return
    try:
        db.collection("users").document(str(user_id)).collection("achievements") \
            .document(achievement_id).set({
                "unlocked_at": datetime.now(TZ),
                "notified": False,
            })
    except Exception as e:
        logger.error(f"save_achievement error: {e}")


def mark_achievement_notified(user_id: int, achievement_id: str):
    """Mark achievement broadcast as sent."""
    from firebase_config import db
    if not db:
        return
    try:
        db.collection("users").document(str(user_id)).collection("achievements") \
            .document(achievement_id).update({"notified": True})
    except Exception as e:
        logger.error(f"mark_achievement_notified error: {e}")


# ─── Core: check and unlock achievements ──────────────────────────────────────

def check_new_achievements(user_id: int, extra_signals: dict = None) -> list:
    """
    Check all achievements for this user and unlock any that are newly met.
    Returns list of newly unlocked achievement dicts.
    extra_signals: optional dict with flags like {"xatm_joined": True}
    """
    from services.firebase_service import get_user
    user = get_user(user_id)
    if not user:
        return []

    extra_signals = extra_signals or {}
    already_unlocked = get_user_achievements(user_id)
    newly_unlocked = []

    for ach in ACHIEVEMENTS:
        aid = ach["id"]
        if aid in already_unlocked:
            continue  # Already earned
        try:
            if ach["condition"](user, extra_signals):
                save_achievement(user_id, aid)
                # Award bonus XP
                if ach["bonus_xp"] > 0:
                    from services.gamification import award_points
                    award_points(user_id, ach["bonus_xp"], f"achievement_{aid}")
                newly_unlocked.append(ach)
                logger.info(f"User {user_id} unlocked achievement: {aid}")
        except Exception as e:
            logger.error(f"check achievement {aid} error: {e}")

    return newly_unlocked


# ─── Broadcast new achievements to all users ──────────────────────────────────

async def broadcast_achievement(bot, achiever_id: int, achiever_name: str, achievement: dict):
    """Send achievement notification to all other users."""
    from services.firebase_service import get_all_users
    try:
        all_users = get_all_users()
    except Exception as e:
        logger.error(f"broadcast_achievement get_all_users error: {e}")
        return

    ach_id     = achievement["id"]
    ach_emoji  = achievement["emoji"]
    ach_title  = achievement["title"]
    ach_desc   = achievement["desc"]
    bonus_xp   = achievement["bonus_xp"]

    xp_line = f"\n⭐ Bonus: +{bonus_xp} Himmat" if bonus_xp > 0 else ""

    text = (
        f"🏆 YANGI YUTUQ!\n\n"
        f"{ach_emoji} {ach_title}\n"
        f"📌 {ach_desc}\n"
        f"{xp_line}\n\n"
        f"👤 {achiever_name} ushbu yutuqqa erishdi!\n\n"
        f"💬 Uni tabriklaymizmi?"
    )

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "🤝 Tabriklash",
            callback_data=f"congrats_{achiever_id}_{ach_id}"
        )
    ]])

    sent = 0
    failed = 0
    for u in all_users:
        uid = u.get("telegram_id")
        if not uid or uid == achiever_id:
            continue
        try:
            await bot.send_message(
                chat_id=uid,
                text=text,
                reply_markup=keyboard,
            )
            sent += 1
        except Exception:
            failed += 1

    logger.info(f"Achievement broadcast for {achiever_id}/{ach_id}: sent={sent}, failed={failed}")
    mark_achievement_notified(achiever_id, ach_id)


# ─── Handle Tabriklash button ─────────────────────────────────────────────────

async def cb_congrats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User tapped 'Tabriklash' button for someone's achievement."""
    query = update.callback_query
    await query.answer("🎆 Tabrik yuborildi!", show_alert=False)

    # Parse callback_data: "congrats_{achiever_id}_{ach_id}"
    parts = query.data.split("_", 2)
    if len(parts) < 3:
        return

    _, achiever_id_str, ach_id = parts
    try:
        achiever_id = int(achiever_id_str)
    except ValueError:
        return

    congratulator_name = query.from_user.first_name or "Bir do'st"
    if query.from_user.last_name:
        congratulator_name += f" {query.from_user.last_name}"

    ach = ACHIEVEMENT_MAP.get(ach_id)
    ach_title = f"{ach['emoji']} {ach['title']}" if ach else "yutuq"

    notify_text = (
        f"🎆🎇🎉\n\n"
        f"<b>{congratulator_name}</b> Sizni <b>{ach_title}</b> yutug'ingiz bilan tabrikladi!\n\n"
        f"Yutuqlaringizni ALLOH ziyoda qilsin!\n"
        f"Ko'tarilishda Davom eting 💪🌙"
    )

    try:
        await context.bot.send_message(
            chat_id=achiever_id,
            text=notify_text,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not notify achiever {achiever_id}: {e}")

    # Edit the button to show it was tapped
    try:
        new_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Tabrikladingiz!", callback_data="congrats_done")
        ]])
        await query.message.edit_reply_markup(reply_markup=new_kb)
    except Exception:
        pass


async def cb_congrats_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Alloh qabul qilsin! 🤲", show_alert=True)


# ─── Show user's achievements page ────────────────────────────────────────────

async def show_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's achievements page from Sahifam."""
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
        send = query.message.reply_text
    else:
        user_id = update.effective_user.id
        send = update.message.reply_text

    unlocked = get_user_achievements(user_id)
    total = len(ACHIEVEMENTS)
    done  = len(unlocked)

    lines = [
        "🏆 YUTUQ VA MUKOFOTLARIM",
        f"──────────────────────",
        f"✅ Erishilgan: {done}/{total}",
        f"──────────────────────",
        "",
    ]

    # Group by category
    categories = [
        ("📖 Oyat Yodlash",  ["first_ayah","verses_10","verses_50","verses_100","verses_300","verses_500","verses_1000","verses_3000","full_quran"]),
        ("📜 Surahlar",       ["first_surah","surahs_5","surahs_10","surahs_20"]),
        ("🔖 Juzlar",         ["first_juz","juz_5","juz_15","juz_30"]),
        ("🔥 Streak",         ["streak_3","streak_7","streak_14","streak_30","streak_100"]),
        ("💫 Himmat Ball",    ["xp_500","xp_2000","xp_5000","xp_10000"]),
        ("🔄 Takrorlar",      ["reps_100","reps_1000","reps_10000"]),
        ("⏱ Vaqt",           ["time_1h","time_10h","time_100h"]),
        ("👥 Ijtimoiy",       ["referral_1","referral_5","referral_10"]),
        ("🕌 Jamoaviy Xatm", ["xatm_joined","xatm_completed"]),
        ("💎 Premium",        ["premium_user"]),
    ]

    for cat_name, ids in categories:
        cat_unlocked = sum(1 for i in ids if i in unlocked)
        cat_total    = len(ids)
        lines.append(f"{cat_name} ({cat_unlocked}/{cat_total})")
        for aid in ids:
            ach = ACHIEVEMENT_MAP.get(aid)
            if not ach:
                continue
            if aid in unlocked:
                unlocked_at = unlocked[aid].get("unlocked_at")
                if hasattr(unlocked_at, "strftime"):
                    date_str = unlocked_at.strftime("%d.%m.%Y")
                elif hasattr(unlocked_at, "isoformat"):
                    # Firestore Timestamp
                    try:
                        date_str = unlocked_at.astimezone(TZ).strftime("%d.%m.%Y")
                    except Exception:
                        date_str = "—"
                else:
                    date_str = "—"
                bonus = f" +{ach['bonus_xp']} XP" if ach["bonus_xp"] > 0 else ""
                lines.append(f"  ✅ {ach['emoji']} {ach['title']}{bonus} ({date_str})")
            else:
                lines.append(f"  🔒 {ach['emoji']} {ach['title']} — {ach['desc']}")
        lines.append("")

    text = "\n".join(lines)

    # Back button
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("↩️ Sahifamga qaytish", callback_data="profile_back")
    ]])

    try:
        if query:
            await query.message.edit_text(text, reply_markup=keyboard)
        else:
            await send(text, reply_markup=keyboard)
    except Exception:
        if query:
            await query.message.reply_text(text, reply_markup=keyboard)
        else:
            await send(text, reply_markup=keyboard)


# ─── Check + notify after any activity ────────────────────────────────────────

async def check_and_notify_achievements(bot, user_id: int, extra_signals: dict = None):
    """
    Call this after any activity (ayah completed, surah done, etc.)
    It checks for newly unlocked achievements and:
      1. Notifies the user directly
      2. Broadcasts to all other users
    """
    from services.firebase_service import get_user
    newly_unlocked = check_new_achievements(user_id, extra_signals)
    if not newly_unlocked:
        return

    user = get_user(user_id)
    full_name = (user.get("full_name") or "Foydalanuvchi") if user else "Foydalanuvchi"

    for ach in newly_unlocked:
        bonus_line = f"\n⭐ +{ach['bonus_xp']} Himmat ball!" if ach["bonus_xp"] > 0 else ""
        try:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    f"🏆 YANGI YUTUQ OLINDI!\n\n"
                    f"{ach['emoji']} <b>{ach['title']}</b>\n"
                    f"📌 {ach['desc']}"
                    f"{bonus_line}\n\n"
                    f"Alloh taolo baraka bersin! 🤲"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Could not notify user {user_id} of achievement: {e}")

        # Broadcast to others
        try:
            await broadcast_achievement(bot, user_id, full_name, ach)
        except Exception as e:
            logger.error(f"broadcast_achievement error for {user_id}/{ach['id']}: {e}")


# ─── Register handlers ────────────────────────────────────────────────────────

def register_achievement_handlers(app):
    app.add_handler(CallbackQueryHandler(show_achievements,  pattern="^achievements_show$"))
    app.add_handler(CallbackQueryHandler(cb_congrats,        pattern="^congrats_\\d+_"))
    app.add_handler(CallbackQueryHandler(cb_congrats_done,   pattern="^congrats_done$"))
    app.add_handler(CallbackQueryHandler(
        lambda u, c: show_achievements(u, c),
        pattern="^profile_back$"
    ))
