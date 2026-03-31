"""Admin panel handler — SQLite-based, replaces Firebase admin.py."""
import base64
import logging
from datetime import date, datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from src.database import db

logger = logging.getLogger(__name__)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_admin(user_id: int) -> bool:
    return user_id == db.ADMIN_ID


def _b64enc(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")


def _b64dec(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("ascii")).decode("utf-8")


def _admin_main_keyboard(pending_count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Barcha foydalanuvchilar", callback_data="admin:users:0")],
        [InlineKeyboardButton("👤 User boshqarish", callback_data="admin:user_search")],
        [InlineKeyboardButton("📢 Xabar yuborish (broadcast)", callback_data="admin:broadcast")],
        [InlineKeyboardButton(
            f"📋 Premium so'rovlar ({pending_count} ta kutilmoqda)",
            callback_data="admin:pending",
        )],
        [InlineKeyboardButton("💎 Premium berish/olish", callback_data="admin:give_premium")],
        [InlineKeyboardButton("📊 Batafsil statistika", callback_data="admin:stats")],
        [InlineKeyboardButton("📋 Kunlik hisobot", callback_data="admin:daily_report")],
    ])


def _back_to_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Admin panel", callback_data="admin:home")],
    ])


async def _send_admin_home(target, context, edit: bool = False):
    """Send or edit the main admin panel message."""
    try:
        total_users    = db.get_total_users()
        active_today   = db.get_active_today()
        new_today      = db.get_new_users_today()
        premium_count  = db.get_premium_count()
        total_memorized = db.get_total_memorized()
        pending        = db.get_pending_payments()
        pending_count  = len(pending)
    except Exception as e:
        logger.error("[Admin] stats error: %s", e)
        total_users = active_today = new_today = premium_count = total_memorized = pending_count = "?"

    text = (
        "🔐 *ADMIN PANEL*\n\n"
        "📊 *UMUMIY STATISTIKA*\n"
        "──────────────────────\n"
        f"👥 Jami: {total_users}\n"
        f"🟢 Bugun faol: {active_today}\n"
        f"🆕 Bugun yangi: {new_today}\n"
        f"💎 Premium: {premium_count}\n"
        f"📖 Yod olingan oyatlar: {total_memorized}\n"
        f"⏳ Kutilayotgan to'lovlar: {pending_count}"
    )
    keyboard = _admin_main_keyboard(pending_count if isinstance(pending_count, int) else 0)

    if edit:
        try:
            await target.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
            return
        except Exception:
            pass
    # Fall back to reply (or plain send for non-query targets)
    try:
        await target.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    except AttributeError:
        await target.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


# ── /admin command ─────────────────────────────────────────────────────────────

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not _is_admin(user.id):
        return
    try:
        await _send_admin_home(update.message, context, edit=False)
    except Exception as e:
        logger.error("[Admin] cmd_admin error: %s", e)
        await update.message.reply_text(f"❌ Xato: {e}")


# ── Callback dispatcher ────────────────────────────────────────────────────────

async def cb_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if not _is_admin(user.id):
        return

    data = query.data  # "admin:<action>" or "admin:<action>:<param>"
    parts = data.split(":", 2)  # max 3 parts to preserve base64 colons
    action = parts[1] if len(parts) > 1 else ""
    param  = parts[2] if len(parts) > 2 else ""

    try:
        if action == "home":
            await _send_admin_home(query, context, edit=True)

        elif action == "users":
            await _cb_users(query, context, int(param) if param else 0)

        elif action == "user_search":
            await _cb_user_search(query, context)

        elif action == "broadcast":
            await _cb_broadcast(query, context)

        elif action == "broadcast_confirm":
            await _cb_broadcast_confirm(query, context, param)

        elif action == "broadcast_cancel":
            await query.edit_message_text(
                "❌ Broadcast bekor qilindi.",
                parse_mode="Markdown",
                reply_markup=_back_to_admin_keyboard(),
            )

        elif action == "pending":
            await _cb_pending(query, context)

        elif action == "approve":
            await _cb_approve(query, context, int(param))

        elif action == "decline":
            await _cb_decline(query, context, int(param))

        elif action == "give_premium":
            await _cb_give_premium(query, context)

        elif action == "grant_30":
            await _cb_grant_user(query, context, int(param), months=1)

        elif action == "grant_7":
            await _cb_grant_user(query, context, int(param), months=None, days=7)

        elif action == "revoke":
            await _cb_revoke_user(query, context, int(param))

        elif action == "stats":
            await _cb_stats(query, context)

        elif action == "daily_report":
            await _cb_daily_report(query, context)

        else:
            await query.edit_message_text(
                f"⚠️ Noma'lum amal: `{action}`",
                parse_mode="Markdown",
                reply_markup=_back_to_admin_keyboard(),
            )

    except Exception as e:
        logger.error("[Admin] cb_admin action=%s error: %s", action, e)
        try:
            await query.edit_message_text(
                f"❌ Xato yuz berdi: `{e}`",
                parse_mode="Markdown",
                reply_markup=_back_to_admin_keyboard(),
            )
        except Exception:
            pass


# ── Feature: Paginated users list ─────────────────────────────────────────────

PAGE_SIZE = 10

async def _cb_users(query, context, page: int):
    try:
        all_users = db.get_all_users()
    except Exception as e:
        await query.edit_message_text(f"❌ Xato: {e}", reply_markup=_back_to_admin_keyboard())
        return

    total = len(all_users)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    chunk = all_users[start: start + PAGE_SIZE]

    lines = [f"👥 *Foydalanuvchilar* (sahifa {page + 1}/{total_pages}):\n"]
    for i, u in enumerate(chunk, start + 1):
        try:
            gam = db.get_gamification(u["id"])
            xp     = gam["total_xp"]     if gam else 0
            streak = gam["current_streak"] if gam else 0
        except Exception:
            xp = streak = 0
        name = u["name"] or "—"
        lines.append(f"{i}. {name} — {xp} XP 🔥{streak}")

    text = "\n".join(lines)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"admin:users:{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"admin:users:{page + 1}"))

    keyboard_rows = []
    if nav_buttons:
        keyboard_rows.append(nav_buttons)
    keyboard_rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin:home")])

    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
    )


# ── Feature: User search ───────────────────────────────────────────────────────

async def _cb_user_search(query, context):
    db.ensure_settings(query.from_user.id)
    db.update_settings(query.from_user.id, awaiting_input="admin_user_search")
    await query.edit_message_text(
        "👤 *User qidirish*\n\nFoydalanuvchi ID raqamini kiriting:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Bekor qilish", callback_data="admin:home")],
        ]),
    )


async def _show_user_info(send_fn, admin_id: int, target_id: int):
    """Fetch user info and send/edit the message via send_fn(text, keyboard)."""
    user = db.get_user(target_id)
    if not user:
        await send_fn(
            f"❌ User topilmadi: `{target_id}`",
            InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin:home")]]),
        )
        return

    gam     = db.get_gamification(target_id)
    premium = db.get_premium_info(target_id)
    is_prem = db.is_premium(target_id)

    xp     = gam["total_xp"]      if gam else 0
    streak = gam["current_streak"] if gam else 0
    league = gam["league"]         if gam else "—"

    if is_prem and premium:
        prem_text = f"✅ Ha (tugash: {str(premium['expires_at'])[:10]})"
    elif premium and not is_prem:
        prem_text = "❌ Muddati tugagan"
    else:
        prem_text = "❌ Yo'q"

    created = str(user["created_at"])[:10] if user["created_at"] else "—"

    text = (
        f"👤 *Foydalanuvchi:* {user['name']}\n"
        f"🆔 *ID:* `{target_id}`\n"
        f"📅 *Ro'yxatdan:* {created}\n"
        f"⭐ *XP:* {xp}\n"
        f"🔥 *Streak:* {streak}\n"
        f"🏆 *Liga:* {league}\n"
        f"💎 *Premium:* {prem_text}"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💎 30 kun premium", callback_data=f"admin:grant_30:{target_id}"),
            InlineKeyboardButton("💎 7 kun",           callback_data=f"admin:grant_7:{target_id}"),
        ],
        [InlineKeyboardButton("❌ Premiumni o'chirish", callback_data=f"admin:revoke:{target_id}")],
        [InlineKeyboardButton("🔙 Orqaga",              callback_data="admin:home")],
    ])

    await send_fn(text, keyboard)


# ── Feature: Broadcast ────────────────────────────────────────────────────────

async def _cb_broadcast(query, context):
    db.ensure_settings(query.from_user.id)
    db.update_settings(query.from_user.id, awaiting_input="admin_broadcast")
    await query.edit_message_text(
        "📢 *Broadcast*\n\nBarcha foydalanuvchilarga yubormoqchi bo'lgan xabarni kiriting:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Bekor qilish", callback_data="admin:broadcast_cancel")],
        ]),
    )


async def _cb_broadcast_confirm(query, context, encoded_text: str):
    try:
        text = _b64dec(encoded_text)
    except Exception:
        await query.edit_message_text("❌ Xabar dekodlanmadi.", reply_markup=_back_to_admin_keyboard())
        return

    try:
        all_users = db.get_all_users()
    except Exception as e:
        await query.edit_message_text(f"❌ Foydalanuvchilar olinmadi: {e}", reply_markup=_back_to_admin_keyboard())
        return

    total = len(all_users)
    sent = failed = 0

    status_msg = await query.edit_message_text(
        f"📢 Broadcast boshlanmoqda... 0/{total}",
        parse_mode="Markdown",
    )

    for u in all_users:
        try:
            await context.bot.send_message(
                chat_id=u["id"],
                text=text,
                parse_mode="Markdown",
            )
            sent += 1
        except Exception:
            failed += 1

        # Update status every 20 users
        if (sent + failed) % 20 == 0:
            try:
                await status_msg.edit_text(
                    f"📢 Broadcast davom etmoqda... {sent + failed}/{total}",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    summary = (
        f"✅ *Broadcast yakunlandi*\n\n"
        f"📤 Yuborildi: {sent}\n"
        f"❌ Xato: {failed}\n"
        f"👥 Jami: {total}"
    )
    try:
        await status_msg.edit_text(summary, parse_mode="Markdown", reply_markup=_back_to_admin_keyboard())
    except Exception:
        await query.message.reply_text(summary, parse_mode="Markdown", reply_markup=_back_to_admin_keyboard())


# ── Feature: Premium requests ─────────────────────────────────────────────────

async def _cb_pending(query, context):
    try:
        pending = db.get_pending_payments()
    except Exception as e:
        await query.edit_message_text(f"❌ Xato: {e}", reply_markup=_back_to_admin_keyboard())
        return

    if not pending:
        await query.edit_message_text(
            "✅ Kutilayotgan to'lov so'rovlari yo'q.",
            parse_mode="Markdown",
            reply_markup=_back_to_admin_keyboard(),
        )
        return

    await query.edit_message_text(
        f"📋 *Kutilayotgan so'rovlar:* {len(pending)} ta\n\nHar bir so'rov uchun rasm yuboriladi.",
        parse_mode="Markdown",
        reply_markup=_back_to_admin_keyboard(),
    )

    for req in pending:
        req_id  = req["id"]
        user_id = req["user_id"]
        name    = req["name"] or "—"
        caption = (
            f"👤 *{name}*\n"
            f"🆔 ID: `{user_id}`\n"
            f"📋 So'rov #{req_id}"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"admin:approve:{req_id}"),
                InlineKeyboardButton("❌ Rad etish",  callback_data=f"admin:decline:{req_id}"),
            ],
        ])
        try:
            await context.bot.send_photo(
                chat_id=query.from_user.id,
                photo=req["photo_file_id"],
                caption=caption,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except Exception as e:
            try:
                await context.bot.send_message(
                    chat_id=query.from_user.id,
                    text=caption + f"\n\n⚠️ Rasm yuborilmadi: {e}",
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            except Exception:
                pass


async def _cb_approve(query, context, req_id: int):
    try:
        req = db.get_payment_request(req_id)
        if not req:
            await query.edit_message_caption(
                caption=f"⚠️ So'rov #{req_id} topilmadi.",
                reply_markup=_back_to_admin_keyboard(),
            )
            return

        user_id = req["user_id"]
        db.grant_premium(user_id, months=1)
        db.update_payment_request(req_id, status="approved")

        # Notify user
        target_user = db.get_user(user_id)
        lang = target_user["language"] if target_user else "uz"
        msg = (
            "✅ *To'lovingiz tasdiqlandi!* 🎉\n\n"
            "💎 Premium faollashtirildi — 30 kun!\n\n"
            "Barcha premium imkoniyatlardan foydalaning."
            if lang == "uz" else
            "✅ *Your payment has been approved!* 🎉\n\n"
            "💎 Premium activated — 30 days!\n\n"
            "Enjoy all premium features."
        )
        try:
            await context.bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")
        except Exception:
            pass

        await query.edit_message_caption(
            caption=f"✅ Tasdiqlandi — #{req_id} ({user_id})",
            reply_markup=_back_to_admin_keyboard(),
        )

    except Exception as e:
        logger.error("[Admin] approve error req_id=%s: %s", req_id, e)
        try:
            await query.edit_message_caption(
                caption=f"❌ Xato: {e}",
                reply_markup=_back_to_admin_keyboard(),
            )
        except Exception:
            pass


async def _cb_decline(query, context, req_id: int):
    try:
        req = db.get_payment_request(req_id)
        if not req:
            await query.edit_message_caption(
                caption=f"⚠️ So'rov #{req_id} topilmadi.",
                reply_markup=_back_to_admin_keyboard(),
            )
            return

        user_id = req["user_id"]
        # Store awaiting_input so settings.py handle_text_input can process the reason
        db.ensure_settings(query.from_user.id)
        db.update_settings(query.from_user.id, awaiting_input=f"decline_reason:{req_id}:{user_id}")

        await query.edit_message_caption(
            caption=(
                f"❌ *Rad etish — so'rov #{req_id}*\n\n"
                f"Rad etish sababini kiriting (matn xabar sifatida yuboring):"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Bekor qilish", callback_data="admin:home")],
            ]),
        )

    except Exception as e:
        logger.error("[Admin] decline error req_id=%s: %s", req_id, e)
        try:
            await query.edit_message_caption(
                caption=f"❌ Xato: {e}",
                reply_markup=_back_to_admin_keyboard(),
            )
        except Exception:
            pass


# ── Feature: Direct premium grant ─────────────────────────────────────────────

async def _cb_give_premium(query, context):
    db.ensure_settings(query.from_user.id)
    db.update_settings(query.from_user.id, awaiting_input="admin_give_premium")
    await query.edit_message_text(
        "💎 *Premium berish*\n\nFoydalanuvchi ID raqamini kiriting:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Bekor qilish", callback_data="admin:home")],
        ]),
    )


async def _cb_grant_user(query, context, target_id: int, months: int = 1, days: int = None):
    try:
        if days and days != 30:
            from src.database.db import get_conn
            now = datetime.utcnow()
            exp = (now + timedelta(days=days)).isoformat()
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO premium(user_id,active,expires_at,granted_at) VALUES(?,1,?,?) "
                    "ON CONFLICT(user_id) DO UPDATE SET active=1,expires_at=excluded.expires_at,"
                    "granted_at=excluded.granted_at",
                    (target_id, exp, now.isoformat()),
                )
            label = f"{days} kun"
        else:
            db.grant_premium(target_id, months=months)
            label = f"{months * 30} kun"

        user = db.get_user(target_id)
        name = user["name"] if user else str(target_id)

        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    f"💎 *Premium faollashtirildi!*\n\n"
                    f"Muddat: *{label}*\n\n"
                    "Barcha premium imkoniyatlardan foydalaning."
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass

        await query.edit_message_text(
            f"✅ *{name}* (`{target_id}`) ga {label} premium berildi.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 User ma'lumoti", callback_data=f"admin:user_search")],
                [InlineKeyboardButton("🔙 Admin panel",    callback_data="admin:home")],
            ]),
        )

    except Exception as e:
        logger.error("[Admin] grant_user error target=%s: %s", target_id, e)
        await query.edit_message_text(
            f"❌ Xato: {e}",
            parse_mode="Markdown",
            reply_markup=_back_to_admin_keyboard(),
        )


async def _cb_revoke_user(query, context, target_id: int):
    try:
        db.revoke_premium(target_id)
        user = db.get_user(target_id)
        name = user["name"] if user else str(target_id)

        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="ℹ️ Sizning premium obunangiz bekor qilindi.",
                parse_mode="Markdown",
            )
        except Exception:
            pass

        await query.edit_message_text(
            f"✅ *{name}* (`{target_id}`) premiumdan mahrum qilindi.",
            parse_mode="Markdown",
            reply_markup=_back_to_admin_keyboard(),
        )

    except Exception as e:
        logger.error("[Admin] revoke_user error target=%s: %s", target_id, e)
        await query.edit_message_text(
            f"❌ Xato: {e}",
            parse_mode="Markdown",
            reply_markup=_back_to_admin_keyboard(),
        )


# ── Feature: Detailed stats ────────────────────────────────────────────────────

async def _cb_stats(query, context):
    try:
        total_users     = db.get_total_users()
        active_today    = db.get_active_today()
        new_today       = db.get_new_users_today()
        premium_count   = db.get_premium_count()
        total_memorized = db.get_total_memorized()
        pending         = db.get_pending_payments()
        top_users       = db.get_leaderboard(limit=10)
    except Exception as e:
        await query.edit_message_text(f"❌ Xato: {e}", reply_markup=_back_to_admin_keyboard())
        return

    top_lines = []
    for i, u in enumerate(top_users, 1):
        name   = u["name"] if isinstance(u, dict) else dict(u).get("name", "—")
        xp     = u["total_xp"] if isinstance(u, dict) else dict(u).get("total_xp", 0)
        streak = u["current_streak"] if isinstance(u, dict) else dict(u).get("current_streak", 0)
        top_lines.append(f"  {i}. {name} — {xp} XP 🔥{streak}")

    top_text = "\n".join(top_lines) if top_lines else "  (hali yo'q)"

    text = (
        f"📊 *BATAFSIL STATISTIKA*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 *Foydalanuvchilar:*\n"
        f"  • Jami: {total_users}\n"
        f"  • Bugun faol: {active_today}\n"
        f"  • Bugun yangi: {new_today}\n"
        f"  • Premium: {premium_count}\n\n"
        f"📖 *Yod olish:*\n"
        f"  • Jami yod olingan oyatlar: {total_memorized}\n\n"
        f"⏳ *To'lovlar:*\n"
        f"  • Kutilayotgan: {len(pending)}\n\n"
        f"🏆 *Top 10 Foydalanuvchi:*\n{top_text}"
    )

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=_back_to_admin_keyboard(),
    )


# ── Feature: Daily report ──────────────────────────────────────────────────────

async def _cb_daily_report(query, context):
    try:
        today           = date.today().isoformat()
        total_users     = db.get_total_users()
        active_today    = db.get_active_today()
        total_memorized = db.get_total_memorized()
        new_today       = db.get_new_users_today()
        premium_count   = db.get_premium_count()
        top_users       = db.get_leaderboard(limit=5)

        try:
            xatm_stats = db.get_xatm_stats()
        except Exception:
            xatm_stats = {}

        top_lines = []
        for i, u in enumerate(top_users, 1):
            row    = dict(u) if not isinstance(u, dict) else u
            name   = row.get("name", "—")
            xp     = row.get("total_xp", 0)
            streak = row.get("current_streak", 0)
            top_lines.append(f"  {i}. {name} — {xp} XP 🔥{streak}")
        top_text = "\n".join(top_lines) if top_lines else "  (hali yo'q)"

        report = (
            f"📊 *Kunlik Hisobot — {today}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 *Foydalanuvchilar:*\n"
            f"  • Jami: {total_users}\n"
            f"  • Bugun faol: {active_today}\n"
            f"  • Bugun yangi: {new_today}\n"
            f"  • Premium: {premium_count}\n\n"
            f"📖 *Yod olish:*\n"
            f"  • Jami yod olingan oyatlar: {total_memorized}\n\n"
            f"👥 *Jamoaviy Xatm:*\n"
            f"  • Yakunlangan Xatmlar: {xatm_stats.get('total_xatms', 0)}\n"
            f"  • Jami ishtirokchilar: {xatm_stats.get('total_participants', 0)}\n\n"
            f"🏆 *Top 5 Foydalanuvchi:*\n{top_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        await query.edit_message_text(
            report,
            parse_mode="Markdown",
            reply_markup=_back_to_admin_keyboard(),
        )

    except Exception as e:
        logger.error("[Admin] daily_report error: %s", e)
        await query.edit_message_text(
            f"❌ Hisobot xatosi: {e}",
            parse_mode="Markdown",
            reply_markup=_back_to_admin_keyboard(),
        )


# ── Text input handler (called from settings.py's handle_text_input) ──────────

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Handle admin-specific awaiting_input states.
    Returns True if the input was consumed (so settings.py can skip further processing).
    """
    user = update.effective_user
    if not _is_admin(user.id):
        return False

    settings = db.get_settings(user.id)
    if not settings or not settings["awaiting_input"]:
        return False

    awaiting = settings["awaiting_input"]
    text     = update.message.text.strip()

    # ── Broadcast preview ────────────────────────────────────────────────────
    if awaiting == "admin_broadcast":
        db.update_settings(user.id, awaiting_input=None)
        encoded = _b64enc(text)
        preview = (
            f"📢 *Broadcast preview:*\n\n"
            f"─────────────────\n"
            f"{text}\n"
            f"─────────────────\n\n"
            f"Barcha foydalanuvchilarga yuborilsinmi?"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Ha, yuborish",    callback_data=f"admin:broadcast_confirm:{encoded}"),
                InlineKeyboardButton("❌ Bekor qilish", callback_data="admin:broadcast_cancel"),
            ],
        ])
        await update.message.reply_text(preview, parse_mode="Markdown", reply_markup=keyboard)
        return True

    # ── User search ───────────────────────────────────────────────────────────
    if awaiting == "admin_user_search":
        db.update_settings(user.id, awaiting_input=None)
        try:
            target_id = int(text)
        except ValueError:
            # Try searching by name
            try:
                all_users = db.get_all_users()
                matches = [u for u in all_users if text.lower() in (u["name"] or "").lower()]
                if not matches:
                    await update.message.reply_text(
                        f"❌ `{text}` ID yoki nom bo'yicha topilmadi.",
                        parse_mode="Markdown",
                        reply_markup=_back_to_admin_keyboard(),
                    )
                    return True
                if len(matches) == 1:
                    target_id = matches[0]["id"]
                else:
                    lines = [f"🔍 *{len(matches)} ta natija:*\n"]
                    for m in matches[:10]:
                        lines.append(f"• {m['name']} — ID: `{m['id']}`")
                    await update.message.reply_text(
                        "\n".join(lines) + "\n\nAniq ID kiriting:",
                        parse_mode="Markdown",
                        reply_markup=_back_to_admin_keyboard(),
                    )
                    return True
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Qidirishda xato: {e}",
                    parse_mode="Markdown",
                    reply_markup=_back_to_admin_keyboard(),
                )
                return True

        async def _send(txt, kb):
            await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=kb)

        await _show_user_info(_send, user.id, target_id)
        return True

    # ── Direct premium grant ─────────────────────────────────────────────────
    if awaiting == "admin_give_premium":
        db.update_settings(user.id, awaiting_input=None)
        try:
            target_id = int(text)
        except ValueError:
            await update.message.reply_text(
                f"❌ Noto'g'ri ID: `{text}`. Raqam kiriting.",
                parse_mode="Markdown",
                reply_markup=_back_to_admin_keyboard(),
            )
            return True

        try:
            target_user = db.get_user(target_id)
            if not target_user:
                await update.message.reply_text(
                    f"❌ User topilmadi: `{target_id}`",
                    parse_mode="Markdown",
                    reply_markup=_back_to_admin_keyboard(),
                )
                return True

            db.grant_premium(target_id, months=1)

            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=(
                        "💎 *Premium faollashtirildi!*\n\n"
                        "Muddat: *30 kun*\n\n"
                        "Barcha premium imkoniyatlardan foydalaning."
                    ),
                    parse_mode="Markdown",
                )
            except Exception:
                pass

            name = target_user["name"] or str(target_id)
            await update.message.reply_text(
                f"✅ *{name}* (`{target_id}`) ga 30 kunlik premium berildi.",
                parse_mode="Markdown",
                reply_markup=_back_to_admin_keyboard(),
            )
        except Exception as e:
            logger.error("[Admin] give_premium text error target=%s: %s", target_id, e)
            await update.message.reply_text(
                f"❌ Xato: {e}",
                parse_mode="Markdown",
                reply_markup=_back_to_admin_keyboard(),
            )
        return True

    return False


# ── Registration ───────────────────────────────────────────────────────────────

def register(app):
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CallbackQueryHandler(cb_admin, pattern=r"^admin:"))
