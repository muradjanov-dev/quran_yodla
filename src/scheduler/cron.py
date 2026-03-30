"""Updated scheduler: reminders + daily motivation + xatm reminders + admin daily report."""
from datetime import datetime, date, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.database import db

ADMIN_ID = db.ADMIN_ID

MOTIVATIONS_EN = [
    ("🌙 *The Quran awaits you.*\n\n"
     "Every Ayah you memorize is a seed planted in paradise.\n"
     "_\"The best of you are those who learn the Quran and teach it.\"_\n\n"
     "Start your journey today!"),
    ("🌅 *Small steps, eternal rewards.*\n\n"
     "Even one Ayah a day, done consistently, is more beloved "
     "to Allah than a thousand deeds done once.\n\n"
     "Set your goal now and begin!"),
    ("🔥 *Your streak is zero — but it doesn't have to be.*\n\n"
     "Every great Hafiz started exactly where you are now.\n"
     "_\"Indeed, with hardship comes ease.\"_ (94:5)\n\n"
     "Today is the day."),
    ("📖 *The Quran is a healer.*\n\n"
     "Whatever you're going through right now, "
     "spending a few minutes with Allah's words will bring peace.\n"
     "Begin. Just one Ayah."),
    ("💪 *Champions are built in the quiet moments.*\n\n"
     "No one sees the daily effort — but Allah does.\n"
     "And the Hifz you build today will be your companion forever."),
]

MOTIVATIONS_UZ = [
    ("🌙 *Qur'on sizni kutmoqda.*\n\n"
     "Yod olgan har bir oyatingiz jannatda ekilgan urug'dir.\n"
     "_«Sizlarning eng yaxshingiz Qur'onni o'rganib, o'rgatgandur.»_\n\n"
     "Bugun safaringizni boshlang!"),
    ("🌅 *Kichik qadamlar — abadiy mukofotlar.*\n\n"
     "Har kuni bitta oyat ham muntazam qilinsa, "
     "Alloh oldida bir marta qilingan ming amaldan muhimroq.\n\n"
     "Maqsadingizni belgilab, boshlang!"),
    ("🔥 *Seriyangiz nolda — lekin shunday qolaverishi shart emas.*\n\n"
     "Har bir Hofiz aynan sizning holingizdan boshlagan.\n"
     "_«Darvoqe, qiyinchilik bilan birga osonlik ham bor.»_ (94:5)\n\n"
     "Bugun — shu kun."),
    ("📖 *Qur'on shifo beruvchi.*\n\n"
     "Nima bilan kurashayotgan bo'lsangiz, "
     "Allohning so'zlari bilan bir necha daqiqa o'tkazish tinchlik beradi.\n"
     "Boshlang. Faqat bitta oyat."),
    ("💪 *Chempionlar jimgina quriladi.*\n\n"
     "Kunlik sa'y-harakatni hech kim ko'rmaydi — lekin Alloh ko'radi.\n"
     "Bugun qurayotgan Hifzingiz sizga abadiy hamroh bo'ladi."),
]

_day_counter = [0]  # mutable container to allow mutation from async function

async def run_reminders(bot):
    """Fires reminder messages (or interactive quiz) for all users whose reminder time matches current HH:MM."""
    now_str = datetime.now().strftime("%H:%M")
    users = db.get_all_users_for_reminder(now_str)

    for row in users:
        user_id = row["id"]
        name = row["name"]
        goal = row["daily_goal_ayahs"] if row["daily_goal_ayahs"] else 3
        lang = row.get("language", "en") if hasattr(row, "get") else dict(row).get("language", "en")

        game = db.get_gamification(user_id)
        streak = game["current_streak"] if game else 0

        from src.i18n import t
        last = game["last_activity"] if game else None
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        streak_just_lost = last and last < yesterday and streak == 0

        # Try to build an interactive quiz reminder if user has memorized ayahs
        memorized = db.get_memorized_ayahs(user_id)
        sent_quiz = False

        if memorized and not streak_just_lost:
            import random, base64
            from src.api import quran as quran_api
            try:
                import asyncio
                entry = random.choice(memorized)
                surah, ayah_num = entry["surah_number"], entry["ayah_number"]
                all_surahs = await quran_api.get_surah_list()
                ayahs = await quran_api.get_ayahs(surah)
                target = next((a for a in ayahs if a["number"] == ayah_num), None)
                surah_info = await quran_api.get_surah_info(surah)
                if target and surah_info:
                    correct_name = surah_info["englishName"]
                    arabic_snippet = target["text"][:80]
                    wrong_pool = [s["englishName"] for s in all_surahs if s["number"] != surah]
                    wrongs = random.sample(wrong_pool, min(3, len(wrong_pool)))
                    options = [correct_name] + wrongs
                    random.shuffle(options)

                    correct_enc = base64.b64encode(correct_name.encode()).decode()
                    ayah_tag = f":{surah}:{ayah_num}"
                    db.update_settings(user_id, awaiting_input=f"quiz_ans:{correct_enc}{ayah_tag}")
                    db.ensure_gamification(user_id)

                    header = (
                        f"📍 *Kunlik Eslatma + Sinov!*\n\n"
                        f"Ushbu oyat qaysi suradan?\n\n_{arabic_snippet}_"
                        if lang == "uz" else
                        f"📍 *Daily Reminder + Quiz!*\n\n"
                        f"Which Surah is this Ayah from?\n\n_{arabic_snippet}_"
                    )
                    rows_kb = [[InlineKeyboardButton(
                        str(opt).replace(":", "§")[:40],
                        callback_data=f"quiz:ans:{str(opt).replace(':', '§')[:38]}"
                    )] for opt in options]
                    rows_kb.append([InlineKeyboardButton(
                        "📚 O'rganishni boshlash" if lang == "uz" else "📚 Start Learning",
                        callback_data="menu:learn"
                    )])
                    await bot.send_message(chat_id=user_id, text=header,
                                           parse_mode="Markdown",
                                           reply_markup=InlineKeyboardMarkup(rows_kb))
                    sent_quiz = True
            except Exception as e:
                print(f"[Scheduler] Interactive quiz build failed for {user_id}: {e}")

        if not sent_quiz:
            text = (t(user_id, "reminder_streak_lost", name=name) if streak_just_lost
                    else t(user_id, "reminder_active", name=name, goal=goal, streak=streak))
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("📚 Start Learning", callback_data="menu:learn"),
                InlineKeyboardButton("🔥 Flow Mode", callback_data="menu:flow"),
            ]])
            try:
                await bot.send_message(chat_id=user_id, text=text,
                                       parse_mode="Markdown", reply_markup=keyboard)
            except Exception as e:
                print(f"[Scheduler] Reminder failed for {user_id}: {e}")

async def run_motivations(bot):
    """Daily motivation for users who have no goals or haven't memorized anything."""
    users = db.get_inactive_users()
    idx = _day_counter[0] % 5

    for row in users:
        user_id = row["id"]
        lang = row["language"]
        text = MOTIVATIONS_UZ[idx] if lang == "uz" else MOTIVATIONS_EN[idx]
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📚 Start Learning", callback_data="menu:learn"),
                InlineKeyboardButton("🔥 Flow Mode", callback_data="menu:flow"),
            ],
            [InlineKeyboardButton("⚙️ Set My Goal", callback_data="menu:settings")],
        ])
        try:
            await bot.send_message(chat_id=user_id, text=text,
                                   parse_mode="Markdown", reply_markup=keyboard)
        except Exception as e:
            print(f"[Scheduler] Motivation failed for {user_id}: {e}")

    _day_counter[0] += 1

async def run_xatm_reminders(bot):
    """Daily reminder to all users about Xatm feature. Participants get progress info."""
    all_users = db.get_all_users()
    for row in all_users:
        user_id = row["id"]
        lang = row.get("language", "en") if hasattr(row, "get") else dict(row).get("language", "en")

        # Check if user has an active xatm assignment
        participation = db.get_user_xatm_participation(user_id)

        if participation:
            xatm_id = participation["xatm_id"]
            completed_juzs = participation["completed_juzs"]
            remaining = 30 - completed_juzs
            pct_done = int(completed_juzs / 30 * 100)
            pct_left = 100 - pct_done

            if lang == "uz":
                text = (
                    f"📖 *Jamoaviy Xatm Eslatmasi*\n\n"
                    f"Siz #{xatm_id} Xatmga qo'shilgansiz.\n\n"
                    f"📊 *Holat:*\n"
                    f"• Tugallangan poralar: {completed_juzs}/30\n"
                    f"• Qolgan poralar: {remaining}\n"
                    f"• Yakunlanishiga: {pct_left}% qoldi\n\n"
                    f"✨ *Ajr va savob va'dalari:*\n"
                    f"_«Qur'on qiyomat kuni o'z sohiblari uchun shafkovchi bo'lib keladi.»_\n"
                    f"_«Qur'on o'qigan har bir harfga 10 savob yoziladi.»_ (Tirmiziy)\n\n"
                    f"Xatmni davom ettiring!"
                )
            else:
                text = (
                    f"📖 *Group Khatm Reminder*\n\n"
                    f"You are part of Khatm #{xatm_id}.\n\n"
                    f"📊 *Progress:*\n"
                    f"• Completed Juz: {completed_juzs}/30\n"
                    f"• Remaining: {remaining} Juz\n"
                    f"• {pct_left}% left until completion\n\n"
                    f"✨ *Rewards & Blessings:*\n"
                    f"_\"The Quran will come as an intercessor for its companions on the Day of Judgment.\"_\n"
                    f"_\"Every letter recited earns 10 rewards.\"_ (Tirmidhi)\n\n"
                    f"Keep going — you're making history!"
                )
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "📖 Xatmga o'tish" if lang == "uz" else "📖 Go to Khatm",
                    callback_data="xatm:dashboard"
                )
            ]])
        else:
            if lang == "uz":
                text = (
                    "👥 *Jamoaviy Xatm*\n\n"
                    "Jamoa bilan birgalikda to'liq Qur'on xatmini amalga oshiring!\n\n"
                    "✨ *Nima bu?*\n"
                    "30 nafar ishtirokchi — har biri 1 pora o'qiydi.\n"
                    "Birga 30 pora — to'liq bir xatm!\n\n"
                    "_«Qur'on qiroati — eng yuksak ibodat.»_\n\n"
                    "Bugun Xatmga qo'shiling!"
                )
            else:
                text = (
                    "👥 *Group Khatm*\n\n"
                    "Complete a full Quran recitation together as a group!\n\n"
                    "✨ *How it works:*\n"
                    "30 participants — each reads 1 Juz.\n"
                    "Together: a complete Khatm!\n\n"
                    "_\"Reciting the Quran is the highest act of worship.\"_\n\n"
                    "Join a Khatm today!"
                )
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "👥 Xatmga qo'shilish" if lang == "uz" else "👥 Join a Khatm",
                    callback_data="xatm:dashboard"
                )
            ]])

        try:
            await bot.send_message(chat_id=user_id, text=text,
                                   parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            print(f"[Scheduler] Xatm reminder failed for {user_id}: {e}")


async def run_daily_admin_report(bot):
    """Send daily stats summary to admin at 23:50."""
    today = date.today().isoformat()
    total_users = db.get_total_users()
    active_today = db.get_active_today()
    total_memorized = db.get_total_memorized()
    new_today = db.get_new_users_today()
    premium_count = db.get_premium_count()
    xatm_stats = db.get_xatm_stats()
    top_users = db.get_leaderboard(limit=5)

    top_lines = []
    for i, u in enumerate(top_users, 1):
        top_lines.append(f"  {i}. {u['name']} — {u['total_xp']} XP 🔥{u['current_streak']}")
    top_text = "\n".join(top_lines) if top_lines else "  (hali yo'q)"

    report = (
        f"📊 *Kunlik Hisobot — {today}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 *Foydalanuvchilar:*\n"
        f"  • Jami: {total_users}\n"
        f"  • Bugun faol: {active_today}\n"
        f"  • Bugun yangi: {new_today}\n"
        f"  • Premium: {premium_count}\n\n"
        f"📖 *Yod olish:*\n"
        f"  • Jami yod olingan oyatlar: {total_memorized}\n\n"
        f"👥 *Jamoaviy Xatm:*\n"
        f"  • Yakunlangan Xatmlar: {xatm_stats.get('total_xatms', 0)}\n"
        f"  • Jami ishtirokchilar: {xatm_stats.get('total_participants', 0)}\n\n"
        f"🏆 *Top 5 Foydalanuvchi:*\n{top_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"_Hisobot avtomatik ravishda har kuni 23:50 da yuboriladi._"
    )

    try:
        await bot.send_message(chat_id=ADMIN_ID, text=report, parse_mode="Markdown")
    except Exception as e:
        print(f"[Scheduler] Admin daily report failed: {e}")


async def run_admin_decline_check(bot):
    """Check if admin sent a decline reason (stored in awaiting_input) and process it."""
    # This is handled via the settings text handler — no extra job needed.
    pass
