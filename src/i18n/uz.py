"""Uzbek string table — complete translation for all features."""

STRINGS = {
    # ── Onboarding
    "choose_language": "🌍 *Hifz Botga Xush Kelibsiz!*\nIltimos, tilingizni tanlang:",
    "lang_en": "🇬🇧 English",
    "lang_uz": "🇺🇿 O'zbek",
    "welcome": (
        "✨ *Assalomu Alaykum, {name}!*\n\n"
        "Men sizning shaxsiy Hifz yordamchingizman. 🕌\n\n"
        "Quyidagilardan birini tanlang:"
    ),
    "help": (
        "📖 *Hifz Bot — Asosiy Menyu*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📚 O'rganish — Hifz safarini boshlash/davom ettirish\n"
        "🔥 Oqim — To'xtovsiz chuqur yod olish rejimi\n"
        "🧠 Test — Qur'on bilimingizni sinash\n"
        "👤 Profil — Shaxsiy dashboard\n"
        "🏆 Reyting — Liga jadvali\n"
        "⚙️ Sozlamalar — Eslatmalar va maqsadlar"
    ),
    "btn_main_menu": "🏠 Asosiy Menyu",
    "btn_learn": "📚 O'rganish",
    "btn_flow": "🔥 Oqim Rejimi",
    "btn_quiz": "🧠 Test",
    "btn_profile_short": "👤 Profil",
    "btn_leaderboard_short": "🏆 Reyting",
    "btn_settings_short": "⚙️ Sozlamalar",

    # ── Profile
    "profile_header": "👤 *Sizning Hifz Dashboardingiz*\n━━━━━━━━━━━━━━━━━━━━",
    "profile_surah": "📖 *Joriy Sura:* {surah_name} (#{surah_num})",
    "profile_progress_bar": "Jarayon: [{bar}] {pct}%  ({done}/{total} Oyat)",
    "profile_xp": "⭐ *Jami XP:* {xp}",
    "profile_streak": "🔥 *Seriya:* {streak} kun",
    "profile_league": "🏅 *Liga:* {league}",
    "profile_goal": "🎯 *Kunlik Maqsad:* {goal} Oyat/kun",
    "profile_projection": "📅 Shu sur'atda, suraning oxirigacha ~{days} kun!",
    "profile_projection_done": "🎉 *Sura tugadi!* Yangi sura tanlang.",
    "profile_badges": "🏆 *Nishonlar:* {badges}",
    "profile_no_badges": "🏆 *Nishonlar:* Hali yo'q — yod olishni boshlang!",
    "profile_full_stats": (
        "📊 *To'liq Statistika*\n━━━━━━━━━━━━━━━━━━━━\n"
        "⭐ Jami XP: {xp}\n"
        "🔥 Joriy seriya: {streak} kun\n"
        "💪 Eng uzun seriya: {longest} kun\n"
        "🏅 Liga: {league}\n"
        "📖 Yod olingan oyatlar: {total_memorized}\n"
        "🕌 Tegilgan suralar: {surahs_touched}"
    ),
    "btn_settings": "⚙️ Sozlamalar",
    "btn_full_stats": "📊 To'liq Statistika",
    "btn_study_plan": "📚 O'qish Rejasi",
    "btn_back_profile": "🔙 Orqaga",

    # ── Navigator
    "nav_welcome": "📚 *Qur'on Navigatori*\n\nQayerdan boshlashni xohlaysiz?",
    "nav_btn_baqara": "📜 Al-Baqara",
    "nav_btn_juz_amma": "🕌 Juz Amma (30-juz)",
    "nav_btn_custom": "🔍 O'z tanlovi",
    "nav_juz_amma_header": "🕌 *Juz Amma — Sura tanlang:*",
    "nav_custom_juz": "📂 *Juz tanlang (1–30):*",
    "nav_surah_selected": "📖 *{surah_name}* — {ayah_count} Oyat\n\nQayerdan boshlash?",
    "nav_btn_start_ayah1": "▶️ 1-oyatdan",
    "nav_btn_choose_ayah": "🔢 Oyat tanlash",
    "nav_choose_ayah_prompt": "📖 *{surah_name}* — {ayah_count} Oyat.\nBoshlash uchun oyat raqamini yozing (1–{ayah_count}):",
    "nav_btn_back": "🔙 Orqaga",
    "nav_choose_plan": "✅ *{surah_name}, {ayah_num}-oyat*\n\nO'qish rejasini tanlang:",
    "plan_gentle": "🌿 Yengil — 1/kun",
    "plan_standard": "📖 Standart — 3/kun",
    "plan_intense": "🔥 Intensiv — 1 sahifa/hafta",
    "plan_custom": "✏️ O'z tanlovi",
    "plan_custom_prompt": "Kuniga nechta oyat yod olishni xohlaysiz? (1–20):",
    "plan_set": "🎯 *Reja belgilandi!*\n📖 {surah_name}, {ayah_num}-oyat\n🗓️ {plan_label}",
    "plan_invalid_number": "⚠️ Iltimos 1 dan 20 gacha raqam kiriting.",

    # ── Settings
    "settings_header": "⚙️ *Sozlamalar*\n━━━━━━━━━━━━━━━━━━━━",
    "settings_current": "🎯 Kunlik maqsad: *{goal}* Oyat/kun",
    "btn_set_reminder": "⏰ Eslatmalarim",
    "btn_set_goal": "🎯 Kunlik maqsad",
    "btn_set_language": "🌐 Til",
    "settings_reminder_list_header": "⏰ *Eslatmalar* ({count}/10)\n━━━━━━━━━━\n{list}\n\n_O'chirish uchun vaqtga bosing._",
    "settings_reminder_list_empty": "⏰ *Eslatmalar* (0/10)\n━━━━━━━━━━\nHali eslatma yo'q.",
    "btn_add_reminder": "➕ Eslatma qo'shish",
    "btn_back_settings": "🔙 Sozlamalarga qaytish",
    "settings_reminder_prompt": "⏰ *HH:MM* formatida vaqt yozing (24 soat), masalan `06:30`:",
    "settings_reminder_saved": "✅ Eslatma qo'shildi: *{time}*",
    "settings_reminder_removed": "🗑 Eslatma *{time}* o'chirildi.",
    "settings_reminder_invalid": "⚠️ Noto'g'ri format. HH:MM ishlatilsin, masalan `06:30`",
    "settings_reminder_max": "⚠️ Sizda allaqachon 10 ta eslatma bor (maksimum).",
    "settings_goal_prompt": "🎯 Kuniga nechta Oyat? (1–20):",
    "settings_goal_saved": "✅ Kunlik maqsad: *{goal}* Oyat/kun",
    "settings_goal_invalid": "⚠️ Iltimos 1 dan 20 gacha raqam kiriting.",

    # ── Leaderboard
    "leaderboard_header": "🏆 *Hifz Reytingi*\n━━━━━━━━━━━━━━━━━━━━\n",
    "league_diamond": "💎 OLMOS LIGASI 💎",
    "league_gold": "🥇 OLTIN LIGASI 🥇",
    "league_silver": "🥈 KUMUSH LIGASI 🥈",
    "league_bronze": "🥉 BRONZA LIGASI 🥉",
    "leaderboard_row": "{rank}. {medal} {name} — {xp} XP 🔥{streak}",
    "leaderboard_you": "{rank}. {medal} {name} — {xp} XP 🔥{streak}  ← Siz",
    "leaderboard_empty": "Hali foydalanuvchilar yo'q. Birinchi bo'ling! 🏅",
    "btn_refresh": "🔄 Yangilash",

    # ── Reminders
    "reminder_active": (
        "🌅 *Hifz vaqti, {name}!*\n\n"
        "📖 Bugun *{goal}* oyat bor.\n"
        "🔥 Seriya: {streak} kun — davom eting!"
    ),
    "reminder_streak_lost": (
        "💔 *{name}, seriyangiz nolga tushdi.*\n\n"
        "_«Yurak — ko'zgu kabi: u faqat har kuni sayqallanganida haqiqiy nurni ko'rsatadi. Qayting, yana boshlang.»_\n\n"
        "🌱 Bugun yangi boshlanish."
    ),

    # ── Gamification
    "xp_earned": "⭐ +{xp} XP! Jami: {total}",
    "league_up": "🎉 *{league} ligasi ochildi!* 🏅",
    "badge_unlocked": "🏆 *Nishon ochildi:* {badge}",
    "badge_first_step": "🌟 Birinchi Qadam",
    "badge_week_warrior": "🔥 Hafta Jangchisi",
    "badge_page_turner": "📖 Sahifa Aylovchi",
    "badge_juz_warrior": "🏅 Juz Jangchisi",
    "badge_quiz_master": "🧠 Test Ustasi (97%+)",

    # ── Quiz
    "quiz_menu": "🧠 *Test — Qur'on Bilimingizni Sinang*\n\nO'yinni tanlang:",
    "quiz_btn_surah_order": "📋 Sura Tartibi",
    "quiz_btn_surah_name": "📖 Sura Nomi",
    "quiz_btn_ayah_order": "🔢 Oyat Tartibi",
    "quiz_btn_pick_surah": "🕌 Sura Tanlash (Oyat Uchun)",
    "quiz_btn_back": "🔙 Orqaga",
    "quiz_question": (
        "🧠 *Savol {num}/{total}*\n"
        "━━━━━━━━━━━━━\n"
        "{question}\n\n"
        "Natija: {correct}/{num_done} to'g'ri  ⭐ {xp} XP"
    ),
    "quiz_correct": "✅ *To'g'ri!* +10 XP\n\n",
    "quiz_wrong": "❌ *Noto'g'ri!* Javob: *{answer}*\n\n",
    "quiz_finished": (
        "🏁 *Test Tugadi!*\n"
        "━━━━━━━━━━━━━━\n"
        "Natija: {correct}/{total} ({pct}%)\n"
        "⭐ Jami XP: {xp}\n\n"
        "{result_msg}"
    ),
    "quiz_passed": "🏆 *Ajoyib! 97%+ — Test Ustasi nishoni ochildi!*",
    "quiz_good": "👍 Zo'r! Mashq qilaverging!",
    "quiz_try_again": "💪 Mashq qiling! Erishib ketasiz.",
    "quiz_q_surah_order": "Qur'onda *{surah_name}* surasi qaysi tartibda (raqamda)?",
    "quiz_q_surah_name": "*{number}-sura* nomi nima?",
    "quiz_q_ayah_order": "*{surah_name}* surasida *{position}-o'rinida* qaysi oyat keladi?",

    # ── Flow Learning
    "flow_menu": (
        "🔥 *Oqim O'rganish Rejimi*\n\n"
        "Chuqur Hifz — oyat ba oyat, qadam ba qadam.\n\n"
        "Boshlash joyini tanlang:"
    ),
    "flow_btn_continue": "▶️ To'xtatgan joyimdan davom etish",
    "flow_btn_new": "🆕 Yangi boshlash",
    "flow_btn_back": "🔙 Orqaga",
    "flow_read3": (
        "📖 *{surah_name} — {ayah_num}-Oyat*\n"
        "━━━━━━━━━━━━━━━━━\n"
        "{arabic}\n\n"
        "_Ushbu oyatni *3 marta* ovoz chiqarib o'qing._"
    ),
    "flow_btn_read3": "✅ 3 marta o'qidim",
    "flow_read7_trans": (
        "📖 *{surah_name} — {ayah_num}-Oyat*\n"
        "━━━━━━━━━━━━━━━━━\n"
        "{arabic}\n\n"
        "💬 *Tarjima:*\n_{translation}_\n\n"
        "_Endi ma'noni tushunib *7 marta* o'qing._"
    ),
    "flow_btn_read7": "✅ 7 marta o'qidim",
    "flow_memorize13": (
        "🧠 *{surah_name} — {ayah_num}-Oyat*\n"
        "━━━━━━━━━━━━━━━━━\n"
        "{arabic}\n\n"
        "_Ko'zingizni yuming va yoddan o'qing. Yuragingizga o'rnashguncha *13 marta* takrorlang._"
    ),
    "flow_btn_memorize13": "✅ 13 marta yod oldim",
    "flow_audio_check": (
        "🎙 *{ayah_num}-Oyat — Tekshiruv*\n\n"
        "Endi *{surah_name} {ayah_num}-oyat*ni yoddan o'qing.\n"
        "*Ovoz xabar* yuboring. 🎤"
    ),
    "flow_audio_received": "✅ *JazakAllah! Ovoz qabul qilindi.* +25 XP\n\n",
    "flow_combine5": (
        "🔗 *Birlashtiring va Mustahkamlang!*\n"
        "━━━━━━━━━━━━━━━━━\n"
        "*{ayah_prev}-Oyat:*\n{arabic_prev}\n\n"
        "*{ayah_curr}-Oyat:*\n{arabic_curr}\n\n"
        "_Ikkalasini ketma-ket *5 marta* o'qing._"
    ),
    "flow_btn_combine5": "✅ 5 marta birlashtirdim",
    "flow_xp_inline": "⭐ +{xp} XP  |  Jami: {total} XP",
    "flow_next_ayah": "➡️ *Zo'r! {next_num}-Oyatga o'tilmoqda...*",
    "flow_surah_done": (
        "🎉 *Mashallah! Siz {surah_name} surasini yakunladingiz!*\n\n"
        "To'liq sura yod olindi — farishtalar sizning harakatingizni ko'rmoqda.\n"
        "_«Kim Qur'onni yod olsa, Alloh unga aslo yo'qolmaydigan narsa beradi.»_"
    ),
    "flow_paused": "⏸ Oqim sessiyasi to'xtatildi. /flow bilan davom eting.",

    # ── Generic
    "error_unknown": "⚠️ Xato yuz berdi. Iltimos, qayta urinib ko'ring.",
    "please_start": "⚠️ Ro'yxatdan o'tish uchun avval /start yuboring.",

    # ── Jamoaviy Xatm
    "btn_group_xatm": "👥 Jamoaviy Xatm",
    "xatm_dashboard_header": "👥 *Jamoaviy Xatm*\n━━━━━━━━━━━━━━━━━━━━\n\nJamoa bilan birgalikda to'liq Qur'on xatmini yakunlang.\n\n📊 *Statistika:*\n• Yakunlangan Xatmlar: {total_xatms}\n• Jami ishtirokchilar: {total_participants}\n• O'rtacha vaqt: {avg_time}\n• Eng tez: {fastest}\n• Eng uzoq: {longest}",
    "xatm_btn_join_active": "🤝 Faol Xatmga Qo'shilish",
    "xatm_btn_create_custom": "➕ Yangi Xatm Yaratish",
    "xatm_view_header": "👥 *Jamoaviy Xatm #{xatm_id}*\n━━━━━━━━━━━━━━━━━━━━\n\nIltimos, o'qish uchun pora (juz) tanlang. Barcha 30 pora olingach, «Xatm Marafoni» boshlanadi.\n\nHolat: {status_text}",
    "xatm_status_recruiting": "🟡 Ishtirokchilar yig'ilmoqda...",
    "xatm_status_active": "🟢 Marafon boshlandi! O'qishni davom eting.",
    "xatm_status_completed": "✅ Xatm yakunlandi! Alloh qabul qilsin.",
    "xatm_already_taken": "⚠️ Bu pora allaqachon olingan.",
    "xatm_marathon_started_notify": "🎉 *Xatm Marafoni Boshlandi!*\n\nSiz qatnashayotgan #{xatm_id} Jamoaviy Xatmda barcha 30 pora o'z egalarini topdi. Endi o'zingizga biriktirilgan porani o'qib, tugatganingizni belgilang. Alloh oson qilsin!",
    "xatm_marathon_completed_notify": "✨ *Masha'Allah! Xatm Yakunlandi!*\n\nSiz qatnashgan #{xatm_id} Jamoaviy Xatm to'liq yakuniga yetdi. Barcha 30 pora o'qildi. Alloh hammamizning ajrimizni ziyoda qilsin!",
    "xatm_btn_mark_completed": "✅ {juz}-porani o'qidim",
    "xatm_share_btn": "🔗 Do'stlarga Ulashish",
    "xatm_share_text": "Men Hifz Bot orqali Jamoaviy Qur'on xatmida qatnashyapman. Siz ham qo'shiling va bir pora o'qing!",
}

BADGE_DISPLAY = {
    "first_step": "🌟 Birinchi Qadam",
    "week_warrior": "🔥 Hafta Jangchisi",
    "page_turner": "📖 Sahifa Aylovchi",
    "juz_warrior": "🏅 Juz Jangchisi",
    "quiz_master": "🧠 Test Ustasi",
}

LEAGUE_DISPLAY = {
    "bronze": "🥉 Bronza",
    "silver": "🥈 Kumush",
    "gold": "🥇 Oltin",
    "diamond": "💎 Olmos",
}

PLAN_LABELS = {
    "gentle": "🌿 Yengil — 1 Oyat/kun",
    "standard": "📖 Standart — 3 Oyat/kun",
    "intense": "🔥 Intensiv — 1 Sahifa/hafta (~20 Oyat)",
    "custom": "✏️ O'z rejasi",
}
