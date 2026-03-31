"""Free-tier limit guard — checks usage and shows upgrade prompt."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.database import db
from src.i18n import t

def _upgrade_keyboard(user_id: int) -> InlineKeyboardMarkup:
    lang = "en"
    u = db.get_user(user_id)
    if u:
        lang = u["language"]
    btn_label = "💎 Go Premium" if lang == "en" else "💎 Premiumga o'tish"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_label, callback_data="menu:premium")],
        [InlineKeyboardButton(t(user_id, "btn_main_menu"), callback_data="menu:learn")],
    ])

def _limit_msg(user_id: int, feature: str, limit: int) -> str:
    u = db.get_user(user_id)
    lang = u["language"] if u else "en"
    if lang == "uz":
        msgs = {
            "quiz": (f"🔒 *Bepul Test limiti:* Kuniga {limit} ta savol.\n\n"
                     "💎 *Premium*: cheksiz testlar + ko'proq imkoniyatlar.\n"
                     "_17 000 so'm/oy — /premium_"),
            "flow": (f"🔒 *Bepul Oqim limiti:* Kuniga {limit} ta oyat.\n\n"
                     "💎 *Premium*: cheksiz oqim o'rganish.\n"
                     "_17 000 so'm/oy — /premium_"),
            "reminder": (f"🔒 *Bepul eslatma limiti:* {limit} ta.\n\n"
                         "💎 *Premium*: 10 tagacha eslatma.\n"
                         "_17 000 so'm/oy — /premium_"),
            "leaderboard": (f"🔒 *Bepul reyting:* Top {limit} ta.\n\n"
                            "💎 *Premium*: to'liq reyting.\n"
                            "_17 000 so'm/oy — /premium_"),
        }
    else:
        msgs = {
            "quiz": (f"🔒 *Free Quiz limit:* {limit} questions/day.\n\n"
                     "💎 *Premium*: Unlimited quizzes + more features.\n"
                     "_17,000 so'm/mo — /premium_"),
            "flow": (f"🔒 *Free Flow limit:* {limit} Ayahs/day.\n\n"
                     "💎 *Premium*: Unlimited Flow Learning.\n"
                     "_17,000 so'm/mo — /premium_"),
            "reminder": (f"🔒 *Free reminder limit:* {limit} times.\n\n"
                         "💎 *Premium*: Up to 10 reminders.\n"
                         "_17,000 so'm/mo — /premium_"),
            "leaderboard": (f"🔒 *Free leaderboard:* Top {limit} only.\n\n"
                            "💎 *Premium*: Full standings.\n"
                            "_17,000 so'm/mo — /premium_"),
        }
    return msgs.get(feature, "🔒 This feature requires Premium.")

async def check_quiz_limit(update_or_query, user_id: int) -> bool:
    """Returns True if user can proceed, False if limit hit (sends message)."""
    if db.is_premium(user_id):
        return True
    used = db.get_quiz_daily_count(user_id)
    if used >= db.FREE_QUIZ_DAILY:
        msg = _limit_msg(user_id, "quiz", db.FREE_QUIZ_DAILY)
        kbd = _upgrade_keyboard(user_id)
        try:
            await update_or_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kbd)
        except Exception:
            try:
                await update_or_query.message.reply_text(msg, parse_mode="Markdown", reply_markup=kbd)
            except Exception:
                await update_or_query.reply_text(msg, parse_mode="Markdown", reply_markup=kbd)
        return False
    return True

async def check_flow_limit(update_or_query, user_id: int) -> bool:
    """Returns True if user can proceed, False if limit hit."""
    if db.is_premium(user_id):
        return True
    used = db.get_flow_daily_count(user_id)
    if used >= db.FREE_FLOW_DAILY:
        msg = _limit_msg(user_id, "flow", db.FREE_FLOW_DAILY)
        kbd = _upgrade_keyboard(user_id)
        try:
            await update_or_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kbd)
        except Exception:
            try:
                await update_or_query.message.reply_text(msg, parse_mode="Markdown", reply_markup=kbd)
            except Exception:
                await update_or_query.reply_text(msg, parse_mode="Markdown", reply_markup=kbd)
        return False
    return True

async def check_reciter_change(update_or_query, user_id: int) -> bool:
    """Returns True if user can change reciter (premium only), False otherwise."""
    if db.is_premium(user_id):
        return True
    u = db.get_user(user_id)
    lang = u["language"] if u else "en"
    if lang == "uz":
        msg = (
            "🔒 *Qori tanlash — Premium xususiyat*\n\n"
            "Barcha foydalanuvchilar uchun standart qori:\n"
            "🎙 *Halil Husary (Muallim)*\n\n"
            "💎 *Premium*: 6 ta qori ichidan tanlash imkoniyati.\n"
            "_17 000 so'm/oy — /premium_"
        )
    else:
        msg = (
            "🔒 *Reciter change — Premium feature*\n\n"
            "Default reciter for all users:\n"
            "🎙 *Halil Husary (Muallim)*\n\n"
            "💎 *Premium*: Choose from 6 reciters.\n"
            "_17,000 so'm/mo — /premium_"
        )
    kbd = _upgrade_keyboard(user_id)
    try:
        await update_or_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kbd)
    except Exception:
        try:
            await update_or_query.message.reply_text(msg, parse_mode="Markdown", reply_markup=kbd)
        except Exception:
            await update_or_query.reply_text(msg, parse_mode="Markdown", reply_markup=kbd)
    return False

def reminder_limit(user_id: int) -> int:
    return 10 if db.is_premium(user_id) else db.FREE_REMINDERS

def leaderboard_limit(user_id: int) -> int:
    return 50 if db.is_premium(user_id) else db.FREE_LB_ROWS
