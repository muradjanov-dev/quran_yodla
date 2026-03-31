"""30 achievements system with weekly XP competition and congrats broadcasts."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from src.database import db
from src.i18n import t

# ── 30 Achievements definition ────────────────────────────────────────────────
# Each entry: id, xp_bonus, condition_fn(stats) -> bool
# stats dict keys: total_memorized, streak, longest_streak, total_xp, weekly_xp,
#                  quiz_correct, quiz_total, recitations, xatm_completed,
#                  surahs_completed, juzs_completed, days_active

ACHIEVEMENTS = [
    # ── Memorization milestones
    {"id": "first_ayah",       "xp": 50,   "check": lambda s: s["total_memorized"] >= 1},
    {"id": "ayah_5",           "xp": 100,  "check": lambda s: s["total_memorized"] >= 5},
    {"id": "ayah_10",          "xp": 150,  "check": lambda s: s["total_memorized"] >= 10},
    {"id": "ayah_25",          "xp": 200,  "check": lambda s: s["total_memorized"] >= 25},
    {"id": "ayah_50",          "xp": 300,  "check": lambda s: s["total_memorized"] >= 50},
    {"id": "ayah_100",         "xp": 500,  "check": lambda s: s["total_memorized"] >= 100},
    {"id": "ayah_200",         "xp": 750,  "check": lambda s: s["total_memorized"] >= 200},
    {"id": "ayah_604",         "xp": 2000, "check": lambda s: s["total_memorized"] >= 604},
    # ── Streak milestones
    {"id": "streak_3",         "xp": 75,   "check": lambda s: s["streak"] >= 3},
    {"id": "streak_7",         "xp": 150,  "check": lambda s: s["streak"] >= 7},
    {"id": "streak_14",        "xp": 250,  "check": lambda s: s["streak"] >= 14},
    {"id": "streak_30",        "xp": 500,  "check": lambda s: s["streak"] >= 30},
    {"id": "streak_60",        "xp": 1000, "check": lambda s: s["streak"] >= 60},
    {"id": "streak_100",       "xp": 2000, "check": lambda s: s["streak"] >= 100},
    # ── Surah / Juz milestones
    {"id": "first_surah",      "xp": 200,  "check": lambda s: s["surahs_completed"] >= 1},
    {"id": "surah_3",          "xp": 400,  "check": lambda s: s["surahs_completed"] >= 3},
    {"id": "surah_10",         "xp": 800,  "check": lambda s: s["surahs_completed"] >= 10},
    {"id": "juz_amma",         "xp": 1000, "check": lambda s: s["juzs_completed"] >= 1},
    # ── Quiz milestones
    {"id": "quiz_10",          "xp": 50,   "check": lambda s: s["quiz_correct"] >= 10},
    {"id": "quiz_100",         "xp": 200,  "check": lambda s: s["quiz_correct"] >= 100},
    {"id": "quiz_500",         "xp": 500,  "check": lambda s: s["quiz_correct"] >= 500},
    {"id": "quiz_perfect",     "xp": 300,  "check": lambda s: s["quiz_total"] >= 10 and s["quiz_accuracy"] >= 97},
    # ── Recitation milestones
    {"id": "recite_1",         "xp": 75,   "check": lambda s: s["recitations"] >= 1},
    {"id": "recite_10",        "xp": 150,  "check": lambda s: s["recitations"] >= 10},
    {"id": "recite_50",        "xp": 400,  "check": lambda s: s["recitations"] >= 50},
    # ── Xatm milestones
    {"id": "xatm_join",        "xp": 100,  "check": lambda s: s["xatm_completed"] >= 1},
    {"id": "xatm_3",           "xp": 500,  "check": lambda s: s["xatm_completed"] >= 3},
    # ── XP milestones
    {"id": "xp_1000",          "xp": 100,  "check": lambda s: s["total_xp"] >= 1000},
    {"id": "xp_5000",          "xp": 300,  "check": lambda s: s["total_xp"] >= 5000},
    # ── Weekly competition
    {"id": "weekly_top3",      "xp": 500,  "check": lambda s: s.get("weekly_rank", 99) <= 3},
]

ACHIEVEMENT_IDS = {a["id"] for a in ACHIEVEMENTS}
ACHIEVEMENT_MAP = {a["id"]: a for a in ACHIEVEMENTS}


def _build_stats(user_id: int) -> dict:
    """Gather all stats needed to evaluate achievements."""
    import sqlite3, json
    conn = sqlite3.connect(str(db.DB_PATH))
    conn.row_factory = sqlite3.Row

    prog = conn.execute(
        "SELECT COUNT(*) FROM progress WHERE user_id=? AND memorized=1", (user_id,)
    ).fetchone()[0]

    gm = conn.execute("SELECT * FROM gamification WHERE user_id=?", (user_id,)).fetchone()
    gm = dict(gm) if gm else {}

    quiz_correct = conn.execute(
        "SELECT COUNT(*) FROM ayah_interactions WHERE user_id=? AND interaction='quiz_correct'",
        (user_id,)
    ).fetchone()[0]
    quiz_wrong = conn.execute(
        "SELECT COUNT(*) FROM ayah_interactions WHERE user_id=? AND interaction='quiz_wrong'",
        (user_id,)
    ).fetchone()[0]
    recitations = conn.execute(
        "SELECT COUNT(*) FROM ayah_interactions WHERE user_id=? AND interaction='recitation'",
        (user_id,)
    ).fetchone()[0]

    surahs_done = conn.execute(
        "SELECT COUNT(DISTINCT surah_number) FROM progress WHERE user_id=? AND memorized=1",
        (user_id,)
    ).fetchone()[0]

    xatm_done = conn.execute(
        "SELECT COUNT(*) FROM group_xatm_juzs j "
        "JOIN group_xatms x ON x.id=j.xatm_id "
        "WHERE j.user_id=? AND j.status='completed' AND x.status='completed'",
        (user_id,)
    ).fetchone()[0]

    week = db._current_week_start()
    wxp_row = conn.execute(
        "SELECT xp FROM weekly_xp WHERE user_id=? AND week_start=?", (user_id, week)
    ).fetchone()
    weekly_xp = wxp_row["xp"] if wxp_row else 0

    conn.close()

    quiz_total = quiz_correct + quiz_wrong
    quiz_accuracy = int(quiz_correct / quiz_total * 100) if quiz_total > 0 else 0

    return {
        "total_memorized": prog,
        "streak": gm.get("current_streak", 0),
        "longest_streak": gm.get("longest_streak", 0),
        "total_xp": gm.get("total_xp", 0),
        "weekly_xp": weekly_xp,
        "quiz_correct": quiz_correct,
        "quiz_total": quiz_total,
        "quiz_accuracy": quiz_accuracy,
        "recitations": recitations,
        "surahs_completed": surahs_done,
        "juzs_completed": xatm_done,  # using completed xatm juzs as proxy
        "xatm_completed": xatm_done,
    }


async def check_and_award(user_id: int, bot) -> list[str]:
    """Check all achievements for user, unlock new ones, return list of newly unlocked IDs."""
    stats = _build_stats(user_id)
    newly_unlocked = []

    for ach in ACHIEVEMENTS:
        if db.has_achievement(user_id, ach["id"]):
            continue
        try:
            if ach["check"](stats):
                if db.unlock_achievement(user_id, ach["id"]):
                    newly_unlocked.append(ach["id"])
                    # Bonus XP for the achievement
                    db.add_xp(user_id, ach["xp"])
                    db.add_weekly_xp(user_id, ach["xp"])
        except Exception:
            pass

    for ach_id in newly_unlocked:
        await _notify_achiever(user_id, ach_id, bot)
        db.enqueue_congrats(user_id, ach_id)

    return newly_unlocked


async def _notify_achiever(user_id: int, ach_id: str, bot):
    """Send congrats message to the user who earned the achievement."""
    ach = ACHIEVEMENT_MAP.get(ach_id, {})
    lang = _lang(user_id)
    name_uz, name_en = _ach_names(ach_id)
    ach_name = name_uz if lang == "uz" else name_en
    bonus_xp = ach.get("xp", 0)

    if lang == "uz":
        text = (
            f"🏆 *Yutuq ochildi!*\n\n"
            f"*{ach_name}*\n\n"
            f"_{_ach_desc_uz(ach_id)}_\n\n"
            f"⭐ +{bonus_xp} XP bonus"
        )
    else:
        text = (
            f"🏆 *Achievement Unlocked!*\n\n"
            f"*{ach_name}*\n\n"
            f"_{_ach_desc_en(ach_id)}_\n\n"
            f"⭐ +{bonus_xp} XP bonus"
        )
    try:
        await bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
    except Exception as e:
        print(f"[Achievements] notify_achiever failed for {user_id}: {e}")


async def flush_congrats_queue(bot):
    """Called periodically — drains congrats queue, max MAX_CONGRATS_PER_DAY per recipient."""
    all_ids = db.get_all_user_ids()
    for uid in all_ids:
        sent_today = db.get_congrats_sent_today(uid)
        remaining = db.MAX_CONGRATS_PER_DAY - sent_today
        if remaining <= 0:
            continue
        pending = db.get_pending_congrats_for(uid, limit=remaining)
        for item in pending:
            await _send_congrats_notification(uid, item, bot)
            db.mark_congrats_sent(item["id"])


async def _send_congrats_notification(recipient_id: int, item: dict, bot):
    """Send broadcast notification to a user about someone else's achievement."""
    lang = _lang(recipient_id)
    achiever_name = item["achiever_name"]
    ach_id = item["achievement_id"]
    achiever_id = item["achiever_id"]
    name_uz, name_en = _ach_names(ach_id)
    ach_name = name_uz if lang == "uz" else name_en

    if lang == "uz":
        text = (
            f"🎉 *{achiever_name}* yangi yutuqqa erishdi!\n\n"
            f"🏆 *{ach_name}*\n\n"
            f"Uni tabriklamaysizmi?"
        )
        btn_label = "🤝 Tabrikling!"
    else:
        text = (
            f"🎉 *{achiever_name}* just earned an achievement!\n\n"
            f"🏆 *{ach_name}*\n\n"
            f"Want to congratulate them?"
        )
        btn_label = "🤝 Congratulate!"

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(btn_label,
                             callback_data=f"congrats:send:{achiever_id}:{ach_id}")
    ]])
    try:
        await bot.send_message(chat_id=recipient_id, text=text,
                               parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        print(f"[Achievements] congrats notify failed for {recipient_id}: {e}")


async def cb_congrats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler: user taps Congratulate button — sends fireworks to achiever + confirms to tapper."""
    query = update.callback_query
    # Show fireworks animation to the tapper immediately via answer()
    await query.answer(text="🎆🎇✨ Tabrik yuborildi!", show_alert=False)

    parts = query.data.split(":")
    if len(parts) < 4:
        return
    achiever_id = int(parts[2])
    ach_id = parts[3]
    sender_id = query.from_user.id
    sender_name = query.from_user.first_name or "Kimdir"
    lang_achiever = _lang(achiever_id)
    name_uz, name_en = _ach_names(ach_id)
    ach_name = name_uz if lang_achiever == "uz" else name_en

    # ── Fireworks message to the achiever ──────────────────────────────────────
    fireworks = "🎆🎇🎉🎊✨🌟🏆🎆🎇🎉"
    if lang_achiever == "uz":
        msg = (
            f"{fireworks}\n\n"
            f"🤝 *{sender_name}* seni tabrikladingiz!\n\n"
            f"🏆 *{ach_name}* yutuqqa erishganingiz uchun!\n\n"
            f"_Xayrli va bardavom bo'lsin. Alloh muvaffaqiyat bersin!_ 🌙\n\n"
            f"{fireworks}"
        )
    else:
        msg = (
            f"{fireworks}\n\n"
            f"🤝 *{sender_name}* just congratulated you!\n\n"
            f"🏆 For earning the *{ach_name}* achievement!\n\n"
            f"_May it be blessed and lasting. May Allah grant you continued success!_ 🌙\n\n"
            f"{fireworks}"
        )

    try:
        await context.bot.send_message(chat_id=achiever_id, text=msg, parse_mode="Markdown")
    except Exception:
        pass

    # ── Remove the button so it can't be tapped again + confirm to tapper ─────
    lang_sender = _lang(sender_id)
    if lang_sender == "uz":
        confirm = "🎆 Tabrikingiz yuborildi! Alloh barakot bersin."
    else:
        confirm = "🎆 Your congratulations was sent! Barakallah."
    try:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(confirm)
    except Exception:
        pass


def register(app):
    app.add_handler(CallbackQueryHandler(cb_congrats, pattern=r"^congrats:send:"))


# ── Weekly competition ────────────────────────────────────────────────────────

async def run_weekly_announcement(bot):
    """Send weekly top-5 to all users + award weekly_top3 achievement. Called Sunday 22:00."""
    top = db.get_weekly_leaderboard(limit=5)
    if not top:
        return

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = []
    for i, row in enumerate(top):
        lines.append(f"{medals[i]} *{row['name']}* — {row['weekly_xp']} XP")

    all_ids = db.get_all_user_ids()
    top3_ids = {row["user_id"] for row in top[:3]}

    for uid in all_ids:
        lang = _lang(uid)
        if lang == "uz":
            text = (
                f"🏆 *Haftalik Musobaqa Yakunlandi!*\n\n"
                f"Bu haftaning eng faol Hifz o'rganuvchilari:\n\n"
                + "\n".join(lines) +
                f"\n\n_Tabriklar! Keyingi hafta yangi musobaqa boshlanadi._"
            )
        else:
            text = (
                f"🏆 *Weekly Competition Results!*\n\n"
                f"This week's top Hifz learners:\n\n"
                + "\n".join(lines) +
                f"\n\n_Congratulations! A new competition starts next week._"
            )
        try:
            await bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
        except Exception:
            pass

    # Award weekly_top3 achievement to top 3
    for uid in top3_ids:
        if db.unlock_achievement(uid, "weekly_top3"):
            ach = ACHIEVEMENT_MAP["weekly_top3"]
            db.add_xp(uid, ach["xp"])
            await _notify_achiever(uid, "weekly_top3", bot)

    # Reset weekly XP
    db.reset_weekly_xp()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _lang(user_id: int) -> str:
    u = db.get_user(user_id)
    return dict(u).get("language", "en") if u else "en"


def _ach_names(ach_id: str) -> tuple[str, str]:
    """Returns (uz_name, en_name)."""
    names = {
        "first_ayah":    ("Birinchi Qadam", "First Step"),
        "ayah_5":        ("5 Oyat Hofizi", "5 Ayahs Memorized"),
        "ayah_10":       ("10 Oyat Hofizi", "10 Ayahs Memorized"),
        "ayah_25":       ("25 Oyat Hofizi", "25 Ayahs Memorized"),
        "ayah_50":       ("50 Oyat Ustasi", "50 Ayahs Master"),
        "ayah_100":      ("100 Oyat Chempioni", "100 Ayahs Champion"),
        "ayah_200":      ("200 Oyat Yulduzi", "200 Ayahs Star"),
        "ayah_604":      ("To'liq Hofiz", "Complete Hafiz"),
        "streak_3":      ("3 Kunlik Seriya", "3-Day Streak"),
        "streak_7":      ("Hafta Jangchisi", "Week Warrior"),
        "streak_14":     ("Ikki Hafta Qahramoni", "Two-Week Hero"),
        "streak_30":     ("Oylik Mustahkamlik", "Monthly Dedication"),
        "streak_60":     ("Ikki Oylik Iroda", "Two-Month Iron Will"),
        "streak_100":    ("100 Kun Afsonasi", "100-Day Legend"),
        "first_surah":   ("Birinchi Sura", "First Surah"),
        "surah_3":       ("3 Sura Hofizi", "3 Surahs Memorized"),
        "surah_10":      ("10 Sura Hofizi", "10 Surahs Memorized"),
        "juz_amma":      ("Juz Hofizi", "Juz Memorized"),
        "quiz_10":       ("Test Boshlovchisi", "Quiz Starter"),
        "quiz_100":      ("Test Ustasi", "Quiz Master"),
        "quiz_500":      ("Test Afsonasi", "Quiz Legend"),
        "quiz_perfect":  ("Mukammal Test", "Perfect Quiz"),
        "recite_1":      ("Birinchi Tilavat", "First Recitation"),
        "recite_10":     ("10 Marta Tilovat", "10 Recitations"),
        "recite_50":     ("Tilovat Ustasi", "Recitation Master"),
        "xatm_join":     ("Xatm Ishtirokchisi", "Khatm Participant"),
        "xatm_3":        ("Xatm Qahramoni", "Khatm Hero"),
        "xp_1000":       ("1000 XP", "1000 XP"),
        "xp_5000":       ("5000 XP Yulduzi", "5000 XP Star"),
        "weekly_top3":   ("Haftalik Top-3", "Weekly Top 3"),
    }
    pair = names.get(ach_id, (ach_id, ach_id))
    return pair


def _ach_desc_uz(ach_id: str) -> str:
    descs = {
        "first_ayah":    "Birinchi oyatingizni yod oldingiz. Ajoyib boshlang'ich!",
        "ayah_5":        "5 ta oyat yod oldingiz. Davom eting!",
        "ayah_10":       "10 ta oyat yod oldingiz — bu zo'r natija!",
        "ayah_25":       "25 ta oyat! Siz haqiqiy Hifz yo'lida!",
        "ayah_50":       "50 ta oyat yod olindi. Mashallah!",
        "ayah_100":      "100 ta oyat — siz chempionsiz!",
        "ayah_200":      "200 ta oyat. Alloh sizni barakali qilsin!",
        "ayah_604":      "To'liq Qur'on yod olindi! Subhanallah!",
        "streak_3":      "3 kun ketma-ket. Odatga aylanyapti!",
        "streak_7":      "7 kunlik seriya — Hafta Jangchisi!",
        "streak_14":     "14 kun to'xtovsiz. Irodangiz mustahkam!",
        "streak_30":     "30 kunlik seriya — oylik sadoqat!",
        "streak_60":     "60 kun to'xtovsiz. Bu haqiqiy iroda!",
        "streak_100":    "100 kunlik seriya — afsona darajasi!",
        "first_surah":   "Birinchi surani to'liq yod oldingiz!",
        "surah_3":       "3 ta sura yod olindi. Zo'r natija!",
        "surah_10":      "10 ta sura — siz ulug' Hofiz bo'lyapsiz!",
        "juz_amma":      "Bir juzni yod oldingiz. Tabriklash munosib!",
        "quiz_10":       "10 ta savolga to'g'ri javob berdingiz.",
        "quiz_100":      "100 ta to'g'ri javob — Test Ustasi!",
        "quiz_500":      "500 ta to'g'ri javob — Afsona!",
        "quiz_perfect":  "97%+ natija bilan mukammal test!",
        "recite_1":      "Birinchi ovozli tilavatingiz qabul bo'lsin!",
        "recite_10":     "10 marta ovozli tilovat — mashq davom etyapti!",
        "recite_50":     "50 marta tilovat — haqiqiy Tilovat Ustasi!",
        "xatm_join":     "Jamoaviy Xatmda bir juzni tugatdingiz!",
        "xatm_3":        "3 ta Xatmda ishtirok etdingiz. Qahramon!",
        "xp_1000":       "1000 XP to'plandi. Katta yul bosib o'tdingiz!",
        "xp_5000":       "5000 XP — siz haqiqiy yulduz bo'ldingiz!",
        "weekly_top3":   "Bu hafta top-3 o'rinda bo'ldingiz. Barakalla!",
    }
    return descs.get(ach_id, "Yutuqqa erishdingiz!")


def _ach_desc_en(ach_id: str) -> str:
    descs = {
        "first_ayah":    "You memorized your first Ayah. What a start!",
        "ayah_5":        "5 Ayahs memorized. Keep going!",
        "ayah_10":       "10 Ayahs — you're on the right path!",
        "ayah_25":       "25 Ayahs! You're truly on the Hifz journey!",
        "ayah_50":       "50 Ayahs memorized. Masha'Allah!",
        "ayah_100":      "100 Ayahs — you're a champion!",
        "ayah_200":      "200 Ayahs. May Allah bless your efforts!",
        "ayah_604":      "Full Quran memorized! Subhanallah!",
        "streak_3":      "3 days in a row. It's becoming a habit!",
        "streak_7":      "7-day streak — Week Warrior!",
        "streak_14":     "14 days without stopping. Strong will!",
        "streak_30":     "30-day streak — monthly dedication!",
        "streak_60":     "60 days straight. True iron will!",
        "streak_100":    "100-day streak — legendary level!",
        "first_surah":   "First full Surah memorized!",
        "surah_3":       "3 Surahs memorized. Great achievement!",
        "surah_10":      "10 Surahs — you're becoming a great Hafiz!",
        "juz_amma":      "One full Juz memorized. Remarkable!",
        "quiz_10":       "10 correct quiz answers. Well done!",
        "quiz_100":      "100 correct answers — Quiz Master!",
        "quiz_500":      "500 correct answers — Quiz Legend!",
        "quiz_perfect":  "97%+ accuracy — Perfect Quiz!",
        "recite_1":      "Your first voice recitation. May it be accepted!",
        "recite_10":     "10 voice recitations — practice is ongoing!",
        "recite_50":     "50 recitations — true Recitation Master!",
        "xatm_join":     "Completed a Juz in a Group Khatm!",
        "xatm_3":        "Participated in 3 Khatms. A true hero!",
        "xp_1000":       "1000 XP earned. A great milestone!",
        "xp_5000":       "5000 XP — you're a true star!",
        "weekly_top3":   "You were in the top 3 this week. Barakallah!",
    }
    return descs.get(ach_id, "Achievement unlocked!")
