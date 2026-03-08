"""
admin.py — Admin panel handler (/admin command).
"""

import logging
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler,
    MessageHandler, CallbackQueryHandler, filters, CommandHandler
)

from config import ADMIN_ID, ADMIN_BROADCAST, ADMIN_USER_SEARCH
from services.firebase_service import (
    get_user, get_pending_premium_requests, get_all_users
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
    progress_msg = await update.message.reply_text(f"⏳ Xabar yuborilmoqda... {len(users)} ta user")

    for user in users:
        uid = user["telegram_id"]
        try:
            if update.message.photo:
                await context.bot.send_photo(uid, update.message.photo[-1].file_id,
                                              caption=update.message.caption or "")
            elif update.message.video:
                await context.bot.send_video(uid, update.message.video.file_id,
                                              caption=update.message.caption or "")
            else:
                await context.bot.send_message(uid, update.message.text)
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
