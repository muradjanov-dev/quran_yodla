"""
referral.py — Do'st taklif qilish (Referral) handler.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters

from services.firebase_service import get_user
from utils.keyboards import referral_share_keyboard
from utils.messages import referral_message

logger = logging.getLogger(__name__)


async def show_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg     = update.message or (update.callback_query and update.callback_query.message)
    if update.callback_query:
        await update.callback_query.answer()

    db_user = get_user(user_id)
    if not db_user:
        await msg.reply_text("Iltimos, /start ni bosing.")
        return

    bot_username = (await context.bot.get_me()).username
    ref_code     = db_user.get("referral_code", "")
    ref_link     = f"https://t.me/{bot_username}?start=ref_{ref_code}"

    await msg.reply_text(
        referral_message(db_user, bot_username),
        reply_markup=referral_share_keyboard(ref_link)
    )


def register_referral_handlers(app):
    # Keep old trigger in case some users still have old keyboard cached
    app.add_handler(MessageHandler(filters.Regex("^👥 Do'st taklif$"), show_referral))
