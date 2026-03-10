"""
profile.py — Sahifam (My Page) handler.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from services.stats_service import get_profile_data, format_time
from utils.keyboards import profile_period_keyboard
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


def register_profile_handlers(app):
    app.add_handler(MessageHandler(filters.Regex("^📊 Sahifam$"), show_profile))
    app.add_handler(CallbackQueryHandler(profile_period_callback, pattern="^profile_period_"))
    app.add_handler(CallbackQueryHandler(profile_share_callback,  pattern="^profile_share$"))
