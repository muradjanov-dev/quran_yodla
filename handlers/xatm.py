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
    check_and_update_xatm_status,
)

logger = logging.getLogger(__name__)


def _fmt_time(secs: int) -> str:
    if secs <= 0:
        return "0 kun"
    days = math.floor(secs / 86400)
    hrs  = math.floor((secs % 86400) / 3600)
    res  = []
    if days > 0: res.append(f"{days} kun")
    if hrs  > 0: res.append(f"{hrs} soat")
    return " ".join(res) if res else "< 1 soat"


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
        "Jamoaviy xatmga qo'shiling yoki yangi xatm yarating!"
    )


def _dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤝 Faol Xatmga Qo'shilish", callback_data="xatm:join")],
        [InlineKeyboardButton("➕ Yangi Xatm Yaratish",    callback_data="xatm:create")],
    ])


def _status_label(status: str) -> str:
    return {"recruiting": "🟡 Ro'yxat ochiq", "active": "🟢 Faol", "completed": "✅ Yakunlangan"}.get(status, status)


def _xatm_view_text(xatm_id: str, status: str) -> str:
    return (
        f"📖 *Xatm #{xatm_id[:8]}*\n"
        f"Holat: {_status_label(status)}\n\n"
        "Juzingizni tanlang 👇"
    )


def _xatm_keyboard(xatm_id: str, juz_map: dict, user_id: int, status: str) -> InlineKeyboardMarkup:
    rows = []
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
                        label = f"{j_num}✅"
                    else:
                        label = f"{j_num}🟢"
                        if status in ("active", "completed"):
                            cb_data = f"xatm:done:{xatm_id}:{j_num}"
                else:
                    label = f"{j_num}🔒" if state["status"] != "completed" else f"{j_num}✅"
            else:
                if status == "recruiting":
                    cb_data = f"xatm:take:{xatm_id}:{j_num}"

        # last row may be <6
            row.append(InlineKeyboardButton(label, callback_data=cb_data))
        rows.append(row)

    # Big mark-complete button for my first active juz during marathon
    if status == "active":
        my_active = [n for n, j in juz_map.items() if j["user_id"] == user_id and j["status"] == "assigned"]
        if my_active:
            first = my_active[0]
            rows.append([InlineKeyboardButton(
                f"✅ {first}-juzni o'qidim",
                callback_data=f"xatm:done:{xatm_id}:{first}"
            )])

    # Share button — Telegram share dialog with direct deep link
    deep_link = f"https://t.me/quranyodla_bot?start=xatm_{xatm_id}"
    rows.append([InlineKeyboardButton(
        "🔗 Do'stlarga Ulashish",
        url=f"https://t.me/share/url?url={deep_link}&text=Jamoaviy+Xatmga+qo%27shiling%21"
    )])
    rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="xatm:dashboard")])
    return InlineKeyboardMarkup(rows)


async def _edit(query, text: str, kb: InlineKeyboardMarkup):
    try:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        if "Message is not modified" not in str(e):
            logger.warning(f"xatm _edit error: {e}")


async def show_xatm_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point from main menu button."""
    stats = get_xatm_stats()
    await update.message.reply_text(
        _dashboard_text(stats),
        parse_mode="Markdown",
        reply_markup=_dashboard_keyboard(),
    )


async def show_xatm_view(xatm_id: str, user_id: int, query, alert: Optional[str] = None):
    xatm = get_xatm(xatm_id)
    if not xatm:
        await query.answer("Xatm topilmadi.", show_alert=True)
        return

    juzs    = get_xatm_juzs(xatm_id)
    juz_map = {j["juz_number"]: j for j in juzs}
    text    = _xatm_view_text(xatm_id, xatm["status"])
    kb      = _xatm_keyboard(xatm_id, juz_map, user_id, xatm["status"])

    await query.answer(alert, show_alert=bool(alert))
    await _edit(query, text, kb)


async def _notify_participants(xatm_id: str, text_fn, bot):
    juzs         = get_xatm_juzs(xatm_id)
    participants = set(j["user_id"] for j in juzs)
    for uid in participants:
        try:
            await bot.send_message(chat_id=uid, text=text_fn(uid), parse_mode="Markdown")
        except Exception:
            pass


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
        await show_xatm_view(xatm_id, user_id, query)

    elif action == "create":
        xatm_id = create_xatm(creator_id=user_id)
        await show_xatm_view(xatm_id, user_id, query)

    elif action == "take":
        _, _, xatm_id, juz = parts
        juz    = int(juz)
        ok     = assign_xatm_juz(xatm_id, juz, user_id)
        alert  = "⚠️ Bu juz allaqachon olingan!" if not ok else None
        new_st = check_and_update_xatm_status(xatm_id) if ok else None
        await show_xatm_view(xatm_id, user_id, query, alert=alert)
        if new_st == "active":
            await _notify_participants(
                xatm_id,
                lambda uid: f"🚀 Xatm #{xatm_id[:8]} boshlandi! Barcha 30 juz taqsimlandi. O'qishni boshlang!",
                context.bot,
            )

    elif action == "done":
        _, _, xatm_id, juz = parts
        juz    = int(juz)
        complete_xatm_juz(xatm_id, juz, user_id)
        new_st = check_and_update_xatm_status(xatm_id)
        await show_xatm_view(xatm_id, user_id, query)
        if new_st == "completed":
            await _notify_participants(
                xatm_id,
                lambda uid: (
                    f"🎉 Xatm #{xatm_id[:8]} yakunlandi!\n"
                    "Barcha ishtirokchilar juzlarini o'qib bo'ldi. Alloh qabul qilsin! 🤲"
                ),
                context.bot,
            )

    elif action == "void":
        await query.answer()


async def show_xatm_dashboard_by_id(update: Update, context: ContextTypes.DEFAULT_TYPE, xatm_id: str):
    """Called from start handler when user arrives via deep link."""
    xatm = get_xatm(xatm_id)
    if not xatm:
        await update.message.reply_text("⚠️ Xatm topilmadi yoki yakunlangan.")
        return
    user_id = update.effective_user.id
    juzs    = get_xatm_juzs(xatm_id)
    juz_map = {j["juz_number"]: j for j in juzs}
    text    = _xatm_view_text(xatm_id, xatm["status"])
    kb      = _xatm_keyboard(xatm_id, juz_map, user_id, xatm["status"])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


def register_xatm_handlers(app):
    app.add_handler(MessageHandler(filters.Regex("^👥 Jamoaviy Xatm$"), show_xatm_dashboard))
    app.add_handler(CallbackQueryHandler(cb_xatm, pattern=r"^xatm:"))
