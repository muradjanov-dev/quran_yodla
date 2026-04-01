"""
premium.py — Premium subscription, trial, and receipt submission.
"""

import logging
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler,
    MessageHandler, CallbackQueryHandler, filters, CommandHandler
)
from config import ADMIN_ID, PREMIUM_AWAIT_RECEIPT
from services.firebase_service import (
    get_user, create_premium_request, get_premium_request, update_premium_request
)
from services.premium_service import (
    activate_trial, activate_premium, is_premium,
    can_use_trial, get_premium_expiry_str
)
from utils.keyboards import premium_keyboard, admin_premium_decision_keyboard
from utils.messages import (
    premium_menu_message, premium_trial_offer, premium_approved_message,
    premium_rejected_message, admin_premium_request_message
)

logger = logging.getLogger(__name__)


async def show_premium_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg     = update.message or (update.callback_query and update.callback_query.message)
    if update.callback_query:
        await update.callback_query.answer()

    db_user = get_user(user_id)
    if not db_user:
        await msg.reply_text("Iltimos, /start ni bosing.")
        return

    active = is_premium(db_user)
    expiry = get_premium_expiry_str(db_user)
    trial_avail = can_use_trial(db_user)

    menu_text = premium_menu_message(active, expiry)
    if not active and trial_avail:
        menu_text += f"\n\n{premium_trial_offer()}"

    await msg.reply_text(
        menu_text,
        reply_markup=premium_keyboard(trial_available=(not active and trial_avail))
    )


async def trial_activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    success = activate_trial(user_id)
    if success:
        await query.message.reply_text(
            "🎉 3 kunlik BEPUL Premium faollashtirildi!\n\n"
            "Barcha imkoniyatlar ochiq! Yodlashni boshlang! 🚀"
        )
        import asyncio
        from handlers.achievements import check_and_notify_achievements
        asyncio.ensure_future(check_and_notify_achievements(context.bot, user_id))
    else:
        await query.message.reply_text(
            "❌ Siz avval trial talab qilgansiz yoki hozir premium faol.\n\n"
            "To'liq premium uchun chek yuboring."
        )


async def receipt_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📸 To'lov chekini (screenshot) yuboring:\n(Rasm ko'rinishida jo'nating)"
    )
    return PREMIUM_AWAIT_RECEIPT


async def receipt_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg     = update.message
    user_id = msg.from_user.id
    db_user = get_user(user_id)

    if not msg.photo:
        await msg.reply_text("❌ Iltimos, chekni RASM sifatida yuboring.")
        return PREMIUM_AWAIT_RECEIPT

    file_id  = msg.photo[-1].file_id
    username = db_user.get("username", "") if db_user else ""
    full_name= db_user.get("full_name", "Foydalanuvchi") if db_user else msg.from_user.full_name

    req_id = create_premium_request(user_id, username, full_name, file_id)

    await msg.reply_text(
        "✅ Chekingiz qabul qilindi! Admin ko'rib chiqadi.\n"
        "Odatda 1-24 soat ichida javob beriladi."
    )

    # Notify admin — first try as photo with caption, fall back to text + forwarded photo
    admin_text = admin_premium_request_message({"full_name": full_name, "username": username, "telegram_id": user_id})
    try:
        admin_msg = await context.bot.send_photo(
            chat_id      = ADMIN_ID,
            photo        = file_id,
            caption      = admin_text,
            reply_markup = admin_premium_decision_keyboard(req_id)
        )
        update_premium_request(req_id, {"admin_message_id": admin_msg.message_id})
        logger.info(f"Admin notified about premium request {req_id} from user {user_id}")
    except Exception as e:
        logger.error(f"Admin photo notify failed: {e}")
        # Fallback: send text message + forward the photo separately
        try:
            await context.bot.send_message(
                chat_id      = ADMIN_ID,
                text         = admin_text,
                reply_markup = admin_premium_decision_keyboard(req_id)
            )
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=file_id)
        except Exception as e2:
            logger.error(f"Admin fallback notify failed: {e2}")

    return ConversationHandler.END


# ─── Admin Approval Callbacks ─────────────────────────────────────────────────

async def admin_approve_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    req_id = query.data.replace("admin_approve_", "")
    req    = get_premium_request(req_id)
    if not req:
        await query.message.reply_text("So'rov topilmadi.")
        return

    user_id = req["user_id"]
    expiry  = activate_premium(user_id, days=30)
    update_premium_request(req_id, {
        "status":       "approved",
        "processed_at": expiry,
    })

    expiry_str = expiry.strftime("%d %B %Y")
    try:
        await context.bot.send_message(
            chat_id = user_id,
            text    = premium_approved_message(expiry_str)
        )
    except Exception as e:
        logger.error(f"User premium notify failed: {e}")

    await query.message.reply_text(f"✅ Premium tasdiqlandi. User {user_id}, tugash: {expiry_str}")



def build_premium_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💎 Premium$"), show_premium_menu),
            CallbackQueryHandler(show_premium_menu,  pattern="^open_premium$"),
            # Receipt entry: clicking the button starts the receipt flow
            CallbackQueryHandler(receipt_prompt,     pattern="^premium_send_receipt$"),
        ],
        states={
            PREMIUM_AWAIT_RECEIPT: [
                MessageHandler(filters.PHOTO, receipt_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receipt_received),
            ],
        },
        fallbacks=[CommandHandler("start", lambda u, c: ConversationHandler.END)],
        allow_reentry=True,
        name="premium",
        per_message=False,
    )


def register_premium_callbacks(app):
    app.add_handler(CallbackQueryHandler(trial_activate,        pattern="^premium_trial$"))
    app.add_handler(CallbackQueryHandler(admin_approve_request, pattern="^admin_approve_"))
