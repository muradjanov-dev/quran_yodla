"""
listen.py — Tinglash (Listen) handler.
"""

import logging
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler,
    MessageHandler, CallbackQueryHandler, filters, CommandHandler
)

from config import LISTEN_SELECT_SURAH, RECITERS
from utils.keyboards import listen_reciter_keyboard, listen_juz_keyboard
from utils.messages import listen_menu_message, listen_surah_prompt, listen_audio_message
from utils.helpers import search_surah, get_surahs_in_juz
from services.quran_api import get_surah_audio_url

logger = logging.getLogger(__name__)


async def open_listen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or (update.callback_query and update.callback_query.message)
    if update.callback_query:
        await update.callback_query.answer()
    await msg.reply_text(
        listen_menu_message(),
        reply_markup=listen_reciter_keyboard()
    )
    return LISTEN_SELECT_SURAH


async def listen_reciter_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query        = update.callback_query
    await query.answer()
    reciter_key  = query.data.replace("listen_reciter_", "")
    reciter_info = RECITERS.get(reciter_key)
    if not reciter_info:
        return

    context.user_data["listen_reciter"] = reciter_key
    await query.message.reply_text(
        listen_surah_prompt(reciter_info["name"]),
        reply_markup=listen_juz_keyboard()
    )
    return LISTEN_SELECT_SURAH


async def listen_juz_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query      = update.callback_query
    await query.answer()
    juz_number = int(query.data.replace("listen_juz_", ""))
    surahs     = get_surahs_in_juz(juz_number)
    reciter    = context.user_data.get("listen_reciter", "afasy")

    if not surahs:
        await query.message.reply_text("Juz ma'lumotlari topilmadi.")
        return ConversationHandler.END

    # Send first surah of juz
    surah_info = surahs[0]
    return await _send_surah_audio(query.message, reciter, surah_info)


async def listen_surah_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User typed surah name/number."""
    text       = update.message.text.strip()
    reciter    = context.user_data.get("listen_reciter", "afasy")
    surah_info = search_surah(text)

    if not surah_info:
        await update.message.reply_text(
            "❌ Sura topilmadi. Qayta kiriting (masalan: 36 yoki Ya-Sin):"
        )
        return LISTEN_SELECT_SURAH

    return await _send_surah_audio(update.message, reciter, surah_info)


async def _send_surah_audio(message, reciter_key: str, surah_info: dict):
    reciter_info = RECITERS.get(reciter_key, RECITERS["afasy"])
    audio_url    = get_surah_audio_url(surah_info["number"], reciter_key)

    await message.reply_text(
        f"🎵 {surah_info['name']} ({surah_info['name_arabic']}) — {reciter_info['name']}\n\n"
        f"Audio yuklanmoqda..."
    )

    try:
        await message.reply_audio(
            audio=audio_url,
            title=surah_info["name"],
            performer=reciter_info["name"].replace("🎵 ", ""),
        )
    except Exception as e:
        logger.warning(f"Audio send failed: {e}")
        await message.reply_text(
            listen_audio_message(surah_info["name"], reciter_info["name"], audio_url),
            parse_mode="Markdown"
        )
    return ConversationHandler.END


def build_listen_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🎧 Tinglash$"), open_listen),
        ],
        states={
            LISTEN_SELECT_SURAH: [
                CallbackQueryHandler(listen_reciter_selected, pattern="^listen_reciter_"),
                CallbackQueryHandler(listen_juz_selected,     pattern="^listen_juz_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, listen_surah_text),
            ],
        },
        fallbacks=[CommandHandler("start", lambda u, c: ConversationHandler.END)],
        allow_reentry=True,
        name="listen",
        per_message=False,
    )
