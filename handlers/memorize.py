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
    get_daily_ayah_count, add_activity_to_period_safe, get_ayah_photo,
    save_memorization_progress, get_memorization_progress,
)
from services.quran_api import get_ayah, get_audio_url, get_surah_ayahs
from services.gamification import (
    award_points, points_for_repetition, points_for_accumulation,
    points_for_ayah_complete, points_for_surah_complete,
    update_streak, check_level_up, get_level,
    apply_streak_update, check_and_award_daily_login, check_and_award_first_ayah
)
from services.premium_service import is_premium
from utils.keyboards import (
    juz_selection_keyboard, direction_keyboard, reciter_keyboard,
    surah_selection_keyboard, repetition_keyboard, accumulation_keyboard,
    checkpoint_keyboard, limit_reached_keyboard, open_memorize_keyboard
)
from utils.messages import (
    ayah_header, ayah_text_message, rep_instruction, accumulation_message,
    checkpoint_message, limit_reached_message, surah_complete_message,
    level_up_message, ayah_progress_message
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
        # 1. Try to resume an active in-progress session
        session = get_active_session(user_id)
        if session:
            context.user_data["session"] = session
            return await _send_current_ayah(query.message.chat_id, context, user_id)
        # 2. Fall back to saved memorization progress (last completed surah+ayah)
        prog = get_memorization_progress(user_id)
        surah_num  = prog.get("current_surah")
        next_ayah  = prog.get("current_ayah", 1)
        surah_name = prog.get("current_surah_name", "")
        if surah_num:
            from utils.helpers import get_surah_by_number
            surah_info = get_surah_by_number(surah_num)
            if surah_info:
                db_user = get_user(user_id)
                if not is_premium(db_user) and get_daily_ayah_count(user_id) >= DAILY_FREE_LIMIT:
                    await query.message.reply_text(limit_reached_message(), reply_markup=limit_reached_keyboard())
                    return ConversationHandler.END
                session = create_session(
                    user_id      = user_id,
                    juz_number   = surah_info.get("juz", [1])[0],
                    surah_number = surah_num,
                    surah_name   = surah_info["name"],
                    direction    = "forward",
                    reciter      = "husary",
                    start_ayah   = next_ayah,
                )
                context.user_data["session"] = session
                await query.message.reply_text(
                    f"▶️ Davom etilmoqda: {surah_info['name']} — {next_ayah}-oyatdan"
                )
                return await _send_current_ayah(query.message.chat_id, context, user_id)
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
        context.user_data["reciter"] = "husary"
        surahs = get_surahs_in_juz(juz_number)
        await query.message.reply_text(
            f"📖 {juz_number}-juz tanlandi\n\nBoshlash uchun tugmani bosing yoki surani tanlang:",
            reply_markup=surah_selection_keyboard(surahs)
        )
        return MEMO_SELECT_SURAH


async def direction_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    direction = "forward" if query.data == "dir_forward" else "backward"
    context.user_data["direction"] = direction
    context.user_data["reciter"] = "husary"
    juz_number = context.user_data.get("juz_number")
    surahs = get_surahs_in_juz(juz_number)
    if direction == "backward":
        surahs = list(reversed(surahs))
    await query.message.reply_text(
        "📖 Boshlash uchun tugmani bosing yoki surani tanlang:",
        reply_markup=surah_selection_keyboard(surahs)
    )
    return MEMO_SELECT_SURAH


async def reciter_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "reciter_locked":
        db_user = get_user(query.from_user.id)
        premium = is_premium(db_user)
        await query.message.reply_text(
            "💎 Bu qori faqat Premium foydalanuvchilar uchun.\n\n"
            "Husary (Muallim) bepul foydalanish mumkin.\n"
            "Premium olish uchun: /start → 💎 Premium"
        )
        await query.message.reply_text("🎙️ Qori tanlang:", reply_markup=reciter_keyboard(for_memorize=True, is_premium=premium))
        return MEMO_SELECT_RECITER

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

    # Close any existing active sessions to prevent conflicts
    existing = get_active_session(user_id)
    if existing:
        close_session(existing["session_id"])

    # Resume from saved progress for this surah (if any)
    prog = get_memorization_progress(user_id)
    if prog.get("current_surah") == surah_info["number"]:
        start_ayah = prog.get("current_ayah", 1)
    else:
        start_ayah = 1

    # Create session
    session = create_session(
        user_id     = user_id,
        juz_number  = juz_number,
        surah_number= surah_info["number"],
        surah_name  = surah_info["name"],
        direction   = direction,
        reciter     = reciter,
        start_ayah  = start_ayah,
    )
    context.user_data["session"] = session

    chat_id = query.message.chat_id
    return await _send_current_ayah(chat_id, context, user_id)


# ─── Core Memorize Flow ───────────────────────────────────────────────────────

async def _send_current_ayah(chat_id: int, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Send the current ayah: header + audio + [photo] + text+button.
    Tracks sent message IDs in context.user_data['step_msgs'] for later cleanup.
    """
    bot     = context.bot
    session = context.user_data.get("session", {})
    surah_num   = session["surah_number"]
    surah_name  = session["surah_name"]
    reciter     = session["reciter"]
    acc_ayahs   = session.get("accumulated_ayahs", [])
    start_ayah  = session.get("start_ayah", 1)
    next_index  = start_ayah + len(acc_ayahs)

    ayah_data = get_ayah(surah_num, next_index)
    if not ayah_data:
        await bot.send_message(chat_id, "API xatoligi. Iltimos, qayta urinib ko'ring.")
        return ConversationHandler.END

    surah_info  = get_surah_by_number(surah_num)
    total_ayahs = surah_info["ayah_count"] if surah_info else 999

    step_msgs = []  # message IDs to delete after ayah is completed

    # Bismillah for first ayah (except Fatiha=1 which already has it, and Tawba=9 which has none)
    if next_index == 1 and surah_num not in (1, 9):
        bismillah = "﷽\nبِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"
        m = await bot.send_message(chat_id, bismillah)
        step_msgs.append(m.message_id)

    # Header
    m = await bot.send_message(chat_id, ayah_header(surah_name, surah_num, next_index, total_ayahs))
    step_msgs.append(m.message_id)

    # Ayah photo (if admin has added one) — shown BEFORE audio
    photo_file_id = get_ayah_photo(surah_num, next_index)
    logger.info(f"Ayah photo lookup: surah={surah_num}, ayah={next_index}, found={bool(photo_file_id)}")
    if photo_file_id:
        try:
            m = await bot.send_photo(chat_id, photo=photo_file_id,
                                     caption=f"📖 {surah_name} — {next_index}-oyat")
            step_msgs.append(m.message_id)
        except Exception as e:
            logger.error(f"Ayah photo send FAILED for {surah_num}:{next_index} — file_id={photo_file_id[:20]}… — error: {e}")
            photo_file_id = None  # mark as unavailable for this session

    # Audio — shown AFTER photo, BEFORE text
    audio_url = get_audio_url(ayah_data["global_number"], reciter)
    try:
        m = await bot.send_audio(chat_id, audio=audio_url)
        step_msgs.append(m.message_id)
    except Exception as e:
        logger.warning(f"Audio send failed: {e}")
        m = await bot.send_message(chat_id, f"🎧 Audio: {audio_url}")
        step_msgs.append(m.message_id)

    # Text + 3x button
    await bot.send_message(
        chat_id,
        ayah_text_message(ayah_data["arabic"], ayah_data["uzbek"], rep_instruction(3), 3),
        reply_markup=repetition_keyboard(3, "3")
    )

    # Track IDs for cleanup (everything EXCEPT the button message itself)
    context.user_data["step_msgs"] = step_msgs
    context.user_data["chat_id"]   = chat_id

    # Save ayah data to session (include photo_file_id to avoid repeated Firestore reads)
    ayah_record = {
        "arabic":        ayah_data["arabic"],
        "uzbek":         ayah_data["uzbek"],
        "global_number": ayah_data["global_number"],
        "surah_number":  surah_num,
        "ayah_number":   next_index,
        "photo_file_id": photo_file_id,  # may be None
    }
    from datetime import datetime
    import pytz
    _tz = pytz.timezone("Asia/Tashkent")
    ayah_started_at = datetime.now(_tz)

    update_session(session["session_id"], {
        "current_ayah_index": next_index,
        "stage":              "rep_3",
        "current_ayah_data":  ayah_record,
    })
    session["current_ayah_index"] = next_index
    session["stage"]              = "rep_3"
    session["current_ayah_data"]  = ayah_record
    context.user_data["session"]  = session
    context.user_data["_cur_ayah"] = ayah_record  # fast fallback for rep_3/rep_7
    context.user_data["_ayah_started_at"] = ayah_started_at

    return MEMO_REP_3


async def _cleanup_step(context: ContextTypes.DEFAULT_TYPE, query):
    """Delete the button message and any tracked step messages (including mid-step photos)."""
    chat_id = query.message.chat_id
    try:
        await query.message.delete()
    except Exception:
        pass
    for mid in context.user_data.pop("step_msgs", []):
        try:
            await context.bot.delete_message(chat_id, mid)
        except Exception:
            pass
    for mid in context.user_data.pop("mid_msgs", []):
        try:
            await context.bot.delete_message(chat_id, mid)
        except Exception:
            pass


async def rep_3_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Double-tap guard: remove buttons atomically; bail if already removed
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        return

    user_id = query.from_user.id
    chat_id = query.message.chat_id
    try:
        await query.message.delete()
    except Exception:
        pass

    session = await _recover_session(context, query.from_user.id)
    if not session.get("session_id"):
        await context.bot.send_message(chat_id, "Sessiya topilmadi. Qaytadan boshlang.")
        return ConversationHandler.END

    level_up = award_points(user_id, points_for_repetition(3), "rep_3")
    if level_up:
        await context.bot.send_message(chat_id, level_up_message(level_up[1]))

    ayah_data = context.user_data.get("_cur_ayah") or session.get("current_ayah_data", {})

    await context.bot.send_message(
        chat_id,
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
    query = update.callback_query
    await query.answer()
    # Double-tap guard
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        return

    user_id = query.from_user.id
    chat_id = query.message.chat_id
    try:
        await query.message.delete()
    except Exception:
        pass

    session = await _recover_session(context, query.from_user.id)
    if not session.get("session_id"):
        await context.bot.send_message(chat_id, "Sessiya topilmadi. Qaytadan boshlang.")
        return ConversationHandler.END

    level_up = award_points(user_id, points_for_repetition(7), "rep_7")
    if level_up:
        await context.bot.send_message(chat_id, level_up_message(level_up[1]))

    ayah_data = context.user_data.get("_cur_ayah") or session.get("current_ayah_data", {})

    await context.bot.send_message(
        chat_id,
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
    # Double-tap guard
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        return

    user_id = query.from_user.id
    chat_id = query.message.chat_id
    session = await _recover_session(context, query.from_user.id)
    if not session.get("session_id"):
        await context.bot.send_message(chat_id, "Sessiya topilmadi. Qaytadan boshlang.")
        return ConversationHandler.END

    # Delete button message + header/audio/photo
    await _cleanup_step(context, query)

    # Bonuses and points
    first_ayah_bonus = check_and_award_first_ayah(user_id)
    check_and_award_daily_login(user_id)
    level_up = award_points(user_id, points_for_repetition(11) + points_for_ayah_complete(), "rep_11+ayah")
    if level_up:
        await context.bot.send_message(chat_id, level_up_message(level_up[1]))

    # Calculate actual time spent on this ayah
    from datetime import datetime
    import pytz
    _tz = pytz.timezone("Asia/Tashkent")
    _ayah_start = context.user_data.get("_ayah_started_at")
    if _ayah_start:
        _elapsed = (datetime.now(_tz) - _ayah_start).total_seconds()
        _minutes = max(1, int(_elapsed / 60))
    else:
        _minutes = 5  # fallback

    add_activity_to_period_safe(user_id, 1, 3+7+11, _minutes, points_for_repetition(11), [session.get("surah_name", "")])

    from datetime import date as _date
    _today_key = f"_streak_updated_{_date.today().isoformat()}"
    if not context.user_data.get(_today_key):
        context.user_data[_today_key] = True
        new_streak, streak_broken, streak_bonus = apply_streak_update(user_id)
        if streak_bonus:
            await context.bot.send_message(chat_id, f"🔥 {new_streak}-kunlik streak! +{streak_bonus} Himmat ball!")
        elif new_streak > 1 and not streak_broken:
            await context.bot.send_message(chat_id, f"🔥 Streak: {new_streak} kun davomida!")
    if first_ayah_bonus:
        await context.bot.send_message(chat_id, f"🌟 BIRINCHI OYAT! +25 Himmat ball! Tabriklaymiz!")

    # Add to accumulated ayahs list
    current_ayah = session.get("current_ayah_data", {})
    acc = session.get("accumulated_ayahs", [])
    acc.append(current_ayah)
    update_session(session["session_id"], {
        "accumulated_ayahs":   acc,
        "stage":               "accumulation",
        "session_ayahs_count": len(acc),
    })
    session["accumulated_ayahs"] = acc
    context.user_data["session"] = session

    # Save progress: next ayah to memorize = start_ayah + how many ayahs accumulated so far
    start_ayah_s = session.get("start_ayah", 1)
    next_to_memorize = start_ayah_s + len(acc)
    save_memorization_progress(user_id, session["surah_number"], session.get("surah_name", ""), next_to_memorize)

    # Free user daily limit check
    db_user = get_user(user_id)
    if not is_premium(db_user):
        daily_count = get_daily_ayah_count(user_id)
        if daily_count >= DAILY_FREE_LIMIT:
            await context.bot.send_message(chat_id, limit_reached_message(),
                                            reply_markup=limit_reached_keyboard())
            close_session(session["session_id"])
            return ConversationHandler.END

    # Show surah progress
    surah_num  = session.get("surah_number")
    surah_info = get_surah_by_number(surah_num) if surah_num else None
    if surah_info and surah_info.get("ayah_count", 0) > 1:
        try:
            await context.bot.send_message(
                chat_id,
                ayah_progress_message(surah_info["name"], len(acc), surah_info["ayah_count"])
            )
        except Exception:
            pass

    # Ayah 1: skip accumulation, go directly to ayah 2
    # Ayah 2+: send all accumulated ayahs together for 5x joint repetition
    if len(acc) == 1:
        return await _send_current_ayah(chat_id, context, user_id)

    return await _send_accumulation(chat_id, context, user_id, acc)


async def _send_accumulation(chat_id: int, context: ContextTypes.DEFAULT_TYPE, user_id: int, acc: list):
    """Send all accumulated ayahs together for 5x joint repetition."""
    bot     = context.bot
    session = context.user_data.get("session", {})
    reciter = session.get("reciter", "husary")

    acc_msgs = []
    for ayah in acc:
        audio_url = get_audio_url(ayah.get("global_number", 1), reciter)
        try:
            m = await bot.send_audio(chat_id, audio=audio_url)
            acc_msgs.append(m.message_id)
        except Exception as e:
            logger.warning(f"Accumulation audio error: {e}")

    await bot.send_message(
        chat_id,
        accumulation_message(acc),
        reply_markup=accumulation_keyboard(len(acc))
    )

    context.user_data["acc_msgs"] = acc_msgs
    update_session(session["session_id"], {"stage": "acc_5"})
    session["stage"] = "acc_5"
    context.user_data["session"] = session
    return MEMO_ACC_7  # reuse same state constant


async def accumulation_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    # Double-tap guard
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        return

    user_id = query.from_user.id
    chat_id = query.message.chat_id
    session = await _recover_session(context, query.from_user.id)
    if not session.get("session_id"):
        await context.bot.send_message(chat_id, "Sessiya topilmadi. Qaytadan boshlang.")
        return ConversationHandler.END

    # Delete the accumulation button message and acc audio messages
    try:
        await query.message.delete()
    except Exception:
        pass
    for mid in context.user_data.pop("acc_msgs", []):
        try:
            await context.bot.delete_message(chat_id, mid)
        except Exception:
            pass

    acc = session.get("accumulated_ayahs", [])
    level_up = award_points(user_id, points_for_accumulation(len(acc)), "accumulation")
    if level_up:
        await context.bot.send_message(chat_id, level_up_message(level_up[1]))

    # Checkpoint every 5 ayahs
    if len(acc) > 0 and len(acc) % 5 == 0:
        await context.bot.send_message(chat_id, checkpoint_message(len(acc)),
                                        reply_markup=checkpoint_keyboard())
        context.user_data["session"] = session
        return MEMO_ACCUMULATION

    # Surah completion check
    surah_info = get_surah_by_number(session["surah_number"])
    if surah_info and len(acc) >= surah_info["ayah_count"]:
        await _handle_surah_complete(chat_id, context, user_id, session, surah_info)
        return ConversationHandler.END

    return await _send_current_ayah(chat_id, context, user_id)


async def checkpoint_go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass
    chat_id = query.message.chat_id
    return await _send_current_ayah(chat_id, context, query.from_user.id)


async def checkpoint_save_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    session = context.user_data.get("session", {})
    close_session(session.get("session_id", ""))
    await query.message.reply_text(
        "💾 Progress saqlandi! Keyingi safar davom etasiz. 🌟"
    )
    return ConversationHandler.END


async def _handle_surah_complete(chat_id: int, context, user_id: int, session: dict, surah_info: dict):
    himmat = points_for_surah_complete(surah_info["ayah_count"])
    level_up = award_points(user_id, himmat, "surah_complete")
    await context.bot.send_message(chat_id, surah_complete_message(surah_info["name"], himmat))
    if level_up:
        await context.bot.send_message(chat_id, level_up_message(level_up[1]))

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


async def _recover_session(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> dict:
    """Get session from context; if missing, recover from Firestore."""
    session = context.user_data.get("session")
    if session and session.get("session_id") and session.get("surah_number"):
        return session
    # Try Firestore recovery
    session = get_active_session(user_id)
    if session:
        context.user_data["session"] = session
    return session or {}


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
        per_message=False,
    )
