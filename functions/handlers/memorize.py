"""
memorize.py — Full 3→7→11→accumulation yodlash flow.
"""

import logging
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CallbackQueryHandler, MessageHandler, filters, CommandHandler
)
from telegram.constants import ParseMode

from config import (
    MEMO_SELECT_JUZ, MEMO_SELECT_DIRECTION, MEMO_SELECT_RECITER,
    MEMO_SELECT_SURAH, MEMO_IN_PROGRESS, MEMO_REP_3, MEMO_REP_7,
    MEMO_REP_11, MEMO_ACCUMULATION, MEMO_ACC_7, DAILY_FREE_LIMIT
)
from services.firebase_service import (
    get_user, get_active_session, create_session, update_session, close_session,
    get_daily_ayah_count, add_activity_to_period_safe
)
from services.quran_api import get_ayah, get_audio_url, get_surah_ayahs
from services.gamification import (
    award_points, points_for_repetition, points_for_accumulation,
    points_for_ayah_complete, points_for_surah_complete,
    update_streak, check_level_up, get_level
)
from services.premium_service import is_premium
from utils.keyboards import (
    juz_selection_keyboard, direction_keyboard, reciter_keyboard,
    surah_selection_keyboard, repetition_keyboard, accumulation_keyboard,
    checkpoint_keyboard, limit_reached_keyboard, open_memorize_keyboard
)
from utils.messages import (
    ayah_header, ayah_text_message, rep_instruction, accumulation_message,
    checkpoint_message, limit_reached_message, surah_complete_message, level_up_message
)
from utils.helpers import get_surahs_in_juz, get_surah_by_number, get_next_surah_in_juz

logger = logging.getLogger(__name__)


# ─── Entry Points ─────────────────────────────────────────────────────────────

async def open_memorize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called from main menu button or /yodlash."""
    user_id = update.effective_user.id
    active  = get_active_session(user_id)

    msg = update.message or (update.callback_query and update.callback_query.message)
    if update.callback_query:
        await update.callback_query.answer()

    await msg.reply_text(
        "📗 YODLASH\n\nQaysi juzdan boshlashni tanlang:",
        reply_markup=juz_selection_keyboard(has_active_session=bool(active))
    )
    return MEMO_SELECT_JUZ


async def juz_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data    = query.data
    user_id = query.from_user.id

    if data == "memo_continue":
        # Resume active session
        session = get_active_session(user_id)
        if session:
            context.user_data["session"] = session
            return await _send_current_ayah(query.message, context, user_id)
        else:
            await query.message.reply_text("Aktiv sessiya topilmadi. Yangi boshlaylik.")
            await query.message.reply_text(
                "Qaysi juzdan boshlashni tanlang:",
                reply_markup=juz_selection_keyboard()
            )
            return MEMO_SELECT_JUZ

    juz_number = int(data.split("_")[1])
    context.user_data["juz_number"] = juz_number

    if juz_number == 30:
        await query.message.reply_text(
            "30-juz tanlandi! 📖\n\nQaysi yo'nalishdan boshlashni tanlang:",
            reply_markup=direction_keyboard()
        )
        return MEMO_SELECT_DIRECTION
    else:
        context.user_data["direction"] = "forward"
        await query.message.reply_text(
            "🎙️ Qori tanlang:",
            reply_markup=reciter_keyboard(for_memorize=True)
        )
        return MEMO_SELECT_RECITER


async def direction_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    direction = "forward" if query.data == "dir_forward" else "backward"
    context.user_data["direction"] = direction
    await query.message.reply_text("🎙️ Qori tanlang:", reply_markup=reciter_keyboard(for_memorize=True))
    return MEMO_SELECT_RECITER


async def reciter_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    reciter_key = query.data.split("_", 1)[1]  # "reciter_husary" → "husary"
    context.user_data["reciter"] = reciter_key

    juz_number = context.user_data.get("juz_number")
    direction  = context.user_data.get("direction", "forward")
    surahs     = get_surahs_in_juz(juz_number)
    if direction == "backward":
        surahs = list(reversed(surahs))

    await query.message.reply_text(
        f"📖 Tanlangan juz: {juz_number}-juz\n\nBoshlash uchun tugmani bosing yoki aniq surani tanlang:",
        reply_markup=surah_selection_keyboard(surahs)
    )
    return MEMO_SELECT_SURAH


async def surah_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    data    = query.data
    user_id = query.from_user.id

    juz_number = context.user_data.get("juz_number")
    direction  = context.user_data.get("direction", "forward")
    reciter    = context.user_data.get("reciter", "husary")

    if data == "surah_start":
        # First surah in juz
        surahs = get_surahs_in_juz(juz_number)
        if direction == "backward":
            surahs = list(reversed(surahs))
        surah_info = surahs[0] if surahs else None
    else:
        surah_num  = int(data.split("_")[1])
        surah_info = get_surah_by_number(surah_num)

    if not surah_info:
        await query.message.reply_text("Xatolik: sura topilmadi.")
        return ConversationHandler.END

    # Check daily limit for free users
    db_user = get_user(user_id)
    if not is_premium(db_user):
        count = get_daily_ayah_count(user_id)
        if count >= DAILY_FREE_LIMIT:
            await query.message.reply_text(
                limit_reached_message(),
                reply_markup=limit_reached_keyboard()
            )
            return ConversationHandler.END

    # Create session
    session = create_session(
        user_id     = user_id,
        juz_number  = juz_number,
        surah_number= surah_info["number"],
        surah_name  = surah_info["name"],
        direction   = direction,
        reciter     = reciter,
        start_ayah  = 1,
    )
    context.user_data["session"] = session

    return await _send_current_ayah(query.message, context, user_id)


# ─── Core Memorize Flow ───────────────────────────────────────────────────────

async def _send_current_ayah(message, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Send the current ayah (header + audio + text + rep button)."""
    session     = context.user_data.get("session", {})
    surah_num   = session["surah_number"]
    surah_name  = session["surah_name"]
    reciter     = session["reciter"]
    acc_ayahs   = session.get("accumulated_ayahs", [])
    next_index  = len(acc_ayahs) + 1  # next ayah to memorize

    # Fetch ayah data
    ayah_data = get_ayah(surah_num, next_index)
    if not ayah_data:
        await message.reply_text("API xatoligi. Iltimos, qayta urinib ko'ring.")
        return ConversationHandler.END

    surah_info  = get_surah_by_number(surah_num)
    total_ayahs = surah_info["ayah_count"] if surah_info else 999

    # Header
    await message.reply_text(
        ayah_header(surah_name, surah_num, next_index, total_ayahs)
    )

    # Audio
    audio_url = get_audio_url(ayah_data["global_number"], reciter)
    try:
        await message.reply_audio(audio=audio_url)
    except Exception as e:
        logger.warning(f"Audio send failed: {e}")
        await message.reply_text(f"🎧 Audio: {audio_url}")

    # Text + first rep button (3x)
    await message.reply_text(
        ayah_text_message(
            ayah_data["arabic"], ayah_data["uzbek"],
            rep_instruction(3), 3
        ),
        reply_markup=repetition_keyboard(3, "3")
    )

    # Save current ayah data to session
    update_session(session["session_id"], {
        "current_ayah_index": next_index,
        "stage":              "rep_3",
        "current_ayah_data":  {
            "arabic":        ayah_data["arabic"],
            "uzbek":         ayah_data["uzbek"],
            "global_number": ayah_data["global_number"],
            "surah_number":  surah_num,
            "ayah_number":   next_index,
        }
    })
    session["current_ayah_index"] = next_index
    session["stage"] = "rep_3"
    context.user_data["session"] = session

    return MEMO_REP_3


async def rep_3_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = context.user_data.get("session", {})

    # Award points
    level_up = award_points(user_id, points_for_repetition(3), "rep_3")
    if level_up:
        await query.message.reply_text(level_up_message(level_up[1]))

    # Get current ayah data
    ayah_data = session.get("current_ayah_data", {})

    await query.message.reply_text(
        ayah_text_message(
            ayah_data.get("arabic", ""), ayah_data.get("uzbek", ""),
            rep_instruction(7), 7
        ),
        reply_markup=repetition_keyboard(7, "7")
    )
    update_session(session["session_id"], {"stage": "rep_7"})
    session["stage"] = "rep_7"
    context.user_data["session"] = session
    return MEMO_REP_7


async def rep_7_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = context.user_data.get("session", {})

    level_up = award_points(user_id, points_for_repetition(7), "rep_7")
    if level_up:
        await query.message.reply_text(level_up_message(level_up[1]))

    ayah_data = session.get("current_ayah_data", {})
    await query.message.reply_text(
        ayah_text_message(
            ayah_data.get("arabic", ""), ayah_data.get("uzbek", ""),
            rep_instruction(11), 11
        ),
        reply_markup=repetition_keyboard(11, "11")
    )
    update_session(session["session_id"], {"stage": "rep_11"})
    session["stage"] = "rep_11"
    context.user_data["session"] = session
    return MEMO_REP_11


async def rep_11_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = context.user_data.get("session", {})

    # Award 11-rep points + full ayah completion
    level_up = award_points(user_id, points_for_repetition(11) + points_for_ayah_complete(), "rep_11+ayah")
    if level_up:
        await query.message.reply_text(level_up_message(level_up[1]))

    # Record stats (1 new ayah)
    add_activity_to_period_safe(user_id, 1, 3+7+11, 5, points_for_repetition(11), [session.get("surah_name","")])

    # Add to accumulated ayahs
    current_ayah = session.get("current_ayah_data", {})
    acc = session.get("accumulated_ayahs", [])
    acc.append(current_ayah)
    update_session(session["session_id"], {
        "accumulated_ayahs": acc,
        "stage": "accumulation",
        "session_ayahs_count": len(acc),
    })
    session["accumulated_ayahs"] = acc

    # Check if free user hit limit
    db_user = get_user(user_id)
    if not is_premium(db_user):
        daily_count = get_daily_ayah_count(user_id)
        if daily_count >= DAILY_FREE_LIMIT:
            await query.message.reply_text(
                limit_reached_message(),
                reply_markup=limit_reached_keyboard()
            )
            close_session(session["session_id"])
            return ConversationHandler.END

    # Send accumulation round
    return await _send_accumulation(query.message, context, user_id, acc)


async def _send_accumulation(message, context, user_id: int, acc: list):
    """Send all accumulated ayahs for combined 7x repetition."""
    session = context.user_data.get("session", {})
    reciter = session.get("reciter", "husary")

    # Send each accumulated audio
    for ayah in acc:
        audio_url = get_audio_url(ayah.get("global_number", 1), reciter)
        try:
            await message.reply_audio(audio=audio_url)
        except Exception as e:
            logger.warning(f"Accumulation audio error: {e}")

    await message.reply_text(
        accumulation_message(acc),
        reply_markup=accumulation_keyboard(len(acc))
    )
    update_session(session["session_id"], {"stage": "acc_7"})
    session["stage"] = "acc_7"
    context.user_data["session"] = session
    return MEMO_ACC_7


async def accumulation_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = context.user_data.get("session", {})

    acc = session.get("accumulated_ayahs", [])
    level_up = award_points(user_id, points_for_accumulation(len(acc)), "accumulation")
    if level_up:
        await query.message.reply_text(level_up_message(level_up[1]))

    # Checkpoint every 5 ayahs
    if len(acc) > 0 and len(acc) % 5 == 0:
        await query.message.reply_text(
            checkpoint_message(len(acc)),
            reply_markup=checkpoint_keyboard()
        )
        context.user_data["session"] = session
        return MEMO_ACCUMULATION

    # Check surah completion
    surah_info = get_surah_by_number(session["surah_number"])
    if surah_info and len(acc) >= surah_info["ayah_count"]:
        await _handle_surah_complete(query.message, context, user_id, session, surah_info)
        return ConversationHandler.END

    # Continue to next ayah
    return await _send_current_ayah(query.message, context, user_id)


async def checkpoint_go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    return await _send_current_ayah(query.message, context, user_id)


async def checkpoint_save_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    session = context.user_data.get("session", {})
    close_session(session.get("session_id", ""))
    await query.message.reply_text(
        "💾 Progress saqlandi! Keyingi safar davom etasiz. 🌟"
    )
    return ConversationHandler.END


async def _handle_surah_complete(message, context, user_id: int, session: dict, surah_info: dict):
    himmat = points_for_surah_complete(surah_info["ayah_count"])
    level_up = award_points(user_id, himmat, "surah_complete")
    await message.reply_text(surah_complete_message(surah_info["name"], himmat))
    if level_up:
        await message.reply_text(level_up_message(level_up[1]))

    # Mark surah completed in user progress
    from services.firebase_service import update_user
    from google.cloud.firestore_v1 import ArrayUnion
    try:
        from firebase_config import db
        if db:
            db.collection("users").document(str(user_id)).update({
                "memorization_progress.completed_surahs": ArrayUnion([surah_info["name"]])
            })
    except Exception as e:
        logger.error(f"Surah complete update error: {e}")

    close_session(session.get("session_id", ""))


async def handle_limit_reached_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Import open_premium handler
    from handlers.premium import show_premium_menu
    await show_premium_menu(update, context)


def build_memorize_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📗 Yodlash$"), open_memorize),
            CallbackQueryHandler(open_memorize, pattern="^open_memorize$"),
        ],
        states={
            MEMO_SELECT_JUZ: [
                CallbackQueryHandler(juz_selected, pattern="^(juz_|memo_continue)"),
            ],
            MEMO_SELECT_DIRECTION: [
                CallbackQueryHandler(direction_selected, pattern="^dir_"),
            ],
            MEMO_SELECT_RECITER: [
                CallbackQueryHandler(reciter_selected, pattern="^reciter_"),
            ],
            MEMO_SELECT_SURAH: [
                CallbackQueryHandler(surah_selected, pattern="^surah_"),
            ],
            MEMO_REP_3: [
                CallbackQueryHandler(rep_3_done, pattern="^rep_done_3$"),
            ],
            MEMO_REP_7: [
                CallbackQueryHandler(rep_7_done, pattern="^rep_done_7$"),
            ],
            MEMO_REP_11: [
                CallbackQueryHandler(rep_11_done, pattern="^rep_done_11$"),
            ],
            MEMO_ACC_7: [
                CallbackQueryHandler(accumulation_done, pattern="^acc_done$"),
            ],
            MEMO_ACCUMULATION: [
                CallbackQueryHandler(checkpoint_go,        pattern="^memo_go$"),
                CallbackQueryHandler(checkpoint_save_exit, pattern="^memo_save_exit$"),
            ],
        },
        fallbacks=[
            CommandHandler("start",    lambda u, c: ConversationHandler.END),
            CallbackQueryHandler(handle_limit_reached_premium, pattern="^open_premium$"),
            CallbackQueryHandler(checkpoint_save_exit,          pattern="^memo_tomorrow$"),
        ],
        allow_reentry=True,
        name="memorize",
        persistent=False,
    )
