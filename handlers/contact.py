"""
contact.py — User → Admin contact/support flow with two-way messaging.
"""

import logging
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler,
    MessageHandler, CallbackQueryHandler, filters, CommandHandler
)
from config import ADMIN_ID, CONTACT_AWAIT_MSG
from utils.keyboards import contact_reply_keyboard

logger = logging.getLogger(__name__)


async def contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User taps 📞 Murojaat."""
    msg = update.message or (update.callback_query and update.callback_query.message)
    if update.callback_query:
        await update.callback_query.answer()
    await msg.reply_text(
        "📞 ADMIN BILAN BOG'LANISH\n\n"
        "Savolingiz, taklifingiz yoki muammoingizni yuboring.\n"
        "(Matn, rasm, audio — har qanday format)\n\n"
        "❌ Bekor qilish: /start"
    )
    return CONTACT_AWAIT_MSG


async def contact_message_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Forward user message to admin with a reply button."""
    user    = update.effective_user
    user_id = user.id
    username = f"@{user.username}" if user.username else "—"

    try:
        await context.bot.forward_message(
            chat_id    = ADMIN_ID,
            from_chat_id = update.effective_chat.id,
            message_id = update.message.message_id,
        )
        await context.bot.send_message(
            chat_id    = ADMIN_ID,
            text       = (
                f"👆 FOYDALANUVCHI MUROJAAT:\n"
                f"👤 [{user.full_name}](tg://user?id={user_id})\n"
                f"🆔 {username} | `{user_id}`"
            ),
            parse_mode = "Markdown",
            reply_markup = contact_reply_keyboard(user_id),
        )
    except Exception as e:
        logger.error(f"Contact forward failed: {e}")

    await update.message.reply_text(
        "✅ Murojaatingiz adminga yuborildi!\n"
        "Tez orada javob beriladi in shaa ALLOH 🤲"
    )
    return ConversationHandler.END


async def contact_admin_reply_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin clicks ↩️ Javob qaytarish — sets reply target in user_data."""
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    target_id = int(query.data.replace("contact_reply_", ""))
    context.user_data["_reply_to"] = target_id
    await query.message.reply_text(
        f"✍️ {target_id} ga javob yuboring (har qanday format):\n"
        f"(Bekor qilish: /admin)"
    )


def build_contact_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📞 Murojaat$"), contact_start),
        ],
        states={
            CONTACT_AWAIT_MSG: [
                MessageHandler(filters.ALL & ~filters.COMMAND, contact_message_received),
            ],
        },
        fallbacks=[CommandHandler("start", lambda u, c: ConversationHandler.END)],
        allow_reentry=True,
        name="contact",
        per_message=False,
    )


def register_contact_callbacks(app):
    app.add_handler(CallbackQueryHandler(contact_admin_reply_init, pattern="^contact_reply_"))
