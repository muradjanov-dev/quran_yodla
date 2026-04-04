"""
start.py — /start command and full onboarding ConversationHandler.
"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, MessageHandler, CallbackQueryHandler,
    filters
)

from config import (
    ONBOARDING_START, ONBOARDING_NAME, ONBOARDING_LEVEL,
    ONBOARDING_SURAHS, ONBOARDING_LOCATION, ONBOARDING_GOAL, ONBOARDING_TIME,
    REFERRAL_BONUS, ADMIN_ID
)
from services.firebase_service import (
    get_user, create_user, update_user, set_onboarding_complete,
    find_user_by_referral_code, increment_referral_count
)
from services.premium_service import activate_trial
from services.gamification import award_points, points_for_onboarding, get_level
from utils.keyboards import (
    main_menu_keyboard, onboarding_start_keyboard,
    onboarding_level_keyboard, onboarding_time_keyboard
)
from utils.messages import (
    onboarding_step_0, onboarding_step_name, onboarding_step_level,
    onboarding_step_surahs, onboarding_step_location, onboarding_step_goal,
    onboarding_step_time, welcome_message, referral_bonus_message
)

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user      = update.effective_user
    args      = context.args or []
    referral  = None

    # Parse referral code
    if args and args[0].startswith("ref_"):
        referral = args[0][4:]  # strip "ref_"

    # Deep link: xatm_<id> — redirect to xatm view after login
    xatm_deep_link = None
    if args and args[0].startswith("xatm_"):
        xatm_deep_link = args[0][5:]  # strip "xatm_"

    # Check if user exists
    db_user = get_user(user.id)

    if db_user and db_user.get("onboarding_complete"):
        # Returning user
        await update.message.reply_text(
            f"Xush kelibsiz, {db_user.get('full_name', user.first_name)}! 🕌",
            reply_markup=main_menu_keyboard()
        )
        # If came via xatm deep link, show the xatm immediately
        if xatm_deep_link:
            from handlers.xatm import show_xatm_dashboard_by_id
            await show_xatm_dashboard_by_id(update, context, xatm_deep_link)
        return ConversationHandler.END

    # New user — save ref code for later use
    if not db_user:
        context.user_data["referral_code"] = referral
        create_user(
            user.id,
            f"@{user.username}" if user.username else "",
            user.full_name or user.first_name or "Foydalanuvchi",
            referred_by=referral
        )
    elif referral and not db_user.get("referred_by"):
        update_user(user.id, {"referred_by": referral})
        context.user_data["referral_code"] = referral

    # Start onboarding
    await update.message.reply_text(
        onboarding_step_0(),
        reply_markup=onboarding_start_keyboard()
    )
    return ONBOARDING_START


async def onboarding_begin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(onboarding_step_name())
    return ONBOARDING_NAME


async def onboarding_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data["ob_name"] = name
    await update.message.reply_text(
        onboarding_step_level(),
        reply_markup=onboarding_level_keyboard()
    )
    return ONBOARDING_LEVEL


async def onboarding_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # e.g. "level_0", "level_30", "level_custom"

    level_map = {
        "level_0":  {"juz_count": 0,  "surahs": []},
        "level_5":  {"juz_count": 5,  "surahs": []},
        "level_15": {"juz_count": 15, "surahs": []},
        "level_29": {"juz_count": 29, "surahs": []},
        "level_30": {"juz_count": 30, "surahs": []},
    }

    if data == "level_custom":
        await query.message.reply_text(onboarding_step_surahs())
        return ONBOARDING_SURAHS
    else:
        context.user_data["ob_level"] = level_map.get(data, {"juz_count": 0, "surahs": []})
        await query.message.reply_text(onboarding_step_location())
        return ONBOARDING_LOCATION


async def onboarding_surahs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    surahs_text = update.message.text.strip()
    surahs = [s.strip() for s in surahs_text.split(",") if s.strip()]
    context.user_data["ob_level"] = {"juz_count": 0, "surahs": surahs}
    await update.message.reply_text(onboarding_step_location())
    return ONBOARDING_LOCATION


async def onboarding_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.text.strip()
    context.user_data["ob_location"] = location
    await update.message.reply_text(onboarding_step_goal())
    return ONBOARDING_GOAL


async def onboarding_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    goal = update.message.text.strip()
    context.user_data["ob_goal"] = goal
    await update.message.reply_text(
        onboarding_step_time(),
        reply_markup=onboarding_time_keyboard()
    )
    return ONBOARDING_TIME


async def onboarding_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    time_map = {"time_15": 15, "time_30": 30, "time_60": 60, "time_120": 120}
    daily_time = time_map.get(query.data, 30)

    user_id   = query.from_user.id
    full_name = context.user_data.get("ob_name", query.from_user.first_name)
    level     = context.user_data.get("ob_level", {"juz_count": 0, "surahs": []})
    location  = context.user_data.get("ob_location", "")
    goal      = context.user_data.get("ob_goal", "")

    # Save to Firestore
    set_onboarding_complete(user_id, full_name, location, goal, daily_time, level)

    # Activate trial
    activate_trial(user_id)

    # Award onboarding points
    award_points(user_id, points_for_onboarding(), "onboarding")

    # Send confetti sticker (Telegram default confetti sticker)
    try:
        await query.message.reply_sticker("CAACAgIAAxkBAAIBbWB5Vf1X5K2K3IFQ-Q-OXXAOi5nTAAIhAQACIjalSrnrxfD5Gq6NHQQ")
    except Exception as e:
        logger.warning(f"Could not send confetti sticker: {e}")

    await query.message.reply_text(
        welcome_message(full_name),
        reply_markup=main_menu_keyboard()
    )

    # Notify admin about new user
    try:
        from services.firebase_service import get_all_users
        total_users = len(get_all_users())
        username_str = f"@{query.from_user.username}" if query.from_user.username else "—"
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"👤 YANGI FOYDALANUVCHI!\n\n"
                f"Ism: {full_name}\n"
                f"Username: {username_str}\n"
                f"ID: {user_id}\n\n"
                f"📊 Jami foydalanuvchilar: {total_users}"
            )
        )
    except Exception as e:
        logger.warning(f"Could not notify admin of new user: {e}")

    # Handle referral reward
    referral_code = context.user_data.get("referral_code")
    if referral_code:
        await _process_referral(query.message, user_id, referral_code, full_name, context)

    return ConversationHandler.END


async def _process_referral(message, new_user_id: int, ref_code: str,
                              new_user_name: str, context):
    referrer = find_user_by_referral_code(ref_code)
    if not referrer:
        return
    referrer_id = referrer["telegram_id"]
    if referrer_id == new_user_id:
        return  # Self-referral

    # Award both users
    old_points = referrer.get("stats", {}).get("himmat_points", 0)
    level_up = award_points(referrer_id, REFERRAL_BONUS, "referral")
    new_total = old_points + REFERRAL_BONUS
    increment_referral_count(referrer_id)
    award_points(new_user_id, REFERRAL_BONUS, "referral_joined")

    # Grant referrer 1 day of free premium for inviting a friend
    try:
        from services.premium_service import activate_premium
        activate_premium(referrer_id, days=1)
    except Exception as e:
        logger.warning(f"Could not grant referral premium to {referrer_id}: {e}")

    # Notify referrer
    try:
        await context.bot.send_message(
            chat_id=referrer_id,
            text=(
                f"{referral_bonus_message(new_user_name, new_total)}\n\n"
                f"🎁 Bonus: Do'stingiz qo'shilgani uchun sizga 1 kun bepul Premium berildi! 💎"
            )
        )
    except Exception as e:
        logger.warning(f"Could not notify referrer {referrer_id}: {e}")

    # Check referral achievements for referrer
    import asyncio
    from handlers.achievements import check_and_notify_achievements
    asyncio.ensure_future(check_and_notify_achievements(context.bot, referrer_id))


def build_onboarding_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            ONBOARDING_START:    [CallbackQueryHandler(onboarding_begin, pattern="^onboarding_start$")],
            ONBOARDING_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_name)],
            ONBOARDING_LEVEL:    [CallbackQueryHandler(onboarding_level, pattern="^level_")],
            ONBOARDING_SURAHS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_surahs)],
            ONBOARDING_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_location)],
            ONBOARDING_GOAL:     [MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_goal)],
            ONBOARDING_TIME:     [CallbackQueryHandler(onboarding_time, pattern="^time_")],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
        allow_reentry=True,
        name="onboarding",
        persistent=False,
        per_message=False,
    )
