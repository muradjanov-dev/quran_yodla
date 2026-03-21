"""Fixed premium handler — correct language lookup, admin settings ensurance, approve/decline working."""
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from src.database import db
from src.i18n import t

ADMIN_ID = db.ADMIN_ID
CARD_NUMBER = "5614 6830 0539 3277"
CARD_OWNER = "Nodirbek Murodjonov"
PRICE = "17 000 so'm/oy"

def _premium_text_en(user_id: int) -> str:
    prem = db.is_premium(user_id)
    info = db.get_premium_info(user_id)
    status = ""
    if prem and info and info["expires_at"]:
        status = f"\n\n✅ *You are Premium until {info['expires_at'][:10]}*"
    return (
        f"💎 *HIFZ BOT PREMIUM*{status}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📖 *Premium members memorize the Quran 3× faster* using our structured audio + repetition system.\n\n"
        "🔓 *What you unlock:*\n"
        "  ✅ Unlimited Quiz (vs 10/day free)\n"
        "  ✅ Unlimited Flow Learning (vs 5 ayahs/day free)\n"
        "  ✅ Up to 10 Reminder Times (vs 2 free)\n"
        "  ✅ Full Leaderboard (vs top 10 free)\n"
        "  ✅ Priority Features & Updates\n\n"
        f"💰 *Price:* {PRICE}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🌍 *Every premium purchase helps more and more people memorize the Qur'an. "
        "Your support keeps this project alive and free for those who cannot afford it.*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💳 *How to subscribe:*\n"
        f"1. Transfer *{PRICE}* to:\n"
        f"   `{CARD_NUMBER}`\n"
        f"   _{CARD_OWNER}_\n"
        "2. Take a screenshot of the payment\n"
        "3. Tap the button below & send the screenshot\n"
        "_Activated within a few hours._"
    )

def _premium_text_uz(user_id: int) -> str:
    prem = db.is_premium(user_id)
    info = db.get_premium_info(user_id)
    status = ""
    if prem and info and info["expires_at"]:
        status = f"\n\n✅ *Siz Premium a'zosiz — {info['expires_at'][:10]} gacha*"
    return (
        f"💎 *HIFZ BOT PREMIUM*{status}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📖 *Premium a'zolar Qur'onni 3 marta tezroq yod oladi* — audio va takrorlash tizimi orqali.\n\n"
        "🔓 *Nimalarni ochasiz:*\n"
        "  ✅ Cheksiz Test (bepul: 10/kun)\n"
        "  ✅ Cheksiz Oqim O'rganish (bepul: 5 oyat/kun)\n"
        "  ✅ 10 tagacha Eslatma (bepul: 2 ta)\n"
        "  ✅ To'liq Reyting jadval (bepul: top 10)\n"
        "  ✅ Ustuvor yangiliklar\n\n"
        f"💰 *Narxi:* {PRICE}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🌍 *Har bir premium xarid ko'proq odamlarning Qur'onni yod olishiga yordam beradi. "
        "Sizning qo'llab-quvvatlashingiz ushbu loyihani tirik saqlaydi.*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💳 *Qanday obuna bo'lish:*\n"
        f"1. *{PRICE}* ni quyidagi kartaga o'tkazing:\n"
        f"   `{CARD_NUMBER}`\n"
        f"   _{CARD_OWNER}_\n"
        "2. To'lov skrinshotini oling\n"
        "3. Quyidagi tugmani bosib, skrinshot yuboring\n"
        "_Bir necha soat ichida faollashtiriladi._"
    )

def _premium_text(user_id: int) -> str:
    user = db.get_user(user_id)
    lang = user["language"] if user else "en"
    return _premium_text_uz(user_id) if lang == "uz" else _premium_text_en(user_id)

def _premium_keyboard(user_id: int) -> InlineKeyboardMarkup:
    prem = db.is_premium(user_id)
    user = db.get_user(user_id)
    lang = user["language"] if user else "en"
    rows = []
    if not prem:
        label = "💳 I've Paid — Send Receipt" if lang == "en" else "💳 To'ladim — Chek yuborish"
        rows.append([InlineKeyboardButton(label, callback_data="premium:send_receipt")])
    rows.append([InlineKeyboardButton(t(user_id, "btn_main_menu"), callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)

async def cmd_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not db.get_user(user.id):
        await update.message.reply_text(t(user.id, "please_start"))
        return
    await update.message.reply_text(
        _premium_text(user.id), parse_mode="Markdown",
        reply_markup=_premium_keyboard(user.id))

async def cb_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    parts = query.data.split(":")
    action = parts[1]

    if action == "send_receipt":
        db.ensure_settings(user.id)
        db.update_settings(user.id, awaiting_input="awaiting_payment_photo")
        user_row = db.get_user(user.id)
        lang = user_row["language"] if user_row else "en"
        prompt = (
            "📸 *Send your payment screenshot now.*\n\nJust send the photo directly in this chat."
            if lang == "en" else
            "📸 *Hozir to'lov skrinshotini yuboring.*\n\nFaqat fotosuratni bu chatga yuboring."
        )
        await query.edit_message_text(prompt, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t(user.id, "btn_main_menu"), callback_data="menu:home"),
            ]]))

    elif action == "approve" and len(parts) >= 3:
        req_id = int(parts[2])
        req = db.get_payment_request(req_id)
        if not req:
            await query.answer("Request not found.", show_alert=True)
            return
        if req["status"] != "pending":
            await query.answer("Already handled.", show_alert=True)
            return
        db.update_payment_request(req_id, status="approved")
        db.grant_premium(req["user_id"], months=1)
        info = db.get_premium_info(req["user_id"])
        exp = info["expires_at"][:10] if info and info["expires_at"] else "?"
        # Get language from users table separately
        target_user = db.get_user(req["user_id"])
        lang = target_user["language"] if target_user else "en"
        approved_msg = (
            f"🎉 *Premium Activated!*\n\nYour premium is active until *{exp}*.\n\n"
            "JazakAllah for supporting the Hifz Bot mission! 🌟\n\n"
            "💎 You now memorize Quran *3× faster* — enjoy unlimited access!"
            if lang == "en" else
            f"🎉 *Premium Faollashtirildi!*\n\nPremiumingiz *{exp}* gacha amal qiladi.\n\n"
            "Hifz Bot missiyasini qo'llab-quvvatlaganingiz uchun JazakAllah! 🌟\n\n"
            "💎 Endi Qur'onni *3 marta tezroq* yod olasiz — cheksiz imkoniyatlardan bahramand bo'ling!"
        )
        try:
            await context.bot.send_message(
                chat_id=req["user_id"], text=approved_msg, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💎 My Premium", callback_data="menu:premium"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="menu:home"),
                ]]))
        except Exception as e:
            print(f"[Premium] Failed to notify user {req['user_id']}: {e}")
        # Edit admin message
        target_name = target_user["name"] if target_user else str(req["user_id"])
        try:
            await query.edit_message_caption(
                caption=f"✅ *APPROVED* — {target_name} (ID:{req['user_id']})\nPremium until {exp}",
                parse_mode="Markdown")
        except Exception:
            await query.message.reply_text(f"✅ Approved: {target_name}, premium until {exp}")

    elif action == "decline" and len(parts) >= 3:
        req_id = int(parts[2])
        req = db.get_payment_request(req_id)
        if not req:
            await query.answer("Request not found.", show_alert=True)
            return
        if req["status"] != "pending":
            await query.answer("Already handled.", show_alert=True)
            return
        # Ensure admin has settings row
        db.ensure_settings(ADMIN_ID)
        db.update_settings(ADMIN_ID, awaiting_input=f"decline_reason:{req_id}:{req['user_id']}")
        try:
            await query.edit_message_caption(
                caption=f"❌ Declining request #{req_id} from user {req['user_id']}.\n\n*Type your decline reason now* (send as a text message to the bot):",
                parse_mode="Markdown",
                reply_markup=None)
        except Exception:
            await query.message.reply_text(
                f"❌ Declining #{req_id}. Type your reason now as a text message.")

async def handle_payment_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo sent by user as payment receipt."""
    user = update.effective_user
    if not db.get_user(user.id):
        return
    db.ensure_settings(user.id)
    settings = db.get_settings(user.id)
    if not settings or settings["awaiting_input"] != "awaiting_payment_photo":
        return

    photo = update.message.photo[-1]
    req_id = db.create_payment_request(user.id, photo.file_id)
    db.update_settings(user.id, awaiting_input=None)

    user_row = db.get_user(user.id)
    lang = user_row["language"] if user_row else "en"
    ack = (
        "✅ *Receipt received!* We'll review it within a few hours and activate your premium."
        if lang == "en" else
        "✅ *Chek qabul qilindi!* Bir necha soat ichida ko'rib chiqamiz va premiumingizni faollashtirамиз."
    )
    await update.message.reply_text(ack, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(t(user.id, "btn_main_menu"), callback_data="menu:home"),
        ]]))

    caption = (
        f"💳 *New Payment Request #{req_id}*\n"
        f"👤 {user.full_name} (@{user.username or 'no\\_username'})\n"
        f"🆔 ID: `{user.id}`\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    try:
        admin_msg = await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo.file_id,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(f"✅ Approve #{req_id}", callback_data=f"premium:approve:{req_id}"),
                InlineKeyboardButton(f"❌ Decline #{req_id}", callback_data=f"premium:decline:{req_id}"),
            ]]),
        )
        db.set_payment_admin_msg(req_id, admin_msg.message_id)
    except Exception as e:
        print(f"[Premium] Failed to notify admin: {e}")

def register(app):
    app.add_handler(CommandHandler("premium", cmd_premium))
    app.add_handler(CallbackQueryHandler(cb_premium, pattern=r"^premium:"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_payment_photo))
