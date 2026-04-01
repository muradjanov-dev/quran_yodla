"""
achievements.py — Yutuq va Mukofotlar (Achievements & Rewards) system.

Achievements are stored in Firebase under users/{uid}/achievements/{achievement_id}
as { "unlocked_at": <timestamp>, "notified": bool, "congrats_count": int }.

Broadcast queue:
  - When an achievement is unlocked, queue items are created in
    `achievement_broadcast_queue` collection (one doc per recipient).
  - `flush_congrats_queue(bot)` is called every 30 minutes by APScheduler.
    It sends max 10 pending notifications per user per day, skipping users
    who are actively memorizing.
  - Congrats count is tracked per achievement and shown on the button.
"""

import logging
from datetime import datetime
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from config import LOCAL_TZ

logger = logging.getLogger(__name__)
TZ = pytz.timezone(LOCAL_TZ)

# ─── Achievement Definitions ──────────────────────────────────────────────────

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

ACHIEVEMENT_MAP = {a["id"]: a for a in ACHIEVEMENTS}

MAX_NOTIFS_PER_DAY = 10


# ─── Helper field extractors ───────────────────────────────────────────────────

def _total_verses(u): return u.get("stats", {}).get("total_verses_read", 0)
def _total_reps(u):   return u.get("stats", {}).get("total_repetitions", 0)
def _total_minutes(u): return u.get("stats", {}).get("total_minutes", 0)
def _himmat(u):        return u.get("stats", {}).get("himmat_points", 0)
def _streak(u):        return u.get("stats", {}).get("current_streak_days", 0)
def _completed_surahs(u): return u.get("memorization_progress", {}).get("completed_surahs", [])
def _completed_juz(u):    return u.get("memorization_progress", {}).get("completed_juz", [])


# ─── Firebase helpers ──────────────────────────────────────────────────────────

def get_user_achievements(user_id: int) -> dict:
    """Returns {achievement_id: {"unlocked_at": ..., "notified": bool, "congrats_count": int}}."""
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
    from firebase_config import db
    if not db:
        return
    try:
        db.collection("users").document(str(user_id)).collection("achievements") \
            .document(achievement_id).set({
                "unlocked_at": datetime.now(TZ),
                "notified": False,
                "congrats_count": 0,
            })
    except Exception as e:
        logger.error(f"save_achievement error: {e}")


def mark_achievement_notified(user_id: int, achievement_id: str):
    from firebase_config import db
    if not db:
        return
    try:
        db.collection("users").document(str(user_id)).collection("achievements") \
            .document(achievement_id).update({"notified": True})
    except Exception as e:
        logger.error(f"mark_achievement_notified error: {e}")


def increment_congrats_count(achiever_id: int, ach_id: str) -> int:
    """Atomically increment congrats_count and return the new value."""
    from firebase_config import db
    from google.cloud.firestore_v1 import Increment
    if not db:
        return 0
    try:
        ref = db.collection("users").document(str(achiever_id)) \
                .collection("achievements").document(ach_id)
        ref.update({"congrats_count": Increment(1)})
        doc = ref.get()
        return doc.to_dict().get("congrats_count", 1) if doc.exists else 1
    except Exception as e:
        logger.error(f"increment_congrats_count error: {e}")
        return 0


def get_congrats_count(achiever_id: int, ach_id: str) -> int:
    from firebase_config import db
    if not db:
        return 0
    try:
        doc = db.collection("users").document(str(achiever_id)) \
                .collection("achievements").document(ach_id).get()
        return doc.to_dict().get("congrats_count", 0) if doc.exists else 0
    except Exception:
        return 0


# ─── Broadcast queue helpers ───────────────────────────────────────────────────

def queue_achievement_broadcast(achiever_id: int, achiever_name: str, achievement: dict, recipients: list):
    """
    Add one queue doc per recipient into `achievement_broadcast_queue`.
    Each doc: {recipient_id, achiever_id, achiever_name, ach_id, created_at, sent: false}
    """
    from firebase_config import db
    if not db:
        return
    coll = db.collection("achievement_broadcast_queue")
    batch = db.batch()
    ach_id = achievement["id"]
    now = datetime.now(TZ)
    for uid in recipients:
        doc_ref = coll.document()
        batch.set(doc_ref, {
            "recipient_id":  uid,
            "achiever_id":   achiever_id,
            "achiever_name": achiever_name,
            "ach_id":        ach_id,
            "created_at":    now,
            "sent":          False,
        })
    try:
        batch.commit()
        logger.info(f"Queued {len(recipients)} broadcast items for {achiever_id}/{ach_id}")
    except Exception as e:
        logger.error(f"queue_achievement_broadcast batch error: {e}")


def _get_daily_sent_count(user_id: int, today_str: str) -> int:
    from firebase_config import db
    if not db:
        return 0
    try:
        doc = db.collection("achievement_queue_daily").document(f"{user_id}_{today_str}").get()
        return doc.to_dict().get("count", 0) if doc.exists else 0
    except Exception:
        return 0


def _increment_daily_sent(user_id: int, today_str: str):
    from firebase_config import db
    from google.cloud.firestore_v1 import Increment
    if not db:
        return
    try:
        db.collection("achievement_queue_daily").document(f"{user_id}_{today_str}") \
            .set({"count": Increment(1)}, merge=True)
    except Exception as e:
        logger.error(f"_increment_daily_sent error: {e}")


# ─── Core: check and unlock achievements ──────────────────────────────────────

def check_new_achievements(user_id: int, extra_signals: dict = None) -> list:
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
            continue
        try:
            if ach["condition"](user, extra_signals):
                save_achievement(user_id, aid)
                if ach["bonus_xp"] > 0:
                    from services.gamification import award_points
                    award_points(user_id, ach["bonus_xp"], f"achievement_{aid}")
                newly_unlocked.append(ach)
                logger.info(f"User {user_id} unlocked achievement: {aid}")
        except Exception as e:
            logger.error(f"check achievement {aid} error: {e}")

    return newly_unlocked


# ─── Flush queue: send pending broadcast notifications ────────────────────────

async def flush_congrats_queue(bot):
    """
    Called every 30 minutes by APScheduler.
    For each user: send up to MAX_NOTIFS_PER_DAY pending notifications,
    skipping users who are actively memorizing.
    """
    from firebase_config import db
    from services.firebase_service import get_active_session
    if not db:
        return

    today_str = datetime.now(TZ).strftime("%Y-%m-%d")

    try:
        pending_docs = db.collection("achievement_broadcast_queue") \
            .where("sent", "==", False) \
            .order_by("created_at") \
            .limit(2000) \
            .stream()
        pending = [(doc.id, doc.to_dict()) for doc in pending_docs]
    except Exception as e:
        logger.error(f"flush_congrats_queue fetch error: {e}")
        return

    # Group by recipient
    by_recipient: dict[int, list] = {}
    for doc_id, data in pending:
        rid = data.get("recipient_id")
        if rid:
            by_recipient.setdefault(rid, []).append((doc_id, data))

    sent_total = 0
    skipped_memorizing = 0

    for recipient_id, items in by_recipient.items():
        # Skip users who are currently memorizing
        try:
            active_session = get_active_session(recipient_id)
            if active_session:
                skipped_memorizing += 1
                continue
        except Exception:
            pass

        daily_sent = _get_daily_sent_count(recipient_id, today_str)
        remaining = MAX_NOTIFS_PER_DAY - daily_sent
        if remaining <= 0:
            continue

        to_send = items[:remaining]

        for doc_id, data in to_send:
            ach_id        = data.get("ach_id", "")
            achiever_id   = data.get("achiever_id")
            achiever_name = data.get("achiever_name", "Foydalanuvchi")
            ach           = ACHIEVEMENT_MAP.get(ach_id)
            if not ach:
                # Mark sent to clean up unknown items
                db.collection("achievement_broadcast_queue").document(doc_id).update({"sent": True})
                continue

            congrats_count = get_congrats_count(achiever_id, ach_id)
            count_label    = f" ({congrats_count})" if congrats_count > 0 else ""

            xp_line = f"\n⭐ Bonus: +{ach['bonus_xp']} Himmat" if ach["bonus_xp"] > 0 else ""
            text = (
                f"🏆 YANGI YUTUQ!\n\n"
                f"{ach['emoji']} {ach['title']}\n"
                f"📌 {ach['desc']}"
                f"{xp_line}\n\n"
                f"👤 {achiever_name} ushbu yutuqqa erishdi!\n\n"
                f"💬 Uni tabriklaymizmi?"
            )
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    f"🤝 Tabriklash{count_label}",
                    callback_data=f"congrats_{achiever_id}_{ach_id}"
                )
            ]])

            try:
                await bot.send_message(
                    chat_id=recipient_id,
                    text=text,
                    reply_markup=keyboard,
                )
                db.collection("achievement_broadcast_queue").document(doc_id).update({"sent": True})
                _increment_daily_sent(recipient_id, today_str)
                sent_total += 1
            except Exception as e:
                logger.warning(f"flush_congrats_queue send to {recipient_id} failed: {e}")

    logger.info(f"flush_congrats_queue: sent={sent_total}, skipped_memorizing={skipped_memorizing}")


# ─── Queue broadcast for all users ────────────────────────────────────────────

def broadcast_achievement(achiever_id: int, achiever_name: str, achievement: dict):
    """
    Queue achievement notification for all other users.
    (Not async — just writes to Firestore queue. flush_congrats_queue delivers them.)
    """
    from services.firebase_service import get_all_users
    try:
        all_users = get_all_users()
        recipients = [
            u["telegram_id"] for u in all_users
            if u.get("telegram_id") and u["telegram_id"] != achiever_id
        ]
        queue_achievement_broadcast(achiever_id, achiever_name, achievement, recipients)
        mark_achievement_notified(achiever_id, achievement["id"])
    except Exception as e:
        logger.error(f"broadcast_achievement error for {achiever_id}/{achievement['id']}: {e}")


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

    # Increment congrats count and get new value
    new_count = increment_congrats_count(achiever_id, ach_id)

    # Notify achiever
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

    # Edit the button: show updated congrats count
    try:
        new_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                f"✅ Tabrikladingiz! ({new_count})",
                callback_data="congrats_done"
            )
        ]])
        await query.message.edit_reply_markup(reply_markup=new_kb)
    except Exception:
        pass


async def cb_congrats_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Alloh qabul qilsin! 🤲", show_alert=True)


# ─── Show user's achievements page ────────────────────────────────────────────

async def show_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                else:
                    try:
                        date_str = unlocked_at.astimezone(TZ).strftime("%d.%m.%Y")
                    except Exception:
                        date_str = "—"
                bonus = f" +{ach['bonus_xp']} XP" if ach["bonus_xp"] > 0 else ""
                congrats = unlocked[aid].get("congrats_count", 0)
                congrats_str = f" 🤝{congrats}" if congrats > 0 else ""
                lines.append(f"  ✅ {ach['emoji']} {ach['title']}{bonus}{congrats_str} ({date_str})")
            else:
                lines.append(f"  🔒 {ach['emoji']} {ach['title']} — {ach['desc']}")
        lines.append("")

    text = "\n".join(lines)

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
    Call this after any activity. Checks for newly unlocked achievements,
    notifies the user directly, and queues broadcast to all other users.
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

        # Queue broadcast (non-async, just Firestore writes)
        try:
            broadcast_achievement(user_id, full_name, ach)
        except Exception as e:
            logger.error(f"broadcast_achievement error for {user_id}/{ach['id']}: {e}")


# ─── Register handlers ────────────────────────────────────────────────────────

def register_achievement_handlers(app):
    app.add_handler(CallbackQueryHandler(show_achievements,  pattern="^achievements_show$"))
    app.add_handler(CallbackQueryHandler(cb_congrats,        pattern="^congrats_\\d+_"))
    app.add_handler(CallbackQueryHandler(cb_congrats_done,   pattern="^congrats_done$"))
    app.add_handler(CallbackQueryHandler(show_achievements, pattern="^profile_back$"))
