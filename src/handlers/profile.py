"""Profile handler: /profile with dynamic XP display and full Back buttons."""
import json
import math
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from src.database import db
from src.i18n import t, badge_display, league_display, plan_label
from src.api import quran

def _make_bar(done: int, total: int, length: int = 8) -> tuple[str, int]:
    pct = int((done / total) * 100) if total else 0
    filled = round((done / total) * length) if total else 0
    bar = "🟩" * filled + "⬜" * (length - filled)
    return bar, pct

def _profile_keyboard(user_id: int) -> InlineKeyboardMarkup:
    from src.handlers.onboarding import main_menu_keyboard
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(user_id, "btn_settings"), callback_data="profile:settings"),
            InlineKeyboardButton(t(user_id, "btn_full_stats"), callback_data="profile:stats"),
        ],
        [InlineKeyboardButton(t(user_id, "btn_study_plan"), callback_data="profile:plan")],
        [InlineKeyboardButton(t(user_id, "btn_main_menu"), callback_data="menu:learn")],
    ])

async def _build_profile_text(user_id: int) -> str:
    game = db.get_gamification(user_id)
    settings = db.get_settings(user_id)
    progress = db.get_progress(user_id)
    total_memorized = sum(1 for r in progress if r["memorized"])

    current_surah_num = db.get_current_surah(user_id)
    surah_info = await quran.get_surah_info(current_surah_num)
    surah_name = surah_info["englishName"] if surah_info else f"Surah {current_surah_num}"
    total_ayahs = surah_info["numberOfAyahs"] if surah_info else 1
    done_in_surah = db.count_memorized_in_surah(user_id, current_surah_num)
    bar, pct = _make_bar(done_in_surah, total_ayahs)
    daily_goal = settings["daily_goal_ayahs"] if settings else 3
    remaining = max(total_ayahs - done_in_surah, 0)

    lines = [
        t(user_id, "profile_header"), "",
        t(user_id, "profile_surah", surah_name=surah_name, surah_num=current_surah_num),
        t(user_id, "profile_progress_bar", bar=bar, pct=pct, done=done_in_surah, total=total_ayahs), "",
        t(user_id, "profile_xp", xp=game["total_xp"] if game else 0),
        t(user_id, "profile_streak", streak=game["current_streak"] if game else 0),
        t(user_id, "profile_league", league=league_display(user_id, game["league"] if game else "bronze")),
        t(user_id, "profile_goal", goal=daily_goal), "",
    ]
    if remaining == 0:
        lines.append(t(user_id, "profile_projection_done"))
    else:
        days = math.ceil(remaining / daily_goal) if daily_goal > 0 else "∞"
        lines.append(t(user_id, "profile_projection", days=days))

    if game:
        badges_list = json.loads(game["badges"])
        if badges_list:
            lines.append(t(user_id, "profile_badges",
                           badges=" ".join(badge_display(user_id, b) for b in badges_list)))
        else:
            lines.append(t(user_id, "profile_no_badges"))

    # Top 3 Best Known Ayahs
    top_ayahs = db.get_top_ayahs(user_id, n=3)
    lang = dict(db.get_user(user_id) or {}).get("language", "en")
    if top_ayahs:
        lines.append("")
        lines.append("🏆 *Top 3 Eng Yaxshi Oyatlar:*" if lang == "uz" else "🏆 *Top 3 Best Known Ayahs:*")
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(top_ayahs):
            s_info = await quran.get_surah_info(row["surah_number"])
            s_name = s_info["englishName"] if s_info else f"Surah {row['surah_number']}"
            cnt = row["cnt"]
            medal = medals[i] if i < 3 else "•"
            lines.append(f"{medal} {s_name}, {row['ayah_number']}-oyat: {cnt}× to'g'ri 🔥" if lang == "uz"
                         else f"{medal} {s_name}, Ayah {row['ayah_number']}: {cnt}× correct 🔥")

    return "\n".join(lines)

async def _show_profile(query_or_msg, user_id: int, edit: bool = False):
    text = await _build_profile_text(user_id)
    keyboard = _profile_keyboard(user_id)
    if edit:
        try:
            await query_or_msg.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            await query_or_msg.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await query_or_msg.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not db.get_user(user.id):
        from src.i18n.en import STRINGS as EN
        await update.message.reply_text(EN["please_start"])
        return
    await _show_profile(update.message, user.id, edit=False)

async def cb_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    action = query.data.split(":")[1]

    if action == "back":
        await _show_profile(query, user.id, edit=True)

    elif action == "stats":
        game = db.get_gamification(user.id)
        game_d = dict(game) if game else {}
        progress = db.get_progress(user.id)
        total_memorized = sum(1 for r in progress if r["memorized"])
        surahs_touched = len(set(r["surah_number"] for r in progress))
        accuracy = db.get_quiz_accuracy(user.id)
        best = db.get_best_surah(user.id)
        lang = dict(db.get_user(user.id) or {}).get("language", "en")

        best_surah_name = ""
        if best:
            bs_info = await quran.get_surah_info(best["surah_number"])
            best_surah_name = bs_info["englishName"] if bs_info else f"Surah {best['surah_number']}"

        xp = game_d.get("total_xp", 0)
        streak = game_d.get("current_streak", 0)
        longest = game_d.get("longest_streak", 0)
        league = league_display(user.id, game_d.get("league", "bronze"))
        rec_count = game_d.get("recitation_count", 0)
        quiz_correct = game_d.get("quiz_correct_count", 0)

        if lang == "uz":
            text = (
                f"📊 *To'liq Statistika*\n\n"
                f"⭐ XP: *{xp}*\n"
                f"🔥 Seriya: *{streak}* (rekord: {longest})\n"
                f"🏆 Liga: {league}\n"
                f"📖 Yod olindi: *{total_memorized}* oyat ({surahs_touched} sura)\n"
                f"🎤 Tilavat soni: *{rec_count}*\n"
                f"✅ To'g'ri javoblar (umr): *{quiz_correct}*\n"
                f"📈 Quiz aniqligi: *{accuracy['pct']}%* ({accuracy['correct']}/{accuracy['total']})\n"
                + (f"⭐ Eng yaxshi Sura: *{best_surah_name}*" if best_surah_name else "")
            )
        else:
            text = (
                f"📊 *Full Statistics*\n\n"
                f"⭐ XP: *{xp}*\n"
                f"🔥 Streak: *{streak}* (best: {longest})\n"
                f"🏆 League: {league}\n"
                f"📖 Memorized: *{total_memorized}* Ayahs ({surahs_touched} Surahs)\n"
                f"🎤 Recitations: *{rec_count}*\n"
                f"✅ Quiz correct (lifetime): *{quiz_correct}*\n"
                f"📈 Quiz accuracy: *{accuracy['pct']}%* ({accuracy['correct']}/{accuracy['total']})\n"
                + (f"⭐ Best Surah: *{best_surah_name}*" if best_surah_name else "")
            )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(t(user.id, "btn_back_profile"), callback_data="profile:back")],
            [InlineKeyboardButton(t(user.id, "btn_main_menu"), callback_data="menu:learn")],
        ]))

    elif action == "settings":
        from src.handlers.settings import _show_settings_menu
        await _show_settings_menu(query, user.id, edit=True)

    elif action == "plan":
        settings = db.get_settings(user.id)
        plan = settings["study_plan"] if settings else "standard"
        text = f"📚 *Your Study Plan:* {plan_label(user.id, plan)}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(t(user.id, "btn_back_profile"), callback_data="profile:back")],
        ]))

def register(app):
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CallbackQueryHandler(cb_profile, pattern=r"^profile:"))
