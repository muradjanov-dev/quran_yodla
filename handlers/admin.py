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
    ADMIN_ID, ADMIN_BROADCAST, ADMIN_USER_SEARCH, ADMIN_REJECT_REASON,
    ADMIN_AYAH_PHOTO_SURAH, ADMIN_AYAH_PHOTO_AYAH, ADMIN_AYAH_PHOTO_UPLOAD,
    ADMIN_AYAH_PHOTO_SURAH_SELECT, ADMIN_AYAH_PHOTO_AYAH_SELECT,
    ADMIN_NOTIF_TIME, ADMIN_NOTIF_COUNT,
)
from services.firebase_service import (
    get_user, get_pending_premium_requests, get_all_users,
    set_ayah_photo, delete_ayah_photo,
    get_notification_time, get_notification_settings, get_notification_times_list,
    set_notification_time, set_notification_times, set_notification_count,
    get_premium_request, update_premium_request,
)
from services.stats_service import get_bot_wide_stats
from services.premium_service import activate_premium, deactivate_premium
from utils.keyboards import (
    admin_main_keyboard, admin_user_actions_keyboard, broadcast_confirm_keyboard,
    admin_notif_count_keyboard, admin_surah_select_keyboard,
    admin_ayah_select_keyboard, admin_photo_next_keyboard,
)
from utils.messages import (
    admin_menu_message, admin_user_info_message,
    premium_rejected_message,
)

logger = logging.getLogger(__name__)


def _admin_keyboard():
    try:
        stats = get_bot_wide_stats()
    except Exception as e:
        logger.error(f"get_bot_wide_stats error: {e}")
        stats = {"total_users": 0, "premium_users": 0, "new_today": 0,
                 "active_today": 0, "active_7d": 0, "pending_premium": 0}
    try:
        hour, minute, count = get_notification_settings()
    except Exception as e:
        logger.error(f"get_notification_settings error: {e}")
        hour, minute, count = 8, 0, 1
    return admin_menu_message(stats), admin_main_keyboard(
        pending_count=stats.get("pending_premium", 0),
        notif_time=f"{hour:02d}:{minute:02d}",
        notif_count=count,
    )


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    text, kb = _admin_keyboard()
    await update.message.reply_text(text, reply_markup=kb)


async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    text, kb = _admin_keyboard()
    await query.message.reply_text(text, reply_markup=kb)


async def admin_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    text, kb = _admin_keyboard()
    await query.message.reply_text(text, reply_markup=kb)


async def admin_user_mgmt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    await query.message.reply_text("👤 USER ID yoki @username kiriting:")
    return ADMIN_USER_SEARCH


_MENU_BUTTONS = {"📊 Sahifam", "📗 Yodlash", "🎧 Tinglash", "🏆 Reyting",
                 "💎 Premium", "📞 Murojaat", "⚙️ Sozlamalar"}


async def admin_user_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    raw = update.message.text.strip().lstrip("@")

    # If input looks like a menu button (contains emoji/spaces/non-alphanumeric),
    # silently exit the conversation so other handlers can process it
    clean = raw.replace("_", "").replace(".", "").replace("-", "")
    if not clean.isalnum():
        return ConversationHandler.END

    db_user = None
    if raw.isdigit():
        db_user = get_user(int(raw))
    else:
        users = get_all_users()
        for u in users:
            un = u.get("username", "").lstrip("@").lower()
            if un == raw.lower():
                db_user = u
                break

    if not db_user:
        await update.message.reply_text("❌ Foydalanuvchi topilmadi. ID yoki @username kiriting:")
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
    """Sets broadcast mode flag — handled by group=-1 interceptor."""
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    context.user_data["_bcast"] = True
    await query.message.reply_text(
        "📢 Barcha foydalanuvchilarga xabar:\n"
        "(Matn, rasm, video yoki har qanday format yuborishingiz mumkin)\n\n"
        "Xabarni yuboring 👇"
    )


async def admin_broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin confirmed broadcast — send to all users."""
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    from_chat = context.user_data.pop("_bcast_from_chat", None)
    msg_id    = context.user_data.pop("_bcast_msg_id",    None)
    if not from_chat or not msg_id:
        await query.message.edit_text("❌ Xabar topilmadi. Qaytadan urinib ko'ring.")
        return

    await query.message.edit_text("⏳ Xabar yuborilmoqda...")
    users   = get_all_users()
    success = 0
    failed  = 0
    import asyncio
    for user in users:
        uid = user.get("telegram_id")
        if not uid:
            continue
        try:
            await context.bot.copy_message(
                chat_id      = uid,
                from_chat_id = from_chat,
                message_id   = msg_id,
            )
            success += 1
        except Exception as e:
            logger.debug(f"Broadcast failed for {uid}: {e}")
            failed += 1
        await asyncio.sleep(0.05)

    await query.message.edit_text(
        f"✅ Muvaffaqiyatli: {success}\n❌ Xato (bloklagan): {failed}"
    )


async def admin_broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin cancelled the broadcast."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("_bcast_from_chat", None)
    context.user_data.pop("_bcast_msg_id",    None)
    await query.message.edit_text("❌ Xabar yuborish bekor qilindi.")


# ─── Admin Reject (moved from premium.py) ─────────────────────────────────────

async def admin_reject_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    req_id = query.data.replace("admin_reject_", "")
    context.user_data["_reject_req_id"] = req_id
    await query.message.reply_text("❌ Rad etish sababini yozing:")
    return ADMIN_REJECT_REASON


async def admin_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    reason = update.message.text.strip()
    req_id = context.user_data.pop("_reject_req_id", None)
    if not req_id:
        return ConversationHandler.END
    req = get_premium_request(req_id)
    if not req:
        await update.message.reply_text("So'rov topilmadi.")
        return ConversationHandler.END
    update_premium_request(req_id, {
        "status":           "rejected",
        "rejection_reason": reason,
    })
    try:
        await context.bot.send_message(
            chat_id = req["user_id"],
            text    = premium_rejected_message(reason)
        )
    except Exception:
        pass
    await update.message.reply_text("✅ Rad etish yuborildi.")
    return ConversationHandler.END


async def admin_all_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all users paginated 15 per page; tap a user number to see their detail."""
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()

    parts = query.data.split("_")
    page: int = int(parts[-1]) if parts[-1].isdigit() else 0

    users     = get_all_users()
    page_size = 15
    total     = len(users)
    start     = page * page_size
    end       = min(start + page_size, total)

    lines = [
        f"👥 FOYDALANUVCHILAR ({start+1}–{end} / {total} ta)",
        "─────────────────────────────────────────",
    ]
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    user_buttons = []
    for i, u in enumerate(users[start:end], start + 1):
        uid      = u.get("telegram_id", 0)
        name     = (u.get("full_name") or "Anonim")[:16]
        username = f"@{u['username']}" if u.get("username") else "—"
        stats    = u.get("stats", {})
        verses   = stats.get("total_verses_read", 0)
        himmat   = stats.get("himmat_points", 0)
        prem     = "💎" if u.get("premium", {}).get("is_active") else "  "
        lines.append(f"#{i:<3} {prem}{name:<16} {username:<18} 📖{verses}  💎{himmat:,}")
        user_buttons.append(InlineKeyboardButton(
            f"{i}. {name[:12]}{prem}",
            callback_data=f"admin_udetail_{uid}"
        ))

    text = "\n".join(lines)

    # Build keyboard: user buttons 2 per row + pagination
    buttons = []
    for j in range(0, len(user_buttons), 2):
        buttons.append(user_buttons[j:j+2])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"admin_users_{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"admin_users_{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("↩️ Orqaga", callback_data="admin_back")])
    keyboard = InlineKeyboardMarkup(buttons)

    await query.message.reply_text(text, reply_markup=keyboard, disable_web_page_preview=True)


async def admin_user_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show full detail for a specific user."""
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    uid = int(query.data.split("_")[-1])
    db_user = get_user(uid)
    if not db_user:
        await query.message.reply_text("❌ Foydalanuvchi topilmadi.")
        return
    # Referral stats
    stats = db_user.get("stats", {})
    ref_count = db_user.get("referral_count", 0)
    from utils.messages import admin_user_info_message
    text = admin_user_info_message(db_user)
    text += f"\n👥 Taklif qilganlar: {ref_count} kishi"
    await query.message.reply_text(
        text,
        reply_markup=admin_user_actions_keyboard(uid)
    )


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
        "🖼 OYATGA RASM QO'SHISH\n\nSurani tanlang:",
        reply_markup=admin_surah_select_keyboard(page=0)
    )
    return ADMIN_AYAH_PHOTO_SURAH_SELECT


async def admin_ayah_photo_surah_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Navigate to different surah page."""
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    page = int(query.data.split("_")[-1])
    try:
        await query.message.edit_reply_markup(reply_markup=admin_surah_select_keyboard(page=page))
    except Exception:
        await query.message.reply_text("Surani tanlang:", reply_markup=admin_surah_select_keyboard(page=page))
    return ADMIN_AYAH_PHOTO_SURAH_SELECT


async def admin_ayah_photo_surah_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin clicked a surah button."""
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    surah_num = int(query.data.split("_")[-1])
    from utils.helpers import get_surah_by_number
    surah_info = get_surah_by_number(surah_num)
    if not surah_info:
        await query.message.reply_text("Sura topilmadi."); return ADMIN_AYAH_PHOTO_SURAH_SELECT
    context.user_data["ayah_photo_surah"] = surah_num
    context.user_data["ayah_photo_surah_name"] = surah_info["name"]
    context.user_data["ayah_photo_total"] = surah_info["ayah_count"]
    try:
        await query.message.edit_text(
            f"✅ {surah_info['name']} ({surah_num}-sura, {surah_info['ayah_count']} oyat)\n\nOyat raqamini tanlang:",
            reply_markup=admin_ayah_select_keyboard(surah_num, surah_info["ayah_count"], page=0)
        )
    except Exception:
        await query.message.reply_text(
            f"✅ {surah_info['name']}\nOyat raqamini tanlang:",
            reply_markup=admin_ayah_select_keyboard(surah_num, surah_info["ayah_count"], page=0)
        )
    return ADMIN_AYAH_PHOTO_AYAH_SELECT


async def admin_ayah_photo_ayah_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Navigate to different ayah page."""
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    parts = query.data.split("_")   # aphoto_ap_{surah}_{page}
    surah_num = int(parts[-2])
    page = int(parts[-1])
    from utils.helpers import get_surah_by_number
    surah_info = get_surah_by_number(surah_num)
    ayah_count = surah_info["ayah_count"] if surah_info else 286
    try:
        await query.message.edit_reply_markup(
            reply_markup=admin_ayah_select_keyboard(surah_num, ayah_count, page=page)
        )
    except Exception:
        pass
    return ADMIN_AYAH_PHOTO_AYAH_SELECT


async def admin_ayah_photo_back_surah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to surah selection."""
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    try:
        await query.message.edit_text(
            "🖼 OYATGA RASM QO'SHISH\n\nSurani tanlang:",
            reply_markup=admin_surah_select_keyboard(page=0)
        )
    except Exception:
        await query.message.reply_text("Surani tanlang:", reply_markup=admin_surah_select_keyboard(page=0))
    return ADMIN_AYAH_PHOTO_SURAH_SELECT


async def admin_ayah_photo_ayah_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin clicked an ayah button."""
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    ayah_num = int(query.data.split("_")[-1])
    context.user_data["ayah_photo_ayah"] = ayah_num
    surah_num  = context.user_data.get("ayah_photo_surah", 1)
    surah_name = context.user_data.get("ayah_photo_surah_name", "")
    try:
        await query.message.edit_text(
            f"✅ {surah_name} — {ayah_num}-oyat\n\n📸 Endi rasmni yuboring:"
        )
    except Exception:
        await query.message.reply_text(f"✅ {surah_name} — {ayah_num}-oyat\n\n📸 Endi rasmni yuboring:")
    return ADMIN_AYAH_PHOTO_UPLOAD


async def admin_ayah_photo_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message.photo:
        await update.message.reply_text("❌ Iltimos, rasm yuboring (foto sifatida):")
        return ADMIN_AYAH_PHOTO_UPLOAD
    surah      = context.user_data.pop("ayah_photo_surah", None)
    ayah       = context.user_data.pop("ayah_photo_ayah", None)
    surah_name = context.user_data.pop("ayah_photo_surah_name", "")
    total      = context.user_data.pop("ayah_photo_total", 286)
    file_id    = update.message.photo[-1].file_id
    set_ayah_photo(surah, ayah, file_id, ADMIN_ID)
    await update.message.reply_text(
        f"✅ {surah_name} {ayah}-oyatga rasm saqlandi!",
        reply_markup=admin_photo_next_keyboard(surah, surah_name, ayah + 1, total)
    )
    return ConversationHandler.END


async def admin_ayah_photo_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin taps 'next ayah' button after upload — jump straight to photo upload state."""
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    parts = query.data.split("_")   # aphoto_nx_{surah}_{ayah}
    surah_num = int(parts[-2])
    ayah_num  = int(parts[-1])
    from utils.helpers import get_surah_by_number
    surah_info = get_surah_by_number(surah_num)
    surah_name = surah_info["name"] if surah_info else ""
    total      = surah_info["ayah_count"] if surah_info else 286
    context.user_data["ayah_photo_surah"] = surah_num
    context.user_data["ayah_photo_ayah"]  = ayah_num
    context.user_data["ayah_photo_surah_name"] = surah_name
    context.user_data["ayah_photo_total"] = total
    await query.message.reply_text(
        f"📸 {surah_name} — {ayah_num}-oyat rasmini yuboring:"
    )
    return ADMIN_AYAH_PHOTO_UPLOAD


# ─── Old text-based ayah photo helpers (kept as fallback stubs) ───────────────

async def admin_ayah_photo_surah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Legacy text handler — exits conversation if non-numeric (e.g. menu button press)."""
    if update.effective_user.id != ADMIN_ID:
        return
    text = update.message.text.strip()
    if not text.isdigit() or not (1 <= int(text) <= 114):
        return ConversationHandler.END   # exit on menu buttons / invalid input
    context.user_data["ayah_photo_surah"] = int(text)
    await update.message.reply_text(f"✅ Sura: {text}\n\n2️⃣ Oyat raqamini yuboring:")
    return ADMIN_AYAH_PHOTO_AYAH


async def admin_ayah_photo_ayah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Legacy text handler."""
    if update.effective_user.id != ADMIN_ID:
        return
    text = update.message.text.strip()
    if not text.isdigit() or int(text) < 1:
        return ConversationHandler.END
    context.user_data["ayah_photo_ayah"] = int(text)
    surah = context.user_data["ayah_photo_surah"]
    await update.message.reply_text(f"✅ Sura {surah}, oyat {text}\n\n3️⃣ Endi rasmni yuboring:")
    return ADMIN_AYAH_PHOTO_UPLOAD


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


async def admin_notif_count_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    _, _, current_count = get_notification_settings()
    await query.message.reply_text(
        f"🔔 KUNLIK BILDIRISHNOMALAR SONI\n\n"
        f"Hozirgi: {current_count}x kuniga\n\n"
        f"Nechta yuborilsin? (1 dan 5 gacha)\n"
        f"Vaqtlar base vaqtdan boshlanib teng taqsimlanadi:",
        reply_markup=admin_notif_count_keyboard(current_count),
    )
    return ADMIN_NOTIF_COUNT


async def admin_notif_count_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    count = int(query.data.split("_")[-1])
    set_notification_count(count)

    # Reschedule notification jobs in APScheduler
    try:
        import pytz
        from apscheduler.triggers.cron import CronTrigger
        scheduler = context.application.bot_data.get("scheduler")
        if scheduler:
            TZ = pytz.timezone("Asia/Tashkent")
            hour, minute, _ = get_notification_settings()
            # Remove old notification jobs
            for i in range(5):
                try:
                    scheduler.remove_job(f"daily_notifications_{i}")
                except Exception:
                    pass
            # Add new jobs evenly spaced
            intervals = {1: 0, 2: 8, 3: 6, 4: 4, 5: 3}
            interval_h = intervals.get(count, 0)
            for i in range(count):
                job_hour = (hour + i * interval_h) % 24
                scheduler.add_job(
                    context.application.bot_data["_daily_notif_fn"],
                    CronTrigger(hour=job_hour, minute=minute, timezone=TZ),
                    id=f"daily_notifications_{i}",
                    replace_existing=True,
                )
            logger.info(f"Notification count set to {count}x")
    except Exception as e:
        logger.error(f"Reschedule notif count error: {e}")

    await query.message.edit_text(
        f"✅ Kunlik bildirishnomalar soni: {count}x ga o'zgartirildi!"
    )
    return ConversationHandler.END


async def admin_notif_time_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer(); return
    await query.answer()
    _, _, count = get_notification_settings()
    times = get_notification_times_list()
    current = ", ".join(f"{h:02d}:{m:02d}" for h, m in times)
    if count > 1:
        await query.message.reply_text(
            f"⏰ BILDIRISHNOMA VAQTLARI ({count}x)\n\n"
            f"Hozirgi vaqtlar: {current} (Toshkent)\n\n"
            f"{count} ta vaqtni vergul bilan kiriting:\n"
            f"(masalan: 05:50, 22:30)"
        )
    else:
        await query.message.reply_text(
            f"⏰ BILDIRISHNOMA VAQTI\n\n"
            f"Hozirgi vaqt: {current} (Toshkent)\n\n"
            f"Yangi vaqtni HH:MM formatida yuboring:\n"
            f"(masalan: 07:30, 09:00, 20:00)"
        )
    return ADMIN_NOTIF_TIME


def _parse_times(text: str) -> list:
    """Parse 'HH:MM' or 'HH:MM, HH:MM, ...' → list of 'HH:MM' strings, or [] on error."""
    result = []
    for part in text.replace("،", ",").split(","):
        part = part.strip()
        pieces = part.split(":")
        if len(pieces) != 2 or not all(p.strip().isdigit() for p in pieces):
            return []
        h, m = int(pieces[0]), int(pieces[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            return []
        result.append(f"{h:02d}:{m:02d}")
    return result


async def admin_notif_time_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    raw = update.message.text.strip()
    if raw in _MENU_BUTTONS:
        return ConversationHandler.END
    _, _, count = get_notification_settings()
    times = _parse_times(raw)

    if not times:
        await update.message.reply_text(
            "❌ Format noto'g'ri.\n"
            f"{'Vergul bilan ' + str(count) + ' ta vaqt' if count > 1 else 'HH:MM'} kiriting\n"
            f"(masalan: {'05:50, 22:30' if count > 1 else '08:00'}):"
        )
        return ADMIN_NOTIF_TIME

    if len(times) != count:
        await update.message.reply_text(
            f"❌ {count} ta vaqt kerak, {len(times)} ta kiritildi.\n"
            f"(masalan: {'05:50, 22:30' if count == 2 else ', '.join(['HH:MM']*count)}):"
        )
        return ADMIN_NOTIF_TIME

    set_notification_times(times)

    # Reschedule all notification jobs
    try:
        import pytz
        from apscheduler.triggers.cron import CronTrigger
        scheduler = context.application.bot_data.get("scheduler")
        if scheduler:
            TZ = pytz.timezone("Asia/Tashkent")
            for i, t in enumerate(times):
                h, m = int(t.split(":")[0]), int(t.split(":")[1])
                try:
                    scheduler.reschedule_job(
                        f"daily_notifications_{i}",
                        CronTrigger(hour=h, minute=m, timezone=TZ),
                    )
                except Exception:
                    scheduler.add_job(
                        context.application.bot_data["_daily_notif_fn"],
                        CronTrigger(hour=h, minute=m, timezone=TZ),
                        id=f"daily_notifications_{i}",
                        replace_existing=True,
                    )
            logger.info(f"Notifications rescheduled: {times}")
    except Exception as e:
        logger.error(f"Reschedule error: {e}")

    times_str = " va ".join(times) if len(times) <= 2 else ", ".join(times)
    await update.message.reply_text(
        f"✅ Bildirishnoma vaqtlari o'zgartirildi!\n"
        f"Endi har kuni soat {times_str} da xabar yuboriladi (Toshkent vaqti)."
    )
    return ConversationHandler.END


def build_admin_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("admin", cmd_admin),
            CallbackQueryHandler(admin_user_mgmt_callback, pattern="^admin_user_mgmt$"),
            CallbackQueryHandler(admin_user_mgmt_callback, pattern="^admin_give_premium$"),
            CallbackQueryHandler(admin_ayah_photo_init,    pattern="^admin_ayah_photo$"),
            CallbackQueryHandler(admin_notif_time_init,    pattern="^admin_notif_time$"),
            CallbackQueryHandler(admin_notif_count_init,   pattern="^admin_notif_count$"),
            CallbackQueryHandler(admin_reject_init,        pattern="^admin_reject_"),
            CallbackQueryHandler(admin_ayah_photo_next,    pattern="^aphoto_nx_"),
        ],
        states={
            ADMIN_USER_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_user_search),
            ],
            ADMIN_AYAH_PHOTO_SURAH_SELECT: [
                CallbackQueryHandler(admin_ayah_photo_surah_selected, pattern="^aphoto_s_"),
                CallbackQueryHandler(admin_ayah_photo_surah_page,     pattern="^aphoto_sp_"),
            ],
            ADMIN_AYAH_PHOTO_AYAH_SELECT: [
                CallbackQueryHandler(admin_ayah_photo_ayah_selected, pattern="^aphoto_a_"),
                CallbackQueryHandler(admin_ayah_photo_ayah_page,     pattern="^aphoto_ap_"),
                CallbackQueryHandler(admin_ayah_photo_back_surah,    pattern="^aphoto_back_surah$"),
            ],
            ADMIN_AYAH_PHOTO_UPLOAD: [
                MessageHandler(filters.PHOTO, admin_ayah_photo_upload),
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: ADMIN_AYAH_PHOTO_UPLOAD),
            ],
            ADMIN_NOTIF_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_notif_time_set),
            ],
            ADMIN_NOTIF_COUNT: [
                CallbackQueryHandler(admin_notif_count_set, pattern="^admin_notif_count_"),
            ],
            ADMIN_REJECT_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_reject_reason),
            ],
        },
        fallbacks=[
            CommandHandler("start", lambda u, c: ConversationHandler.END),
            CallbackQueryHandler(admin_back_callback, pattern="^admin_back$"),
        ],
        allow_reentry=True,
        name="admin",
        per_message=False,
    )


async def _admin_message_interceptor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """group=-1 interceptor: catches admin's broadcast message or contact reply."""
    from telegram.ext import ApplicationHandlerStop
    if update.effective_user is None or update.effective_user.id != ADMIN_ID:
        return
    if not update.message:
        return

    # 1. Check if Admin is broadcasting
    if context.user_data.get("_bcast"):
        context.user_data.pop("_bcast", None)
        context.user_data["_bcast_from_chat"] = update.effective_chat.id
        context.user_data["_bcast_msg_id"]    = update.message.message_id
        users = get_all_users()
        await update.message.reply_text(
            f"📢 TASDIQLASH\n\n"
            f"Yuqoridagi xabar {len(users)} ta foydalanuvchiga yuboriladi.\n\n"
            f"Davom etasizmi?",
            reply_markup=broadcast_confirm_keyboard(),
        )
        raise ApplicationHandlerStop

    # 2. Check if Admin is replying to a user
    target_id = context.user_data.get("_reply_to")
    if target_id:
        context.user_data.pop("_reply_to", None)
        try:
            await context.bot.copy_message(
                chat_id      = target_id,
                from_chat_id = update.effective_chat.id,
                message_id   = update.message.message_id,
            )
            await context.bot.send_message(
                target_id,
                "📩 Admin javob berdi. Yana savol bo'lsa — /start → 📞 Murojaat"
            )
            await update.message.reply_text(f"✅ Javob {target_id} ga yuborildi.")
        except Exception as e:
            await update.message.reply_text(f"❌ Yuborishda xato: {e}")
        raise ApplicationHandlerStop


async def cmd_clear_xatms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: delete all xatm data from Firestore."""
    if update.effective_user.id != ADMIN_ID:
        return
    from firebase_config import db
    juzs  = list(db.collection("group_xatm_juzs").stream())
    xatms = list(db.collection("group_xatms").stream())
    for d in juzs:  d.reference.delete()
    for d in xatms: d.reference.delete()
    await update.message.reply_text(
        f"✅ Tozalandi: {len(xatms)} xatm, {len(juzs)} juz yozuvi o'chirildi.\n"
        "Endi foydalanuvchilar birinchi Xatm #1 ni boshlashi mumkin."
    )


def register_admin_callbacks(app):
    app.add_handler(CommandHandler("clearxatms", cmd_clear_xatms))
    # Users list with pagination + user detail
    app.add_handler(CallbackQueryHandler(admin_all_users_callback,  pattern="^admin_users_"))
    app.add_handler(CallbackQueryHandler(admin_user_detail_callback, pattern="^admin_udetail_"))
    # Broadcast
    app.add_handler(CallbackQueryHandler(admin_broadcast_init,    pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast_confirm, pattern="^broadcast_confirm$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast_cancel,  pattern="^broadcast_cancel$"))
    # group=-1: admin message interceptor (broadcast preview, contact reply)
    app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, _admin_message_interceptor),
        group=-1,
    )
    app.add_handler(CallbackQueryHandler(admin_stats_callback,            pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_back_callback,             pattern="^admin_back$"))
    app.add_handler(CallbackQueryHandler(admin_pending_requests_callback, pattern="^admin_pending_requests$"))
    app.add_handler(CallbackQueryHandler(admin_prem30_callback,           pattern="^admin_prem30_"))
    app.add_handler(CallbackQueryHandler(admin_prem7_callback,            pattern="^admin_prem7_"))
    app.add_handler(CallbackQueryHandler(admin_rem_prem_callback,         pattern="^admin_rem_prem_"))
