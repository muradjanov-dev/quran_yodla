"""
profile.py — Sahifam (My Page) handler and Settings.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from services.stats_service import get_profile_data, format_time
from utils.keyboards import profile_period_keyboard, settings_keyboard, settings_notif_count_keyboard
from utils.messages import profile_message, share_result_message

logger = logging.getLogger(__name__)


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called from main menu: '📊 Sahifam'"""
    user_id = update.effective_user.id
    msg = update.message or (update.callback_query and update.callback_query.message)

    data = get_profile_data(user_id)
    if not data:
        await msg.reply_text("Ma'lumotlaringiz topilmadi. /start ni bosing.")
        return

    context.user_data["profile_data"] = data

    await msg.reply_text(
        profile_message(data, period="today"),
        reply_markup=profile_period_keyboard(active="today"),
        parse_mode=None,
    )


async def profile_period_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    period = query.data.split("_")[-1]  # "profile_period_week" → "week"

    data = get_profile_data(query.from_user.id)
    if not data:
        await query.message.reply_text("Ma'lumot topilmadi.")
        return

    try:
        await query.message.edit_text(
            profile_message(data, period=period),
            reply_markup=profile_period_keyboard(active=period),
        )
    except Exception:
        await query.message.reply_text(
            profile_message(data, period=period),
            reply_markup=profile_period_keyboard(active=period),
        )


async def profile_share_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    bot_username = (await context.bot.get_me()).username
    data = get_profile_data(user_id)
    if not data:
        return
    share_text = share_result_message(data, bot_username)
    await query.message.reply_text(share_text)


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called from main menu: '⚙️ Sozlamalar'"""
    from services.firebase_service import get_user
    user_id = update.effective_user.id
    msg = update.message or (update.callback_query and update.callback_query.message)
    if update.callback_query:
        await update.callback_query.answer()

    db_user = get_user(user_id)
    notif_enabled = True
    notif_count   = 1
    if db_user:
        notif_enabled = db_user.get("notification_settings", {}).get("enabled", True)
        notif_count   = db_user.get("notification_settings", {}).get("daily_count", 1)

    await msg.reply_text(
        "⚙️ SOZLAMALAR\n\n"
        "Quyidagi sozlamalarni o'zgartiring:",
        reply_markup=settings_keyboard(notif_enabled, notif_count)
    )


async def settings_notif_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.firebase_service import get_user, update_user
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    db_user = get_user(user_id)
    if not db_user:
        return
    current = db_user.get("notification_settings", {}).get("enabled", True)
    new_state = not current
    update_user(user_id, {"notification_settings.enabled": new_state})
    count = db_user.get("notification_settings", {}).get("daily_count", 1)
    icon = "🔔" if new_state else "🔕"
    status = "yoqildi" if new_state else "o'chirildi"
    try:
        await query.message.edit_reply_markup(
            reply_markup=settings_keyboard(new_state, count)
        )
    except Exception:
        pass
    await query.answer(f"{icon} Eslatmalar {status}!", show_alert=True)


async def settings_notif_count_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    from services.firebase_service import get_user
    db_user = get_user(query.from_user.id)
    current = 1
    if db_user:
        current = db_user.get("notification_settings", {}).get("daily_count", 1)
    await query.message.reply_text(
        "🔢 Kunlik eslatmalar sonini tanlang (1-5):",
        reply_markup=settings_notif_count_keyboard(current)
    )


async def settings_notif_count_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    count = int(query.data.split("_")[-1])
    from services.firebase_service import update_user, get_user
    update_user(query.from_user.id, {"notification_settings.daily_count": count})
    db_user = get_user(query.from_user.id)
    notif_enabled = True
    if db_user:
        notif_enabled = db_user.get("notification_settings", {}).get("enabled", True)
    try:
        await query.message.edit_text(
            f"✅ Kunlik eslatmalar soni: {count}x ga o'zgartirildi!",
            reply_markup=settings_keyboard(notif_enabled, count)
        )
    except Exception:
        await query.message.reply_text(f"✅ Kunlik eslatmalar soni: {count}x")


async def settings_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_settings(update, context)


async def settings_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    from services.firebase_service import get_user
    from utils.keyboards import referral_share_keyboard
    from utils.messages import referral_message
    db_user = get_user(query.from_user.id)
    if not db_user:
        return
    bot_username = (await context.bot.get_me()).username
    await query.message.reply_text(
        referral_message(db_user, bot_username),
        reply_markup=referral_share_keyboard(
            f"https://t.me/{bot_username}?start=ref_{db_user.get('referral_code', '')}"
        )
    )


async def settings_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔧 Til o'zgartirish tez orada qo'shiladi!", show_alert=True)


async def profile_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Legacy: redirect to settings."""
    await show_settings(update, context)


def register_profile_handlers(app):
    app.add_handler(MessageHandler(filters.Regex("^📊 Sahifam$"),    show_profile))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Sozlamalar$"), show_settings))
    app.add_handler(CallbackQueryHandler(profile_period_callback,    pattern="^profile_period_"))
    app.add_handler(CallbackQueryHandler(profile_share_callback,     pattern="^profile_share$"))
    app.add_handler(CallbackQueryHandler(profile_settings_callback,  pattern="^profile_settings$"))
    app.add_handler(CallbackQueryHandler(settings_notif_toggle,      pattern="^settings_notif_toggle$"))
    app.add_handler(CallbackQueryHandler(settings_notif_count_init,  pattern="^settings_notif_count$"))
    app.add_handler(CallbackQueryHandler(settings_notif_count_set,   pattern="^settings_nc_"))
    app.add_handler(CallbackQueryHandler(settings_back,              pattern="^settings_back$"))
    app.add_handler(CallbackQueryHandler(settings_referral,          pattern="^settings_referral$"))
    app.add_handler(CallbackQueryHandler(settings_lang,              pattern="^settings_lang$"))
