"""Gamification helpers: XP, streaks, badges, league notifications."""
import json
from telegram.ext import ContextTypes

from src.database import db
from src.i18n import t, badge_display, league_display

BADGE_THRESHOLDS = {
    "first_step": lambda stats: stats["total_memorized"] >= 1,
    "week_warrior": lambda stats: stats["streak"] >= 7,
    "page_turner": lambda stats: stats["total_memorized"] >= 15,
    "juz_warrior": lambda stats: stats["total_memorized"] >= 604,
}

async def award_xp_and_streak(user_id: int, xp_amount: int, context: ContextTypes.DEFAULT_TYPE):
    """Award XP, update streak, check badges, send notifications."""
    # XP
    total_xp, new_league, league_changed = db.add_xp(user_id, xp_amount)
    # Streak
    new_streak, streak_reset = db.update_streak(user_id)

    # Notify XP
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=t(user_id, "xp_earned", xp=xp_amount, total=total_xp),
            parse_mode="Markdown",
        )
    except Exception:
        pass

    # Notify league up
    if league_changed:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=t(user_id, "league_up", league=league_display(user_id, new_league)),
                parse_mode="Markdown",
            )
        except Exception:
            pass

    # Check badges
    progress_rows = db.get_progress(user_id)
    total_memorized = sum(1 for r in progress_rows if r["memorized"])
    stats = {"streak": new_streak, "total_memorized": total_memorized}
    for badge_key, predicate in BADGE_THRESHOLDS.items():
        if predicate(stats):
            if db.unlock_badge(user_id, badge_key):
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=t(user_id, "badge_unlocked", badge=badge_display(user_id, badge_key)),
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass

    return new_streak, streak_reset
