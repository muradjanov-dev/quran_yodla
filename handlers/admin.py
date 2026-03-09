"""
admin.py — Admin panel handler (/admin command).
"""

import logging
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler,
    MessageHandler, CallbackQueryHandler, filters, CommandHandler
)

from config import (
    ADMIN_ID, ADMIN_BROADCAST, ADMIN_USER_SEARCH,
    ADMIN_AYAH_PHOTO_SURAH, ADMIN_AYAH_PHOTO_AYAH, ADMIN_AYAH_PHOTO_UPLOAD,
)
from services.firebase_service import (
    get_user, get_pending_premium_requests, get_all_users,
    set_ayah_photo, delete_ayah_photo,
)
from services.stats_service import get_bot_wide_stats
from services.premium_service import activate_premium, deactivate_premium
from utils.keyboards import admin_main_keyboard, admin_user_actions_keyboard
from utils.messages import admin_menu_message, admin_user_info_message

logger = logging.getLogger(__name__)


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return  # silent ignore

    stats   = get_bot_wide_stats()
    pending = stats.get("pending_premium", 0)
    await update.message.reply_text(
        admin_menu_message(stats),
        reply_markup=admin_main_keyboard(pending_count=pending)
    )


async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer()
        return
    await query.answer()
    stats = get_bot_wide_stats()
    await query.message.reply_text(admin_menu_message(stats), reply_markup=admin_main_keyboard(stats.get("pending_premium",0)))


async def admin_user_mgmt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    await query.message.reply_text("👤 USER ID yoki @username kiriting:")
    return ADMIN_USER_SEARCH


async def admin_user_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    raw     = update.message.text.strip().lstrip("@")
    db_user = None

    if raw.isdigit():
        db_user = get_user(int(raw))
    else:
        # Search by username
        users = get_all_users()
        for u in users:
            un = u.get("username", "").lstrip("@").lower()
            if un == raw.lower():
                db_user = u
                break

    if not db_user:
        await update.message.reply_text("❌ Foydalanuvchi topilmadi.")
        return ADMIN_USER_SEARCH

    context.user_data["admin_target"] = db_user["telegram_id"]
    await update.message.reply_text(
        admin_user_info_message(db_user),
        reply_markup=admin_user_actions_keyboard(db_user["telegram_id"])
    )
    return ConversationHandler.END


async def admin_prem30_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    target_id = int(query.data.split("_")[-1])
    expiry    = activate_premium(target_id, days=30)
    try:
        await context.bot.send_message(target_id, f"💎 Admindan 30 kunlik premium berildi! (Tugaydi: {expiry.strftime('%d.%m.%Y')})")
    except Exception: pass
    await query.message.reply_text(f"✅ {target_id} ga 30 kunlik premium berildi.")


async def admin_prem7_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    target_id = int(query.data.split("_")[-1])
    expiry    = activate_premium(target_id, days=7)
    try:
        await context.bot.send_message(target_id, f"💎 Admindan 7 kunlik premium berildi! (Tugaydi: {expiry.strftime('%d.%m.%Y')})")
    except Exception: pass
    await query.message.reply_text(f"✅ {target_id} ga 7 kunlik premium berildi.")


async def admin_rem_prem_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    target_id = int(query.data.split("_")[-1])
    deactivate_premium(target_id)
    await query.message.reply_text(f"❌ {target_id} premium o'chirildi.")


async def admin_broadcast_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    await query.message.reply_text("📢 Barcha foydalanuvchilarga xabar:\n(Matn, rasm yoki video yuborishingiz mumkin)")
    return ADMIN_BROADCAST


async def admin_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users   = get_all_users()
    success = 0
    failed  = 0
    from_chat = update.effective_chat.id
    msg_id    = update.message.message_id
    progress_msg = await update.message.reply_text(f"⏳ Xabar yuborilmoqda... {len(users)} ta user")

    for user in users:
        uid = user.get("telegram_id")
        if not uid:
            continue
        try:
            await context.bot.copy_message(
                chat_id     = uid,
                from_chat_id= from_chat,
                message_id  = msg_id,
            )
            success += 1
        except Exception:
            failed += 1

    await progress_msg.edit_text(
        f"✅ Muvaffaqiyatli: {success}\n❌ Xato (bloklagan): {failed}"
    )
    return ConversationHandler.END


async def admin_pending_requests_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    reqs = get_pending_premium_requests()
    if not reqs:
        await query.message.reply_text("✅ Hozircha kutilayotgan so'rovlar yo'q.")
        return
    await query.message.reply_text(f"📋 {len(reqs)} ta premium so'rovi kutilmoqda. Tasdiqlash esingizda bo'lsin.")


async def admin_ayah_photo_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    await query.message.reply_text(
        "🖼 OYATGA RASM QO'SHISH\n\n"
        "1️⃣ Avval sura raqamini yuboring (masalan: 1):"
    )
    return ADMIN_AYAH_PHOTO_SURAH


async def admin_ayah_photo_surah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    text = update.message.text.strip()
    if not text.isdigit() or not (1 <= int(text) <= 114):
        await update.message.reply_text("❌ 1 dan 114 gacha raqam kiriting:")
        return ADMIN_AYAH_PHOTO_SURAH
    context.user_data["ayah_photo_surah"] = int(text)
    await update.message.reply_text(f"✅ Sura: {text}\n\n2️⃣ Oyat raqamini yuboring:")
    return ADMIN_AYAH_PHOTO_AYAH


async def admin_ayah_photo_ayah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    text = update.message.text.strip()
    if not text.isdigit() or int(text) < 1:
        await update.message.reply_text("❌ To'g'ri oyat raqami kiriting:")
        return ADMIN_AYAH_PHOTO_AYAH
    context.user_data["ayah_photo_ayah"] = int(text)
    surah = context.user_data["ayah_photo_surah"]
    await update.message.reply_text(
        f"✅ Sura {surah}, oyat {text}\n\n3️⃣ Endi rasmni yuboring:"
    )
    return ADMIN_AYAH_PHOTO_UPLOAD


async def admin_ayah_photo_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message.photo:
        await update.message.reply_text("❌ Iltimos, rasm yuboring (foto sifatida):")
        return ADMIN_AYAH_PHOTO_UPLOAD
    surah   = context.user_data.pop("ayah_photo_surah", None)
    ayah    = context.user_data.pop("ayah_photo_ayah", None)
    file_id = update.message.photo[-1].file_id
    set_ayah_photo(surah, ayah, file_id, ADMIN_ID)
    await update.message.reply_text(
        f"✅ Sura {surah}, {ayah}-oyatga rasm saqlandi!\n"
        f"Endi foydalanuvchilar bu oyatni yodlaganda rasm ko'rsatiladi."
    )
    return ConversationHandler.END


async def admin_ayah_photo_delete_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete photo: admin sends 'surah_ayah' e.g. '2_255' to delete."""
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    await query.message.reply_text(
        "🗑 O'chirish uchun sura va oyat raqamini yuboring.\n"
        "Format: <sura>_<oyat>  (masalan: 2_255)"
    )


async def admin_ayah_photo_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    parts = update.message.text.strip().split("_")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        await update.message.reply_text("❌ Format: <sura>_<oyat>  masalan: 2_255")
        return
    delete_ayah_photo(int(parts[0]), int(parts[1]))
    await update.message.reply_text(f"✅ Sura {parts[0]}, {parts[1]}-oyat rasmi o'chirildi.")


def build_admin_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("admin", cmd_admin),
        ],
        states={
            ADMIN_USER_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_user_search),
            ],
            ADMIN_BROADCAST: [
                MessageHandler(filters.ALL & ~filters.COMMAND, admin_broadcast_send),
            ],
            ADMIN_AYAH_PHOTO_SURAH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ayah_photo_surah),
            ],
            ADMIN_AYAH_PHOTO_AYAH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ayah_photo_ayah),
            ],
            ADMIN_AYAH_PHOTO_UPLOAD: [
                MessageHandler(filters.PHOTO, admin_ayah_photo_upload),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ayah_photo_upload),
            ],
        },
        fallbacks=[CommandHandler("start", lambda u, c: ConversationHandler.END)],
        allow_reentry=True,
        name="admin",
        per_message=False,
    )


def register_admin_callbacks(app):
    app.add_handler(CallbackQueryHandler(admin_stats_callback,          pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_user_mgmt_callback,      pattern="^admin_user_mgmt$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast_init,          pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(admin_pending_requests_callback,pattern="^admin_pending_requests$"))
    app.add_handler(CallbackQueryHandler(admin_prem30_callback,         pattern="^admin_prem30_"))
    app.add_handler(CallbackQueryHandler(admin_prem7_callback,          pattern="^admin_prem7_"))
    app.add_handler(CallbackQueryHandler(admin_rem_prem_callback,       pattern="^admin_rem_prem_"))
    app.add_handler(CallbackQueryHandler(admin_ayah_photo_init,         pattern="^admin_ayah_photo$"))
