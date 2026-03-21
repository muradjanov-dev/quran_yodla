"""
leaderboard.py — Reyting (Leaderboard) handler.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from services.firebase_service import get_leaderboard, get_user_rank, get_user
from utils.keyboards import leaderboard_period_keyboard
from utils.messages import leaderboard_message

logger = logging.getLogger(__name__)


async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message or (update.callback_query and update.callback_query.message)
    if update.callback_query:
        await update.callback_query.answer()

    entries   = get_leaderboard(limit=50)
    user_rank = get_user_rank(user_id)
    db_user   = get_user(user_id)
    user_entry= next((e for e in entries if e["user_id"] == user_id), None)
    if not user_entry and db_user:
        stats = db_user.get("stats", {})
        user_entry = {
            "user_id":      user_id,
            "full_name":    db_user.get("full_name", "Siz"),
            "total_verses": stats.get("total_verses_read", 0),
            "himmat_points":stats.get("himmat_points", 0),
        }

    text = leaderboard_message(entries, user_id, user_rank, user_entry)
    await msg.reply_text(text, reply_markup=leaderboard_period_keyboard(active="month"))


async def leaderboard_period_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    # period = query.data.split("_")[1]  # "lb_week", "lb_month" etc
    # For now leaderboard is global (all-time); period filtering is cosmetic
    user_id   = query.from_user.id
    period    = query.data.replace("lb_", "")
    entries   = get_leaderboard(limit=50)
    user_rank = get_user_rank(user_id)
    user_entry= next((e for e in entries if e["user_id"] == user_id), None)
    text = leaderboard_message(entries, user_id, user_rank, user_entry)
    try:
        await query.message.edit_text(text, reply_markup=leaderboard_period_keyboard(active=period))
    except Exception:
        await query.message.reply_text(text, reply_markup=leaderboard_period_keyboard(active=period))


def register_leaderboard_handlers(app):
    app.add_handler(MessageHandler(filters.Regex("^🏆 Reyting$"), show_leaderboard))
    app.add_handler(CallbackQueryHandler(leaderboard_period_callback, pattern="^lb_"))
