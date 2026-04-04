"""
leaderboard.py — Reyting (Leaderboard) handler.
Fixed: daily/weekly/monthly/yearly periods now pull from correct stat collections.
Added: anonymous toggle so users can hide their name in the leaderboard.
"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from services.firebase_service import get_leaderboard, get_user_rank, get_user, update_user
from utils.keyboards import leaderboard_period_keyboard
from utils.messages import leaderboard_message

logger = logging.getLogger(__name__)


def _leaderboard_anon_kb(active: str, is_anon: bool) -> InlineKeyboardMarkup:
    """Period keyboard + anonymous toggle button."""
    row1_periods = [("📅 Bugun", "day"), ("📆 Hafta", "week"), ("📆 Oy", "month")]
    row2_periods = [("📅 Yil", "year"), ("🏆 Umumiy", "all")]
    row1 = [
        InlineKeyboardButton(f"[{lb}]" if k == active else lb, callback_data=f"lb_{k}")
        for lb, k in row1_periods
    ]
    row2 = [
        InlineKeyboardButton(f"[{lb}]" if k == active else lb, callback_data=f"lb_{k}")
        for lb, k in row2_periods
    ]
    toggle_label = "👁 Ismni Ko'rsatish" if is_anon else "🫥 Ismni Yashirish"
    row3 = [InlineKeyboardButton(toggle_label, callback_data="lb_toggle_anon")]
    return InlineKeyboardMarkup([row1, row2, row3])


async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message or (update.callback_query and update.callback_query.message)
    if update.callback_query:
        await update.callback_query.answer()

    db_user   = get_user(user_id)
    is_anon   = db_user.get("lb_anonymous", False) if db_user else False
    entries   = get_leaderboard(limit=50)
    user_rank = get_user_rank(user_id)
    user_entry = next((e for e in entries if e["user_id"] == user_id), None)
    if not user_entry and db_user:
        stats = db_user.get("stats", {})
        user_entry = {
            "user_id":       user_id,
            "full_name":     "Siz" if is_anon else db_user.get("full_name", "Siz"),
            "total_verses":  stats.get("total_verses_read", 0),
            "himmat_points": stats.get("himmat_points", 0),
        }

    text = leaderboard_message(entries, user_id, user_rank, user_entry,
                               period="all", viewer_id=user_id, anon_ids=_get_anon_ids())
    await msg.reply_text(text, reply_markup=_leaderboard_anon_kb("all", is_anon))


async def leaderboard_period_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id

    if query.data == "lb_toggle_anon":
        await query.answer()
        db_user  = get_user(user_id)
        is_anon  = db_user.get("lb_anonymous", False) if db_user else False
        update_user(user_id, {"lb_anonymous": not is_anon})
        is_anon  = not is_anon
        msg_text = "🫥 Ismingiz reytingda yashirildi" if is_anon else "👁 Ismingiz reytingda ko'rinadi"
        await query.answer(msg_text, show_alert=True)
        # Refresh current view — re-fetch last period from context
        period = context.user_data.get("lb_period", "all")
        await _refresh_lb(query, user_id, period, is_anon)
        return

    await query.answer()
    period = query.data.replace("lb_", "")
    context.user_data["lb_period"] = period
    db_user = get_user(user_id)
    is_anon = db_user.get("lb_anonymous", False) if db_user else False
    await _refresh_lb(query, user_id, period, is_anon)


async def _refresh_lb(query, user_id: int, period: str, is_anon: bool):
    """Build and send/edit leaderboard for the given period."""
    anon_ids = _get_anon_ids()

    if period == "all":
        entries    = get_leaderboard(limit=50)
        user_rank  = get_user_rank(user_id)
        user_entry = next((e for e in entries if e["user_id"] == user_id), None)
        text = leaderboard_message(entries, user_id, user_rank, user_entry,
                                   period="all", viewer_id=user_id, anon_ids=anon_ids)
    else:
        entries, user_entry, user_rank = _get_period_leaderboard(user_id, period)
        text = leaderboard_message(entries, user_id, user_rank, user_entry,
                                   period=period, viewer_id=user_id, anon_ids=anon_ids)

    try:
        await query.message.edit_text(text, reply_markup=_leaderboard_anon_kb(period, is_anon))
    except Exception:
        await query.message.reply_text(text, reply_markup=_leaderboard_anon_kb(period, is_anon))


def _get_anon_ids() -> set:
    """Returns set of user_ids who have lb_anonymous=True."""
    from firebase_config import db
    if not db:
        return set()
    try:
        docs = db.collection("users").where("lb_anonymous", "==", True).stream()
        return {d.to_dict().get("telegram_id") for d in docs if d.to_dict().get("telegram_id")}
    except Exception:
        return set()


def _get_period_leaderboard(user_id: int, period: str):
    """Aggregate period-specific stats and return (entries, user_entry, user_rank)."""
    from firebase_config import db
    from services.firebase_service import (
        _today_str, _week_str, _month_str, _year_str,
        get_period_stats, get_daily_stats,
    )

    period_map = {
        "day":   "daily_stats",
        "week":  "weekly_stats",
        "month": "monthly_stats",
        "year":  "yearly_stats",
    }
    coll_name = period_map.get(period, "daily_stats")

    if not db:
        return [], None, 0

    try:
        docs = (
            db.collection(coll_name)
            .where("verses_read", ">", 0)
            .stream()
        )
        rows = []
        for doc in docs:
            d   = doc.to_dict()
            uid = d.get("user_id")
            if not uid:
                continue
            u    = get_user(uid)
            name = (u.get("full_name") or "Anonim") if u else "Anonim"
            rows.append({
                "user_id":       uid,
                "full_name":     name,
                "total_verses":  d.get("verses_read", 0),
                "himmat_points": d.get("himmat_earned", 0),
            })

        rows.sort(key=lambda x: (-x["himmat_points"], -x["total_verses"]))
        rows = rows[:50]

        user_rank  = next((i + 1 for i, r in enumerate(rows) if r["user_id"] == user_id), 0)
        user_entry = next((r for r in rows if r["user_id"] == user_id), None)

        if not user_entry:
            st = get_daily_stats(user_id) if period == "day" else get_period_stats(user_id, period)
            u  = get_user(user_id)
            user_entry = {
                "user_id":       user_id,
                "full_name":     (u.get("full_name") or "Siz") if u else "Siz",
                "total_verses":  st.get("verses_read", 0),
                "himmat_points": st.get("himmat_earned", 0),
            }

        return rows, user_entry, user_rank

    except Exception as e:
        logger.error(f"_get_period_leaderboard error: {e}")
        return [], None, 0


def register_leaderboard_handlers(app):
    app.add_handler(MessageHandler(filters.Regex("^🏆 Reyting$"), show_leaderboard))
    app.add_handler(CallbackQueryHandler(leaderboard_period_callback, pattern="^lb_"))
