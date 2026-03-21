"""English string table (full — all features)."""

STRINGS = {
    # ── Onboarding ────────────────────────────────────────────────────
    "choose_language": "🌍 *Welcome to Hifz Bot!*\nPlease choose your language:",
    "lang_en": "🇬🇧 English",
    "lang_uz": "🇺🇿 O'zbek",
    "welcome": (
        "✨ *Assalamu Alaikum, {name}!*\n\n"
        "I'm your personal Hifz companion. 🕌\n\n"
        "Choose what to do:"
    ),
    "help": (
        "📖 *Hifz Bot — Main Menu*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📚 Learn — Start/continue Hifz journey\n"
        "🔥 Flow — Non-stop deep learning mode\n"
        "🧠 Quiz — Test your Quran knowledge\n"
        "👤 Profile — Your dashboard\n"
        "🏆 Leaderboard — League standings\n"
        "⚙️ Settings — Reminders & goals"
    ),
    "btn_main_menu": "🏠 Main Menu",
    "btn_learn": "📚 Start Learning",
    "btn_flow": "🔥 Flow Mode",
    "btn_quiz": "🧠 Quiz",
    "btn_profile_short": "👤 Profile",
    "btn_leaderboard_short": "🏆 Leaderboard",
    "btn_settings_short": "⚙️ Settings",

    # ── Profile ───────────────────────────────────────────────────────
    "profile_header": "👤 *Your Hifz Dashboard*\n━━━━━━━━━━━━━━━━━━━━",
    "profile_surah": "📖 *Current Surah:* {surah_name} (#{surah_num})",
    "profile_progress_bar": "Progress: [{bar}] {pct}%  ({done}/{total} Ayahs)",
    "profile_xp": "⭐ *Total XP:* {xp}",
    "profile_streak": "🔥 *Streak:* {streak} day(s)",
    "profile_league": "🏅 *League:* {league}",
    "profile_goal": "🎯 *Daily Goal:* {goal} Ayah(s)/day",
    "profile_projection": "📅 At this pace, finish Surah in ~{days} day(s)!",
    "profile_projection_done": "🎉 *Surah complete!* Choose a new one.",
    "profile_badges": "🏆 *Badges:* {badges}",
    "profile_no_badges": "🏆 *Badges:* None yet — start memorizing!",
    "profile_full_stats": (
        "📊 *Full Stats*\n━━━━━━━━━━━━━━━━━━━━\n"
        "⭐ Total XP: {xp}\n"
        "🔥 Current Streak: {streak} days\n"
        "💪 Longest Streak: {longest} days\n"
        "🏅 League: {league}\n"
        "📖 Ayahs Memorized: {total_memorized}\n"
        "🕌 Surahs Touched: {surahs_touched}"
    ),
    "btn_settings": "⚙️ Settings",
    "btn_full_stats": "📊 Full Stats",
    "btn_study_plan": "📚 Study Plan",
    "btn_back_profile": "🔙 Back",

    # ── Navigator ────────────────────────────────────────────────────
    "nav_welcome": "📚 *Quran Navigator*\n\nWhere would you like to begin?",
    "nav_btn_baqara": "📜 Al-Baqara",
    "nav_btn_juz_amma": "🕌 Juz Amma (Juz 30)",
    "nav_btn_custom": "🔍 Custom",
    "nav_juz_amma_header": "🕌 *Juz Amma — Select Surah:*",
    "nav_custom_juz": "📂 *Select Juz (1–30):*",
    "nav_surah_selected": "📖 *{surah_name}* — {ayah_count} Ayahs\n\nWhere to start?",
    "nav_btn_start_ayah1": "▶️ From Ayah 1",
    "nav_btn_choose_ayah": "🔢 Choose Ayah",
    "nav_choose_ayah_prompt": "📖 *{surah_name}* — {ayah_count} Ayahs.\nType the Ayah number to start from (1–{ayah_count}):",
    "nav_btn_back": "🔙 Back",
    "nav_choose_plan": "✅ *{surah_name}, Ayah {ayah_num}*\n\nChoose your study plan:",
    "plan_gentle": "🌿 Gentle — 1/day",
    "plan_standard": "📖 Standard — 3/day",
    "plan_intense": "🔥 Intense — 1 pg/wk",
    "plan_custom": "✏️ Custom",
    "plan_custom_prompt": "Type how many Ayahs/day you want to memorize (1–20):",
    "plan_set": "🎯 *Plan set!*\n📖 {surah_name}, Ayah {ayah_num}\n🗓️ {plan_label}",
    "plan_invalid_number": "⚠️ Please enter a number between 1 and 20.",

    # ── Settings ──────────────────────────────────────────────────────
    "settings_header": "⚙️ *Settings*\n━━━━━━━━━━━━━━━━━━━━",
    "settings_current": "🎯 Daily Goal: *{goal}* Ayah(s)/day",
    "btn_set_reminder": "⏰ My Reminders",
    "btn_set_goal": "🎯 Daily Goal",
    "btn_set_language": "🌐 Language",
    "settings_reminder_list_header": "⏰ *Your Reminders* ({count}/10)\n━━━━━━━━━━\n{list}\n\n_Tap a time to remove it._",
    "settings_reminder_list_empty": "⏰ *Your Reminders* (0/10)\n━━━━━━━━━━\nNo reminders set yet.",
    "btn_add_reminder": "➕ Add Reminder",
    "btn_back_settings": "🔙 Back to Settings",
    "settings_reminder_prompt": "⏰ Type reminder time in *HH:MM* (24h), e.g. `06:30`:",
    "settings_reminder_saved": "✅ Reminder added: *{time}*",
    "settings_reminder_removed": "🗑 Reminder *{time}* removed.",
    "settings_reminder_invalid": "⚠️ Invalid format. Use HH:MM, e.g. `06:30`",
    "settings_reminder_max": "⚠️ You already have 10 reminders (maximum).",
    "settings_goal_prompt": "🎯 How many Ayahs/day? (1–20):",
    "settings_goal_saved": "✅ Daily goal: *{goal}* Ayah(s)/day",
    "settings_goal_invalid": "⚠️ Please enter a number between 1 and 20.",

    # ── Leaderboard ───────────────────────────────────────────────────
    "leaderboard_header": "🏆 *Hifz Leaderboard*\n━━━━━━━━━━━━━━━━━━━━\n",
    "league_diamond": "💎 DIAMOND LEAGUE 💎",
    "league_gold": "🥇 GOLD LEAGUE 🥇",
    "league_silver": "🥈 SILVER LEAGUE 🥈",
    "league_bronze": "🥉 BRONZE LEAGUE 🥉",
    "leaderboard_row": "{rank}. {medal} {name} — {xp} XP 🔥{streak}",
    "leaderboard_you": "{rank}. {medal} {name} — {xp} XP 🔥{streak}  ← You",
    "leaderboard_empty": "No users yet. Be the first! 🏅",
    "btn_refresh": "🔄 Refresh",

    # ── Daily Reminder ────────────────────────────────────────────────
    "reminder_active": (
        "🌅 *Time for Hifz, {name}!*\n\n"
        "📖 You have *{goal}* Ayah(s) today.\n"
        "🔥 Streak: {streak} days — keep it alive!"
    ),
    "reminder_streak_lost": (
        "💔 *{name}, your streak reset to 0.*\n\n"
        "_\"The heart is like a mirror — it only shows true light "
        "when polished daily. Return, and begin again.\"_\n\n"
        "🌱 Today is a new beginning."
    ),

    # ── Gamification ──────────────────────────────────────────────────
    "xp_earned": "⭐ +{xp} XP! Total: {total}",
    "league_up": "🎉 *{league} League unlocked!* 🏅",
    "badge_unlocked": "🏆 *Badge Unlocked:* {badge}",
    "badge_first_step": "🌟 First Step",
    "badge_week_warrior": "🔥 Week Warrior",
    "badge_page_turner": "📖 Page Turner",
    "badge_juz_warrior": "🏅 Juz Warrior",
    "badge_quiz_master": "🧠 Quiz Master (97%+)",

    # ── Quiz ──────────────────────────────────────────────────────────
    "quiz_menu": "🧠 *Quiz — Test Your Quran Knowledge*\n\nChoose a game:",
    "quiz_btn_surah_order": "📋 Surah Order",
    "quiz_btn_surah_name": "📖 Surah Name",
    "quiz_btn_ayah_order": "🔢 Ayah Order",
    "quiz_btn_pick_surah": "🕌 Pick Surah for Ayah Quiz",
    "quiz_btn_back": "🔙 Back",
    "quiz_question": (
        "🧠 *Question {num}/{total}*\n"
        "━━━━━━━━━━━━━\n"
        "{question}\n\n"
        "Score: {correct}/{num_done} correct  ⭐ {xp} XP earned"
    ),
    "quiz_correct": "✅ *Correct!* +10 XP\n\n",
    "quiz_wrong": "❌ *Wrong!* The answer was: *{answer}*\n\n",
    "quiz_finished": (
        "🏁 *Quiz Complete!*\n"
        "━━━━━━━━━━━━━━\n"
        "Score: {correct}/{total} ({pct}%)\n"
        "⭐ Total XP earned: {xp}\n\n"
        "{result_msg}"
    ),
    "quiz_passed": "🏆 *Amazing! 97%+ correct — Quiz Master badge unlocked!*",
    "quiz_good": "👍 Great job! Keep practicing!",
    "quiz_try_again": "💪 Keep training! You'll get there.",
    "quiz_q_surah_order": "Which position (number) is *{surah_name}* in the Quran?",
    "quiz_q_surah_name": "What is the name of *Surah #{number}*?",
    "quiz_q_ayah_order": "In *{surah_name}*, which of these comes at position *#{position}*?",

    # ── Flow Learning ─────────────────────────────────────────────────
    "flow_menu": "🔥 *Flow Learning Mode*\n\nDeep Hifz — ayah by ayah, step by step.\n\nChoose starting point:",
    "flow_btn_continue": "▶️ Continue Where I Left Off",
    "flow_btn_new": "🆕 Start Fresh",
    "flow_btn_back": "🔙 Back",
    "flow_read3": (
        "📖 *{surah_name} — Ayah {ayah_num}*\n"
        "━━━━━━━━━━━━━━━━━\n"
        "{arabic}\n\n"
        "_Read this ayah *3 times* aloud, focusing on every word._"
    ),
    "flow_btn_read3": "✅ Read 3 times",
    "flow_read7_trans": (
        "📖 *{surah_name} — Ayah {ayah_num}*\n"
        "━━━━━━━━━━━━━━━━━\n"
        "{arabic}\n\n"
        "💬 *Translation:*\n_{translation}_\n\n"
        "_Now read it *7 times* while understanding the meaning._"
    ),
    "flow_btn_read7": "✅ Read 7 times",
    "flow_memorize13": (
        "🧠 *{surah_name} — Ayah {ayah_num}*\n"
        "━━━━━━━━━━━━━━━━━\n"
        "{arabic}\n\n"
        "_Close your eyes and recite from memory. Read/recite *13 times* until it's locked in your heart._"
    ),
    "flow_btn_memorize13": "✅ Memorized 13 times",
    "flow_audio_check": (
        "🎙 *Ayah {ayah_num} — Memory Check*\n\n"
        "Now recite *{surah_name} Ayah {ayah_num}* from memory.\n"
        "Send a *voice message* and I'll confirm. 🎤"
    ),
    "flow_audio_received": "✅ *JazakAllah! Voice received.* +25 XP\n\n",
    "flow_combine5": (
        "🔗 *Combine & Consolidate!*\n"
        "━━━━━━━━━━━━━━━━━\n"
        "*Ayah {ayah_prev}:*\n{arabic_prev}\n\n"
        "*Ayah {ayah_curr}:*\n{arabic_curr}\n\n"
        "_Read both together *5 times* in order._"
    ),
    "flow_btn_combine5": "✅ Read together 5 times",
    "flow_xp_inline": "⭐ +{xp} XP  |  Total: {total} XP",
    "flow_next_ayah": "➡️ *Great! Moving to Ayah {next_num}...*",
    "flow_surah_done": (
        "🎉 *Masha'Allah! You've completed {surah_name}!*\n\n"
        "A full Surah memorized — the angels witness your effort.\n"
        "_\"Whoever memorizes the Quran, Allah will give him in return something that will not be lost.\"_"
    ),
    "flow_paused": "⏸ Flow session paused. Resume anytime with /flow.",

    # ── Generic ───────────────────────────────────────────────────────
    "error_unknown": "⚠️ Something went wrong. Please try again.",
    "please_start": "⚠️ Please send /start first to register.",
}

BADGE_DISPLAY = {
    "first_step": "🌟 First Step",
    "week_warrior": "🔥 Week Warrior",
    "page_turner": "📖 Page Turner",
    "juz_warrior": "🏅 Juz Warrior",
    "quiz_master": "🧠 Quiz Master",
}

LEAGUE_DISPLAY = {
    "bronze": "🥉 Bronze",
    "silver": "🥈 Silver",
    "gold": "🥇 Gold",
    "diamond": "💎 Diamond",
}

PLAN_LABELS = {
    "gentle": "🌿 Gentle — 1 Ayah/day",
    "standard": "📖 Standard — 3 Ayahs/day",
    "intense": "🔥 Intense — 1 Page/week (~20 Ayahs)",
    "custom": "✏️ Custom Plan",
}
