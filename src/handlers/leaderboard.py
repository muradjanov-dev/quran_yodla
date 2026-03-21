"""Leaderboard with Back buttons and in-place refresh."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from src.database import db
from src.i18n import t, league_display

MEDALS = ["🥇", "🥈", "🥉"]

def _build_leaderboard_text(caller_id: int) -> str:
    rows = db.get_leaderboard()
    if not rows:
        return t(caller_id, "leaderboard_empty")

    lines = [t(caller_id, "leaderboard_header")]
    league_order = ["diamond", "gold", "silver", "bronze"]
    league_label_keys = {
        "diamond": "league_diamond",
        "gold": "league_gold",
        "silver": "league_silver",
        "bronze": "league_bronze",
    }
    for league in league_order:
        league_rows = [r for r in rows if r["league"] == league]
        if not league_rows:
            continue
        lines.append(f"\n{t(caller_id, league_label_keys[league])}")
        for i, row in enumerate(league_rows):
            medal = MEDALS[i] if i < 3 else f"{i + 1}."
            key = "leaderboard_you" if row["id"] == caller_id else "leaderboard_row"
            lines.append(t(caller_id, key,
                           rank=i + 1, medal=medal, name=row["name"],
                           xp=f"{row['total_xp']:,}", streak=row["current_streak"]))
    return "\n".join(lines)

def _lb_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(user_id, "btn_refresh"), callback_data="lb:refresh")],
        [InlineKeyboardButton(t(user_id, "btn_main_menu"), callback_data="menu:learn")],
    ])

async def _show_leaderboard(query_or_msg, user_id: int, edit: bool = False):
    text = _build_leaderboard_text(user_id)
    keyboard = _lb_keyboard(user_id)
    if edit:
        try:
            await query_or_msg.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            await query_or_msg.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await query_or_msg.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not db.get_user(user.id):
        from src.i18n.en import STRINGS as EN
        await update.message.reply_text(EN["please_start"])
        return
    await _show_leaderboard(update.message, user.id, edit=False)

async def cb_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Refreshed!")
    await _show_leaderboard(query, query.from_user.id, edit=True)

def register(app):
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CallbackQueryHandler(cb_leaderboard, pattern=r"^lb:"))
