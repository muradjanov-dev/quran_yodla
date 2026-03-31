"""Onboarding: /start with project intro + live stats, language picker, main menu."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from src.database import db
from src.i18n import t
from src.i18n.en import STRINGS as EN

ADMIN_ID = db.ADMIN_ID

def main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Shared main menu keyboard used across all handlers."""
    prem = db.is_premium(user_id)
    gem  = "💎 " if prem else ""
    lang = db.get_user(user_id)
    lang = lang["language"] if lang else "en"
    surah_num  = db.get_active_surah(user_id)
    surah_label = f"📖 Sura #{surah_num}" if lang == "uz" else f"📖 Surah #{surah_num}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(surah_label, callback_data="flow:dashboard")],
        [InlineKeyboardButton(t(user_id, "btn_group_xatm"), callback_data="menu:group_xatm")],
        [
            InlineKeyboardButton(t(user_id, "btn_quiz"),            callback_data="menu:quiz"),
            InlineKeyboardButton(t(user_id, "btn_profile_short"),   callback_data="menu:profile"),
        ],
        [
            InlineKeyboardButton(t(user_id, "btn_leaderboard_short"), callback_data="menu:leaderboard"),
            InlineKeyboardButton(t(user_id, "btn_settings_short"),    callback_data="menu:settings"),
        ],
        [InlineKeyboardButton(f"{gem}💎 Premium", callback_data="menu:premium")],
    ])

def _build_intro_text(user_id: int) -> str:
    total_users = db.get_total_users()
    total_memorized = db.get_total_memorized()
    active_today = db.get_active_today()
    user = db.get_user(user_id)
    lang = user["language"] if user else "en"

    if lang == "uz":
        return (
            "🕌 *Hifz Bot — Qur'on Yod Olish Hamrohi*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Bu bot sizga Qur'onni tizimli va qiziqarli usulda yod olishga yordam beradi:\n\n"
            "📚 *Qur'on Navigatori* — Istalgan suradan boshlang\n"
            "🔥 *Oqim Rejimi* — To'xtovsiz chuqur yod olish (3x tezroq) (3×→7×→13×→ovoz)\n"
            "🧠 *Test* — 3 xil o'yin bilan bilimingizni sinang\n"
            "⏰ *Eslatmalar* — Kunlik maqsad va avtomatik eslatmalar\n"
            "🏆 *Liga tizimi* — Bronza→Kumush→Oltin→Olmos\n"
            "💎 *Premium* — Cheksiz imkoniyatlar (17 000 so'm/oy)\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Jamoatchilik statistikasi:*\n"
            f"👥 Jami foydalanuvchilar: *{total_users:,}*\n"
            f"📖 Jami yod olingan oyatlar: *{total_memorized:,}*\n"
            f"🟢 Bugun faol: *{active_today}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Tilni tanlang:"
        )
    else:
        return (
            "🕌 *Hifz Bot — Your Quran Memorization Companion*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "A structured, gamified Telegram bot to help you memorize the Qur'an:\n\n"
            "📚 *Quran Navigator* — Start from any Surah\n"
            "🔥 *Flow Mode* — Deep continuous memorization (3x faster) (3×→7×→13×→Voice)\n"
            "🧠 *Quiz* — 3 game modes to test your knowledge\n"
            "⏰ *Smart Reminders* — Daily goals & automated notifications\n"
            "🏆 *League System* — Bronze→Silver→Gold→Diamond\n"
            "💎 *Premium* — Unlimited access (17,000 so'm/month)\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Community Stats (Live):*\n"
            f"👥 Total Users: *{total_users:,}*\n"
            f"📖 Total Ayahs Memorized: *{total_memorized:,}*\n"
            f"🟢 Active Today: *{active_today}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Choose your language:"
        )

def _home_text(user_id: int) -> str:
    total_users = db.get_total_users()
    total_memorized = db.get_total_memorized()
    active_today = db.get_active_today()
    user = db.get_user(user_id)
    lang = user["language"] if user else "en"

    if lang == "uz":
        return (
            "🕌 *Hifz Bot — Qur'on Yod Olish Hamrohi*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Bu bot sizga Qur'onni tizimli va qiziqarli usulda yod olishga yordam beradi:\n\n"
            "📚 *Qur'on Navigatori* — Istalgan suradan boshlang\n"
            "🔥 *Oqim Rejimi* — To'xtovsiz chuqur yod olish (3x tezroq) (3×→7×→13×→ovoz)\n"
            "🧠 *Test* — 3 xil o'yin bilan bilimingizni sinang\n"
            "⏰ *Eslatmalar* — Kunlik maqsad va avtomatik eslatmalar\n"
            "🏆 *Liga tizimi* — Bronza→Kumush→Oltin→Olmos\n"
            "💎 *Premium* — Cheksiz imkoniyatlar (17 000 so'm/oy)\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Jamoatchilik statistikasi:*\n"
            f"👥 Jami foydalanuvchilar: *{total_users:,}*\n"
            f"📖 Jami yod olingan oyatlar: *{total_memorized:,}*\n"
            f"🟢 Bugun faol: *{active_today}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Asosiy menyu:"
        )
    else:
        return (
            "🕌 *Hifz Bot — Your Quran Memorization Companion*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "A structured, gamified Telegram bot to help you memorize the Qur'an:\n\n"
            "📚 *Quran Navigator* — Start from any Surah\n"
            "🔥 *Flow Mode* — Deep continuous memorization (3x faster) (3×→7×→13×→Voice)\n"
            "🧠 *Quiz* — 3 game modes to test your knowledge\n"
            "⏰ *Smart Reminders* — Daily goals & automated notifications\n"
            "🏆 *League System* — Bronze→Silver→Gold→Diamond\n"
            "💎 *Premium* — Unlimited access (17,000 so'm/month)\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Community Stats (Live):*\n"
            f"👥 Total Users: *{total_users:,}*\n"
            f"📖 Total Ayahs Memorized: *{total_memorized:,}*\n"
            f"🟢 Active Today: *{active_today}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Main menu:"
        )

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.first_name)
    db.ensure_settings(user.id)
    db.ensure_gamification(user.id)

    # Check deep links
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith("xatm_"):
            try:
                xatm_id = int(arg.split("_", 1)[1])
                from src.handlers.xatm import _show_xatm_view
                await _show_xatm_view(update.message, user.id, xatm_id)
                return
            except ValueError:
                pass

    # Remove any legacy reply keyboard (delete the helper message immediately)
    rm_msg = await update.message.reply_text("\u200b", reply_markup=ReplyKeyboardRemove())
    try:
        await rm_msg.delete()
    except Exception:
        pass

    text = _build_intro_text(user.id)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(EN["lang_en"], callback_data="lang:en"),
            InlineKeyboardButton(EN["lang_uz"], callback_data="lang:uz"),
        ]
    ])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

async def cb_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":")[1]
    user = query.from_user
    db.set_user_language(user.id, lang)
    await query.edit_message_text(
        t(user.id, "welcome", name=user.first_name),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(user.id),
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not db.get_user(user.id):
        await update.message.reply_text(EN["please_start"])
        return
    await update.message.reply_text(
        t(user.id, "help"),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(user.id),
    )

async def cb_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Central menu dispatcher from inline buttons."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    action = query.data.split(":")[1]

    if action == "home":
        text = _home_text(user.id)
        keyboard = main_menu_keyboard(user.id)
        try:
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    elif action in ("learn", "flow"):
        # Both now go to the unified Surah Dashboard
        from src.handlers.flow import _show_surah_dashboard
        await _show_surah_dashboard(query, user.id)
    elif action == "quiz":
        from src.handlers.quiz import _show_quiz_menu
        await _show_quiz_menu(query, user.id)
    elif action == "profile":
        from src.handlers.profile import _show_profile
        await _show_profile(query, user.id, edit=True)
    elif action == "leaderboard":
        from src.handlers.leaderboard import _show_leaderboard
        await _show_leaderboard(query, user.id, edit=True)
    elif action == "settings":
        from src.handlers.settings import _show_settings_menu
        await _show_settings_menu(query, user.id, edit=True)
    elif action == "group_xatm":
        from src.handlers.xatm import _show_xatm_dashboard
        await _show_xatm_dashboard(query, user.id)
    elif action == "premium":
        from src.handlers.premium import _premium_text, _premium_keyboard
        try:
            await query.edit_message_text(
                _premium_text(user.id), parse_mode="Markdown",
                reply_markup=_premium_keyboard(user.id))
        except Exception:
            await query.message.reply_text(
                _premium_text(user.id), parse_mode="Markdown",
                reply_markup=_premium_keyboard(user.id))

def register(app):
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(cb_language, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(cb_menu, pattern=r"^menu:"))
