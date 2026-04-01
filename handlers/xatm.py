"""
xatm.py — Jamoaviy Xatm (Group Quran Reading) handler.

Juz states (from user's perspective):
  unassigned  → plain number, clickable if recruiting
  assigned    → 🟡 (mine, not done) — click to mark done OR unassign
  completed   → ✅ (mine, done)     — click to undo (back to assigned)
  taken       → 🔒 (someone else's assigned)
  other done  → ✅ (someone else's completed)
"""
import math
import logging
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from services.firebase_service import (
    get_xatm_stats, get_or_create_recruiting_xatm, create_xatm,
    get_xatm, get_xatm_juzs, assign_xatm_juz, complete_xatm_juz,
    unassign_xatm_juz, uncomplete_xatm_juz,
    check_and_update_xatm_status, get_user, update_user,
    get_xatm_ranking, get_user_xatms,
)

import asyncio
from handlers.achievements import check_and_notify_achievements

logger = logging.getLogger(__name__)

BOT_USERNAME = "quranyodla_bot"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fmt_time(secs: int) -> str:
    if secs <= 0:
        return "—"
    days = math.floor(secs / 86400)
    hrs  = math.floor((secs % 86400) / 3600)
    mins = math.floor((secs % 3600) / 60)
    res  = []
    if days > 0: res.append(f"{days}k")
    if hrs  > 0: res.append(f"{hrs}s")
    if mins > 0 and days == 0: res.append(f"{mins}d")
    return " ".join(res) if res else "< 1d"


def _status_label(status: str) -> str:
    return {
        "recruiting": "🟡 Ro'yxat ochiq",
        "active":     "🟢 Faol",
        "completed":  "✅ Yakunlangan",
    }.get(status, status)


# ─── Dashboard ────────────────────────────────────────────────────────────────

def _dashboard_text(stats: dict) -> str:
    avg     = _fmt_time(int(stats.get("avg_seconds", 0)))
    fastest = _fmt_time(int(stats.get("fastest_seconds", 0)))
    longest = _fmt_time(int(stats.get("longest_seconds", 0)))
    return (
        "👥 *Jamoaviy Xatm*\n\n"
        f"📖 Yakunlangan xatmlar: *{stats.get('total_xatms', 0)}*\n"
        f"👤 Jami ishtirokchilar: *{stats.get('total_participants', 0)}*\n\n"
        f"⏱ O'rtacha vaqt: *{avg}*\n"
        f"⚡ Eng tez: *{fastest}*\n"
        f"🐢 Eng uzun: *{longest}*\n\n"
        "Jamoaviy xatmga qo'shiling 👇"
    )


def _dashboard_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤝 Xatmga Qo'shilish",  callback_data="xatm:join")],
        [InlineKeyboardButton("📋 Mening Xatmlarim",   callback_data="xatm:myxatms")],
    ])


# ─── My Xatms View ────────────────────────────────────────────────────────────

def _my_xatms_text(xatms_info: list) -> str:
    if not xatms_info:
        return "📋 *Mening Xatmlarim*\n\nSiz hali hech bir xatmga qo'shilmagansiz."
    lines = ["📋 *Mening Xatmlarim*\n"]
    for info in xatms_info:
        xatm   = info["xatm"]
        juzs   = info["juzs"]
        num    = xatm.get("xatm_number", "?")
        status = _status_label(xatm["status"])
        done   = sum(1 for j in juzs if j["status"] == "completed")
        nums   = sorted(j["juz_number"] for j in juzs)
        nums_s = ", ".join(map(str, nums)) if nums else "—"
        lines.append(f"📖 *Xatm #{num}* — {status}")
        lines.append(f"   Juzlar: {nums_s} ({done}/{len(juzs)} ✅)\n")
    return "\n".join(lines)


def _my_xatms_keyboard(xatms_info: list) -> InlineKeyboardMarkup:
    rows = []
    for info in xatms_info:
        xatm = info["xatm"]
        num  = xatm.get("xatm_number", "?")
        xid  = xatm["xatm_id"]
        rows.append([InlineKeyboardButton(
            f"📖 Xatm #{num} →", callback_data=f"xatm:view:{xid}"
        )])
    rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="xatm:dashboard")])
    return InlineKeyboardMarkup(rows)


# ─── Xatm View ────────────────────────────────────────────────────────────────

def _xatm_view_text(xatm: dict, juzs: list, user_id: int) -> str:
    status    = xatm["status"]
    xatm_num  = xatm.get("xatm_number", "?")
    total     = len(juzs)
    completed = sum(1 for j in juzs if j["status"] == "completed")
    my_juzs   = [j for j in juzs if j["user_id"] == user_id]
    my_done   = sum(1 for j in my_juzs if j["status"] == "completed")

    lines = [
        f"📖 *Xatm #{xatm_num}*",
        f"Holat: {_status_label(status)}",
        f"Juzlar: *{total}/30* band | *{completed}/30* o'qildi",
    ]
    if my_juzs:
        my_nums = sorted(j["juz_number"] for j in my_juzs)
        lines.append(
            f"Sizning juzlaringiz: *{', '.join(map(str, my_nums))}* "
            f"({my_done}/{len(my_juzs)} ✅)"
        )
    lines += [
        "",
        "🟡 = sizniki (o'qilmagan)   ✅ = o'qildi",
        "🔒 = band   · raqam = bo'sh",
        "",
        "Juz tugmasi: bir marta bosing — o'qib bo'ldim ✅",
        "Yana bosing — bekor qilish (🟡 ga qaytadi)",
    ]
    return "\n".join(lines)


def _xatm_keyboard(xatm: dict, juz_map: dict, user_id: int) -> InlineKeyboardMarkup:
    xatm_id = xatm["xatm_id"]
    status  = xatm["status"]
    rows    = []

    for row_idx in range(5):
        row = []
        for col_idx in range(1, 7):
            j_num = row_idx * 6 + col_idx
            state = juz_map.get(j_num)
            label   = str(j_num)
            cb_data = "xatm:void"

            if state:
                if state["user_id"] == user_id:
                    if state["status"] == "completed":
                        # Mine + done → ✅, click to undo
                        label   = f"{j_num}✅"
                        cb_data = f"xatm:undone:{xatm_id}:{j_num}"
                    else:
                        # Mine + assigned → 🟡, click to mark done
                        label   = f"{j_num}🟡"
                        cb_data = f"xatm:done:{xatm_id}:{j_num}"
                else:
                    # Someone else's
                    label   = f"{j_num}✅" if state["status"] == "completed" else f"{j_num}🔒"
                    cb_data = "xatm:void"
            else:
                # Unassigned
                if status == "recruiting":
                    cb_data = f"xatm:take:{xatm_id}:{j_num}"

            row.append(InlineKeyboardButton(label, callback_data=cb_data))
        rows.append(row)

    # Action buttons
    deep_link = f"https://t.me/{BOT_USERNAME}?start=xatm_{xatm_id}"
    rows.append([
        InlineKeyboardButton("👥 Ishtirokchilar", callback_data=f"xatm:members:{xatm_id}"),
        InlineKeyboardButton("🏆 Reyting",        callback_data=f"xatm:rank:{xatm_id}"),
    ])
    rows.append([InlineKeyboardButton(
        "🔗 Do'stlarga Ulashish",
        url=f"https://t.me/share/url?url={deep_link}&text=Jamoaviy+Xatmga+qo%27shiling%21"
    )])
    if len(juz_map) == 30:
        rows.append([InlineKeyboardButton(
            "➕ Keyingi Xatmni Boshlash", callback_data="xatm:join"
        )])
    rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="xatm:dashboard")])
    return InlineKeyboardMarkup(rows)


# ─── Members View ─────────────────────────────────────────────────────────────

def _display_name(uid: int, viewer_uid: int) -> str:
    """Returns name or 'Anonim' based on user's xatm_anonymous setting."""
    user = get_user(uid)
    if not user:
        return "Foydalanuvchi"
    if uid == viewer_uid:
        # Always show own name to yourself
        return user.get("full_name", str(uid))
    if user.get("xatm_anonymous", False):
        return "🫥 Anonim"
    return user.get("full_name", str(uid))


def _members_text(xatm: dict, juzs: list, viewer_uid: int) -> str:
    xatm_num = xatm.get("xatm_number", "?")
    by_user: dict = {}
    for j in juzs:
        by_user.setdefault(j["user_id"], []).append(j)

    lines = [f"👥 *Xatm #{xatm_num} — Ishtirokchilar*\n"]
    if not by_user:
        lines.append("Hali hech kim qo'shilmagan.")
    else:
        for uid, user_juzs in sorted(by_user.items()):
            name = _display_name(uid, viewer_uid)
            done = sum(1 for j in user_juzs if j["status"] == "completed")
            nums = sorted(j["juz_number"] for j in user_juzs)
            lines.append(f"👤 *{name}*")
            lines.append(f"   {', '.join(map(str, nums))} ({done}/{len(user_juzs)} ✅)")
    return "\n".join(lines)


def _members_keyboard(xatm_id: str, is_anonymous: bool) -> InlineKeyboardMarkup:
    toggle_label = "👁 Ismni Ko'rsatish" if is_anonymous else "🫥 Ismni Yashirish"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_label, callback_data=f"xatm:privacy:{xatm_id}")],
        [InlineKeyboardButton("🔙 Orqaga",  callback_data=f"xatm:view:{xatm_id}")],
    ])


# ─── Ranking View ─────────────────────────────────────────────────────────────

def _ranking_text(xatm: dict, ranking: list, viewer_uid: int) -> str:
    xatm_num = xatm.get("xatm_number", "?")
    lines = [f"🏆 *Xatm #{xatm_num} — Reyting*\n"]
    if not ranking:
        lines.append("Hali hech kim juz o'qib bo'lmagan.")
    else:
        medals = ["🥇", "🥈", "🥉"]
        for i, entry in enumerate(ranking):
            medal = medals[i] if i < 3 else f"{i+1}."
            name  = _display_name(entry["user_id"], viewer_uid)
            lines.append(
                f"{medal} *{name}* — "
                f"{entry['completed']}/{entry['total']} ✅ "
                f"({_fmt_time(entry.get('total_seconds', 0))})"
            )
    return "\n".join(lines)


def _ranking_keyboard(xatm_id: str, is_anonymous: bool) -> InlineKeyboardMarkup:
    toggle_label = "👁 Ismni Ko'rsatish" if is_anonymous else "🫥 Ismni Yashirish"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_label, callback_data=f"xatm:privacy:{xatm_id}")],
        [InlineKeyboardButton("🔙 Orqaga",  callback_data=f"xatm:view:{xatm_id}")],
    ])


# ─── Core helpers ─────────────────────────────────────────────────────────────

async def _edit(query, text: str, kb: InlineKeyboardMarkup):
    try:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        if "Message is not modified" not in str(e):
            logger.warning(f"xatm _edit error: {e}")


async def _refresh_xatm_view(query, xatm_id: str, user_id: int, alert: Optional[str] = None):
    xatm = get_xatm(xatm_id)
    if not xatm:
        await query.answer("Xatm topilmadi.", show_alert=True)
        return
    juzs    = get_xatm_juzs(xatm_id)
    juz_map = {j["juz_number"]: j for j in juzs}
    text    = _xatm_view_text(xatm, juzs, user_id)
    kb      = _xatm_keyboard(xatm, juz_map, user_id)
    await query.answer(alert or "", show_alert=bool(alert))
    await _edit(query, text, kb)


async def _notify_participants(xatm_id: str, text: str, bot):
    juzs         = get_xatm_juzs(xatm_id)
    participants = set(j["user_id"] for j in juzs)
    for uid in participants:
        try:
            await bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
        except Exception:
            pass


# ─── Main Handlers ────────────────────────────────────────────────────────────

async def show_xatm_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_xatm_stats()
    await update.message.reply_text(
        _dashboard_text(stats),
        parse_mode="Markdown",
        reply_markup=_dashboard_keyboard(update.effective_user.id),
    )


async def cb_xatm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    parts   = query.data.split(":")
    action  = parts[1] if len(parts) > 1 else ""

    if action == "dashboard":
        await query.answer()
        stats = get_xatm_stats()
        await _edit(query, _dashboard_text(stats), _dashboard_keyboard(user_id))

    elif action == "myxatms":
        await query.answer()
        xatms_info = get_user_xatms(user_id)
        await _edit(query, _my_xatms_text(xatms_info), _my_xatms_keyboard(xatms_info))

    elif action == "join":
        xatm_id = get_or_create_recruiting_xatm()
        if xatm_id is None:
            xatm_id = create_xatm(creator_id=user_id)
        await _refresh_xatm_view(query, xatm_id, user_id)

    elif action == "view":
        xatm_id = parts[2]
        await _refresh_xatm_view(query, xatm_id, user_id)

    elif action == "take":
        xatm_id = parts[2]
        juz     = int(parts[3])
        ok      = assign_xatm_juz(xatm_id, juz, user_id)
        alert   = "⚠️ Bu juz allaqachon olingan!" if not ok else None
        new_st  = check_and_update_xatm_status(xatm_id) if ok else None
        await _refresh_xatm_view(query, xatm_id, user_id, alert=alert)
        if ok:
            asyncio.ensure_future(check_and_notify_achievements(context.bot, user_id, {"xatm_joined": True}))
        if new_st == "active":
            xatm = get_xatm(xatm_id)
            num  = xatm.get("xatm_number", "?") if xatm else "?"
            # Auto-create the next xatm so it's ready
            create_xatm()
            await _notify_participants(xatm_id,
                f"🚀 *Xatm #{num} boshlandi!*\n"
                f"Barcha 30 juz taqsimlandi. O'qishni boshlang!\n\n"
                f"Keyingi Xatm #{int(num)+1 if str(num).isdigit() else '?'} ham ochildi 🎉",
                context.bot)

    elif action == "done":
        # Mark juz as completed
        xatm_id = parts[2]
        juz     = int(parts[3])
        complete_xatm_juz(xatm_id, juz, user_id)
        new_st  = check_and_update_xatm_status(xatm_id)
        await _refresh_xatm_view(query, xatm_id, user_id)
        asyncio.ensure_future(check_and_notify_achievements(context.bot, user_id, {"xatm_completed": new_st == "completed"}))
        if new_st == "completed":
            xatm = get_xatm(xatm_id)
            num  = xatm.get("xatm_number", "?") if xatm else "?"
            await _notify_participants(xatm_id,
                f"🎉 *Xatm #{num} yakunlandi!*\n"
                "Barcha ishtirokchilar juzlarini o'qib bo'ldi. Alloh qabul qilsin! 🤲",
                context.bot)

    elif action == "undone":
        # Undo completion → back to assigned (🟡)
        xatm_id = parts[2]
        juz     = int(parts[3])
        uncomplete_xatm_juz(xatm_id, juz, user_id)
        await _refresh_xatm_view(query, xatm_id, user_id)

    elif action == "members":
        xatm_id    = parts[2]
        await query.answer()
        xatm = get_xatm(xatm_id)
        if not xatm:
            return
        juzs       = get_xatm_juzs(xatm_id)
        viewer     = get_user(user_id)
        is_anon    = viewer.get("xatm_anonymous", False) if viewer else False
        await _edit(query, _members_text(xatm, juzs, user_id), _members_keyboard(xatm_id, is_anon))

    elif action == "rank":
        xatm_id = parts[2]
        await query.answer()
        xatm    = get_xatm(xatm_id)
        ranking = get_xatm_ranking(xatm_id)
        if not xatm:
            return
        viewer  = get_user(user_id)
        is_anon = viewer.get("xatm_anonymous", False) if viewer else False
        await _edit(query, _ranking_text(xatm, ranking, user_id), _ranking_keyboard(xatm_id, is_anon))

    elif action == "privacy":
        xatm_id = parts[2]
        viewer  = get_user(user_id)
        is_anon = viewer.get("xatm_anonymous", False) if viewer else False
        update_user(user_id, {"xatm_anonymous": not is_anon})
        # Refresh members view with new setting
        xatm = get_xatm(xatm_id)
        if not xatm:
            await query.answer()
            return
        juzs    = get_xatm_juzs(xatm_id)
        msg     = "🫥 Ismingiz yashirildi" if not is_anon else "👁 Ismingiz ko'rinadi"
        await query.answer(msg, show_alert=True)
        await _edit(query, _members_text(xatm, juzs, user_id), _members_keyboard(xatm_id, not is_anon))

    elif action == "void":
        await query.answer()


async def show_xatm_dashboard_by_id(update: Update, context: ContextTypes.DEFAULT_TYPE, xatm_id: str):
    """Called from /start deep link."""
    xatm = get_xatm(xatm_id)
    if not xatm:
        await update.message.reply_text("⚠️ Xatm topilmadi yoki yakunlangan.")
        return
    user_id = update.effective_user.id
    juzs    = get_xatm_juzs(xatm_id)
    juz_map = {j["juz_number"]: j for j in juzs}
    text    = _xatm_view_text(xatm, juzs, user_id)
    kb      = _xatm_keyboard(xatm, juz_map, user_id)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


def register_xatm_handlers(app):
    app.add_handler(MessageHandler(filters.Regex("^👥 Jamoaviy Xatm$"), show_xatm_dashboard))
    app.add_handler(CallbackQueryHandler(cb_xatm, pattern=r"^xatm:"))
