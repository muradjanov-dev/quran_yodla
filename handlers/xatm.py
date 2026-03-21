"""
xatm.py — Jamoaviy Xatm (Group Quran Reading) handler.
"""
import math
import logging
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from services.firebase_service import (
    get_xatm_stats, get_or_create_recruiting_xatm, create_xatm,
    get_xatm, get_xatm_juzs, assign_xatm_juz, complete_xatm_juz,
    check_and_update_xatm_status, get_xatm_count, get_user,
    get_xatm_ranking,
)

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


def _dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤝 Xatmga Qo'shilish", callback_data="xatm:join")],
    ])


# ─── Xatm View ────────────────────────────────────────────────────────────────

def _xatm_view_text(xatm: dict, juzs: list, user_id: int) -> str:
    xatm_id     = xatm["xatm_id"]
    status      = xatm["status"]
    xatm_num    = xatm.get("xatm_number", "?")
    total       = len(juzs)
    completed   = sum(1 for j in juzs if j["status"] == "completed")
    my_juzs     = [j for j in juzs if j["user_id"] == user_id]
    my_done     = sum(1 for j in my_juzs if j["status"] == "completed")

    lines = [
        f"📖 *Xatm #{xatm_num}*",
        f"Holat: {_status_label(status)}",
        f"Juzlar: *{total}/30* band | *{completed}/30* o'qildi",
    ]
    if my_juzs:
        my_nums = sorted(j["juz_number"] for j in my_juzs)
        lines.append(f"Sizning juzlaringiz: *{', '.join(map(str, my_nums))}* ({my_done}/{len(my_juzs)} ✅)")
    lines.append("")
    lines.append("Juzingizni tanlang 👇")
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
                        label   = f"{j_num}✅"
                        cb_data = "xatm:void"
                    else:
                        label   = f"{j_num}🟢"
                        # Allow marking done at any time after assigning
                        cb_data = f"xatm:done:{xatm_id}:{j_num}"
                else:
                    label = f"{j_num}✅" if state["status"] == "completed" else f"{j_num}🔒"
            else:
                if status == "recruiting":
                    cb_data = f"xatm:take:{xatm_id}:{j_num}"

            row.append(InlineKeyboardButton(label, callback_data=cb_data))
        rows.append(row)

    # Bottom action buttons
    deep_link = f"https://t.me/{BOT_USERNAME}?start=xatm_{xatm_id}"
    rows.append([
        InlineKeyboardButton("👥 Ishtirokchilar", callback_data=f"xatm:members:{xatm_id}"),
        InlineKeyboardButton("🏆 Reyting",        callback_data=f"xatm:rank:{xatm_id}"),
    ])
    rows.append([InlineKeyboardButton(
        "🔗 Do'stlarga Ulashish",
        url=f"https://t.me/share/url?url={deep_link}&text=Jamoaviy+Xatmga+qo%27shiling%21"
    )])
    # If all 30 juzs are taken, show button to start next xatm
    if len(juz_map) == 30:
        rows.append([InlineKeyboardButton(
            "➕ Keyingi Xatmni Boshlash", callback_data="xatm:join"
        )])
    rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="xatm:dashboard")])
    return InlineKeyboardMarkup(rows)


# ─── Members View ─────────────────────────────────────────────────────────────

def _members_text(xatm: dict, juzs: list) -> str:
    xatm_num = xatm.get("xatm_number", "?")
    # Group juzs by user
    by_user: dict = {}
    for j in juzs:
        uid = j["user_id"]
        by_user.setdefault(uid, []).append(j)

    lines = [f"👥 *Xatm #{xatm_num} — Ishtirokchilar*\n"]
    if not by_user:
        lines.append("Hali hech kim qo'shilmagan.")
    else:
        for uid, user_juzs in sorted(by_user.items()):
            user = get_user(uid)
            name = user.get("full_name", str(uid)) if user else str(uid)
            done  = sum(1 for j in user_juzs if j["status"] == "completed")
            nums  = sorted(j["juz_number"] for j in user_juzs)
            nums_str = ", ".join(map(str, nums))
            lines.append(f"👤 *{name}*")
            lines.append(f"   Juzlar: {nums_str} ({done}/{len(user_juzs)} ✅)")
    return "\n".join(lines)


def _members_keyboard(xatm_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Orqaga", callback_data=f"xatm:view:{xatm_id}")
    ]])


# ─── Ranking View ─────────────────────────────────────────────────────────────

def _ranking_text(xatm: dict, ranking: list) -> str:
    xatm_num = xatm.get("xatm_number", "?")
    lines = [f"🏆 *Xatm #{xatm_num} — Reyting*\n"]
    if not ranking:
        lines.append("Hali hech kim juz o'qib bo'lmagan.")
    else:
        medals = ["🥇", "🥈", "🥉"]
        for i, entry in enumerate(ranking):
            medal = medals[i] if i < 3 else f"{i+1}."
            lines.append(
                f"{medal} *{entry['name']}* — "
                f"{entry['completed']} juz ✅ "
                f"({_fmt_time(entry.get('total_seconds', 0))})"
            )
    return "\n".join(lines)


def _ranking_keyboard(xatm_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Orqaga", callback_data=f"xatm:view:{xatm_id}")
    ]])


# ─── Core edit helper ─────────────────────────────────────────────────────────

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


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def show_xatm_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_xatm_stats()
    await update.message.reply_text(
        _dashboard_text(stats),
        parse_mode="Markdown",
        reply_markup=_dashboard_keyboard(),
    )


async def cb_xatm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    parts   = query.data.split(":")
    action  = parts[1] if len(parts) > 1 else ""

    if action == "dashboard":
        await query.answer()
        stats = get_xatm_stats()
        await _edit(query, _dashboard_text(stats), _dashboard_keyboard())

    elif action == "join":
        xatm_id = get_or_create_recruiting_xatm()
        if xatm_id is None:
            # No recruiting xatm — auto-create one
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
        if new_st == "active":
            xatm = get_xatm(xatm_id)
            num  = xatm.get("xatm_number", "?") if xatm else "?"
            await _notify_participants(xatm_id,
                f"🚀 *Xatm #{num} boshlandi!*\nBarcha 30 juz taqsimlandi. O'qishni boshlang!",
                context.bot)

    elif action == "done":
        xatm_id = parts[2]
        juz     = int(parts[3])
        complete_xatm_juz(xatm_id, juz, user_id)
        new_st  = check_and_update_xatm_status(xatm_id)
        await _refresh_xatm_view(query, xatm_id, user_id)
        if new_st == "completed":
            xatm = get_xatm(xatm_id)
            num  = xatm.get("xatm_number", "?") if xatm else "?"
            await _notify_participants(xatm_id,
                f"🎉 *Xatm #{num} yakunlandi!*\n"
                "Barcha ishtirokchilar juzlarini o'qib bo'ldi. Alloh qabul qilsin! 🤲",
                context.bot)

    elif action == "members":
        xatm_id = parts[2]
        await query.answer()
        xatm = get_xatm(xatm_id)
        if not xatm:
            return
        juzs = get_xatm_juzs(xatm_id)
        await _edit(query, _members_text(xatm, juzs), _members_keyboard(xatm_id))

    elif action == "rank":
        xatm_id = parts[2]
        await query.answer()
        xatm    = get_xatm(xatm_id)
        ranking = get_xatm_ranking(xatm_id)
        if not xatm:
            return
        await _edit(query, _ranking_text(xatm, ranking), _ranking_keyboard(xatm_id))

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
