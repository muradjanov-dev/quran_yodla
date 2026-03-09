"""
messages.py — All message templates for the bot.
"""

from typing import Optional


def welcome_message(user_name: str) -> str:
    return (
        f"🎉🎊🎆🎇\n\n"
        f"Assalomu alaykum, {user_name}!\n\n"
        f"Tabriklaymiz! Siz Qur'on yodlash yo'lida muhim qadam qo'ydingiz!\n\n"
        f"🌟 Alloh taolo sizga bu yo'lda baraka va sobitqadamlik ato etsin!\n\n"
        f"──────────────────\n"
        f"📌 BOT QANDAY ISHLAYDI:\n\n"
        f"📗 YODLASH — Oyatlarni ilmiy usulda yodlash\n"
        f"   • Juz yoki surani tanlaysiz\n"
        f"   • Avval audio eshitasiz, so'ng 3→7→11 marta takrorlab yodlaysiz\n"
        f"   • Yangi oyat qo'shilganda avvalgisi bilan jamlanadi\n\n"
        f"📊 SAHIFAM — Shaxsiy statistikangiz\n"
        f"   • Yodlagan oyatlaringiz, takrorlar, vaqt\n"
        f"   • Himmat ballari va progress bar\n\n"
        f"🎧 TINGLASH — Mashhur qorilar tilovati\n\n"
        f"🏆 REYTING — Top 50 foydalanuvchi\n\n"
        f"💎 PREMIUM — Kuniga 5 oyat BEPUL | Premium: limitsiz\n"
        f"──────────────────\n\n"
        f"3 kunlik BEPUL Premium faollashtirildi! 🎁"
    )


def onboarding_step_0() -> str:
    return (
        "🕌 Assalomu alaykum! Quron Yodlaymiz botiga xush kelibsiz!\n\n"
        "Bu bot sizga Qur'oni Karimni ilmiy va samarali usulda yodlashga yordam beradi.\n\n"
        "Loyiha millionlab insonlarga foyda keltirishi uchun tinmay yaxshilanib boramiz "
        "in shaa ALLOH, duolaringizdan umidvormiz 🤲\n\n"
        "Boshlash uchun bir necha savolga javob bering 👇"
    )


def onboarding_step_name() -> str:
    return "📝 1/5 — Ismingizni kiriting:"


def onboarding_step_level() -> str:
    return (
        "📖 2/5 — Hozircha Qur'ondan qancha yod olganingizni tanlang:\n\n"
    )


def onboarding_step_surahs() -> str:
    return "📖 Qaysi suralarni yodlaganingizni yozing (vergul bilan ajrating):"


def onboarding_step_location() -> str:
    return "📍 3/5 — Qayerda istiqomat qilasiz?\n(Shahar yoki viloyat nomini yozing)"


def onboarding_step_goal() -> str:
    return "🎯 4/5 — Qur'onni nima maqsadda yodlamoqchisiz?\n(Erkin yozing)"


def onboarding_step_time() -> str:
    return "⏰ 5/5 — Kuniga o'rtacha qancha vaqt ajrata olasiz?"


def referral_bonus_message(new_user_name: str, total_points: int) -> str:
    return (
        f"🎉 Do'stingiz {new_user_name} botga qo'shildi! "
        f"Sizga +15 Himmat ball berildi!\n"
        f"Jami ballaringiz: {total_points:,} Himmat 💫"
    )


# ─── Memorize ─────────────────────────────────────────────────────────────────

def ayah_header(surah_name: str, surah_number: int,
                ayah_number: int, total_ayahs: int) -> str:
    return (
        f"──────────────────\n"
        f"📖 {surah_name.upper()} SURASI | {surah_number}-sura\n"
        f"🔢 {ayah_number}-oyat / {total_ayahs} oyat\n"
        f"──────────────────"
    )


def ayah_text_message(arabic: str, uzbek: str, instruction: str, count: int) -> str:
    return (
        f"{arabic}\n\n"
        f"📝 O'zbekcha: {uzbek}\n\n"
        f"──────────────────\n"
        f"{instruction}\n"
        f"──────────────────"
    )


def rep_instruction(count: int) -> str:
    if count == 3:
        return "🎧 Oyatni 3 marotaba eshitib o'qing"
    elif count == 7:
        return "🔄 Endi 7 marotaba o'qing"
    elif count == 11:
        return "🔄 11 marotaba o'qing — bu oyatni mustahkamlang!"
    return f"🔄 {count} marotaba o'qing"


def accumulation_message(ayahs: list) -> str:
    n = len(ayahs)
    lines = [
        "──────────────────",
        f"🔗 {n} OYATNI BIRGA TAKRORLANG",
        "──────────────────\n"
    ]
    for i, a in enumerate(ayahs, 1):
        lines.append(f"{i}. {a['arabic']}\n")
    lines.append("──────────────────")
    lines.append(f"🔄 Barcha {n} oyatni birga 5 marotaba o'qing")
    lines.append("──────────────────")
    return "\n".join(lines)


def checkpoint_message(count: int) -> str:
    return (
        f"──────────────────\n"
        f"✨ Ajoyib! {count} oyat yodladingiz!\n"
        f"──────────────────"
    )


def limit_reached_message() -> str:
    return (
        "⚠️ Bugungi bepul limitingiz tugadi (5/5 oyat).\n\n"
        "💎 Premium bilan kuniga 1000+ oyat yodlang!"
    )


def surah_complete_message(surah_name: str, himmat: int) -> str:
    return (
        f"🎉 TABRIKLAYMIZ!\n\n"
        f"✅ {surah_name} surasi to'liq yodlandi!\n\n"
        f"💫 +{himmat} Himmat ball qo'shildi!"
    )


def level_up_message(level_name: str) -> str:
    return (
        f"🎊 YANGI DARAJA!\n\n"
        f"Siz {level_name} darajasiga ko'tarildingiz!\n\n"
        f"Alloh taolo baraka bersin! 🌟"
    )


# ─── Profile ──────────────────────────────────────────────────────────────────

def profile_message(data: dict, period: str = "today") -> str:
    period_stats = {
        "today": data["today_stats"],
        "week":  data["week_stats"],
        "month": data["month_stats"],
        "year":  data["year_stats"],
    }.get(period, data["today_stats"])

    period_label = {
        "today": "BUGUNGI NATIJA",
        "week":  "HAFTALIK NATIJA",
        "month": "OYLIK NATIJA",
        "year":  "YILLIK NATIJA",
    }.get(period, "BUGUNGI NATIJA")

    p_verses   = period_stats.get("verses_read", 0)
    p_reps     = period_stats.get("repetitions", 0)
    p_mins     = period_stats.get("minutes", 0)

    rank_str = f"#{data['rank']}" if data["rank"] else "—"

    lines = [
        f"──────────────────────",
        f"📊 SAHIFAM — {data['full_name']}",
        f"──────────────────────",
        f"",
        f"💫 HIMMAT BALLARI: {data['himmat_fmt']} ✨",
        f"🏆 Reyting o'rningiz: {rank_str}",
        f"{data['level_name']}",
        f"",
        f"──────────────────────",
        f"📈 UMUMIY STATISTIKA",
        f"──────────────────────",
        f"📖 Jami oyatlar o'qildi: {data['total_verses']:,}",
        f"🔄 Jami takrorlar: {data['total_reps']:,}",
        f"⏱ Jami vaqt: {data['total_time']}",
        f"🔥 Joriy streak: {data['streak']} kun",
        f"🏅 Eng uzun streak: {data['longest_streak']} kun",
        f"",
        f"──────────────────────",
        f"📅 {period_label}:",
        f"Oyatlar: {p_verses} | Takrorlar: {p_reps} | Vaqt: {p_mins} daqiqa",
        f"",
        f"──────────────────────",
        f"📊 30 JUZ PROGRESSI",
        f"[{data['quran_progress_bar']}] {data['percent_complete']}%",
        f"──────────────────────",
    ]

    if data.get("is_premium"):
        lines.append(f"💎 Premium faol | {data.get('premium_expiry', '')}")

    return "\n".join(lines)


def share_result_message(data: dict, bot_username: str) -> str:
    ref_link = f"https://t.me/{bot_username}?start=ref_{data['referral_code']}"
    return (
        f"🕌 Quron Yodlaymiz botida natijalarim:\n\n"
        f"📖 {data['total_verses']} oyat yodladim\n"
        f"💫 {data['himmat_fmt']} Himmat ball to'pladim\n"
        f"🔥 {data['streak']} kunlik streak\n"
        f"🏆 #{data['rank']}-o'rinda\n\n"
        f"Sen ham boshlash: {ref_link}"
    )


# ─── Leaderboard ──────────────────────────────────────────────────────────────

def leaderboard_message(entries: list, user_id: int, user_rank: int,
                        user_entry: Optional[dict] = None) -> str:
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines  = [
        "🏆 FAOLLAR REYTINGI",
        "──────────────────────",
        "TOP 50 — OYLIK REYTING",
        "──────────────────────",
    ]

    for i, e in enumerate(entries[:50], 1):
        medal   = medals.get(i, "  ")
        name    = e.get("full_name", "Anonim")[:15]
        verses  = e.get("total_verses", 0)
        himmat  = e.get("himmat_points", 0)
        is_me   = e.get("user_id") == user_id

        if i <= 3:
            line = f"{medal} #{i}  {name:<16} {verses} oyat | {himmat:,} 💫"
        elif is_me:
            line = f"➡️ #{i} SIZNING O'RNINGIZ   {verses} oyat | {himmat:,} 💫"
        else:
            line = f"   #{i} {name:<16} {verses} oyat | {himmat:,} 💫"

        if i == 3:
            lines.append("━")
        lines.append(line)

    if user_rank > 50:
        lines.extend([
            "──────────────────────",
            f"(#{user_rank-3} yuguruvchi):",
        ])
        if user_entry:
            lines.append(f"➡️ #{user_rank} SIZNING O'RNINGIZ   {user_entry.get('total_verses',0)} oyat | {user_entry.get('himmat_points',0):,} 💫")

    lines.append("──────────────────────")
    return "\n".join(lines)


# ─── Premium ──────────────────────────────────────────────────────────────────

def premium_menu_message(is_active: bool, expiry: Optional[str]) -> str:
    status = f"💎 Premium faol — {expiry} gacha" if is_active else "⚡ Bepul rejimda"
    return (
        f"💎 PREMIUM\n\n"
        f"{status}\n\n"
        f"──────────────────\n"
        f"🆓 BEPUL:\n"
        f"  • Kuniga 5 oyat\n"
        f"  • Barcha qorilar\n"
        f"  • Asosiy statistika\n"
        f"  • Reyting\n\n"
        f"💎 PREMIUM — 10,000 so'm/oy:\n"
        f"  • Limitsiz oyat ♾️\n"
        f"  • Barcha qorilar\n"
        f"  • To'liq statistika\n"
        f"  • Reyting\n\n"
        f"──────────────────\n"
        f"TO'LOV:\n"
        f"💳 5614 6830 0539 3277\n"
        f"👤 M.Nodirjon\n\n"
        f"To'lov qilgach, chekni yuboring 👇"
    )


def premium_trial_offer() -> str:
    return (
        "🎁 SIZ UCHUN MAXSUS TAKLIF!\n\n"
        "3 kunlik BEPUL Premium sinab ko'ring!\n"
        "Barcha imkoniyatlar ochiq!"
    )


def premium_approved_message(expiry_str: str) -> str:
    return (
        f"🎉 TABRIKLAYMIZ!\n\n"
        f"💎 Premium muvaffaqiyatli faollashtirildi!\n"
        f"📅 Tugash sanasi: {expiry_str}\n"
        f"♾️ Kunlik limit: Limitsiz oyat\n\n"
        f"Davom etaylik! 💪"
    )


def premium_rejected_message(reason: str) -> str:
    return (
        f"❌ Premium so'rovingiz rad etildi.\n\n"
        f"Sabab: {reason}\n\n"
        f"Savollaringiz bo'lsa admin bilan bog'laning."
    )


# ─── Admin ────────────────────────────────────────────────────────────────────

def admin_menu_message(stats: dict) -> str:
    return (
        f"🔐 ADMIN PANEL\n\n"
        f"──────────────────────\n"
        f"📊 UMUMIY STATISTIKA\n"
        f"──────────────────────\n"
        f"👥 Jami foydalanuvchilar: {stats['total_users']:,}\n"
        f"💎 Premium foydalanuvchilar: {stats['premium_users']}\n"
        f"📈 Bugun qo'shilganlar: {stats['new_today']}\n"
        f"🔥 Faol (7 kun): {stats['active_7d']}\n"
        f"──────────────────────"
    )


def admin_user_info_message(user: dict) -> str:
    stats      = user.get("stats", {})
    premium    = user.get("premium", {})
    prem_label = "Ha (faol)" if premium.get("is_active") else "Yoq"
    return (
        f"FOYDALANUVCHI MA'LUMOTLARI:\n"
        f"──────────────────────\n"
        f"Ism: {user.get('full_name', '—')}\n"
        f"Username: {user.get('username', '—')}\n"
        f"ID: {user.get('telegram_id', '—')}\n"
        f"Premium: {prem_label}\n"
        f"Oyatlar: {stats.get('total_verses_read', 0)}\n"
        f"Himmat: {stats.get('himmat_points', 0):,}\n"
        f"──────────────────────"
    )


def admin_premium_request_message(user_info: dict) -> str:
    import datetime
    now = datetime.datetime.now().strftime("%d %B %Y, %H:%M")
    return (
        f"💳 YANGI PREMIUM SO'ROV\n\n"
        f"👤 Foydalanuvchi: {user_info.get('full_name', '—')}\n"
        f"📱 Username: {user_info.get('username', '—')}\n"
        f"🆔 ID: {user_info.get('telegram_id', '—')}\n"
        f"📅 Sana: {now}\n\n"
        f"[Chek rasmi quyida]"
    )


# ─── Referral ─────────────────────────────────────────────────────────────────

def referral_message(user: dict, bot_username: str) -> str:
    ref_code    = user.get("referral_code", "")
    ref_link    = f"https://t.me/{bot_username}?start=ref_{ref_code}"
    ref_count   = user.get("referral_count", 0)
    total_bonus = ref_count * 15
    return (
        f"👥 DO'ST TAKLIF QILISH\n\n"
        f"──────────────────────\n"
        f"🎁 MUKOFOT TIZIMI\n"
        f"──────────────────────\n"
        f"Har bir taklif qilgan do'stingiz\n"
        f"uchun ikkalangizga +15 Himmat ball!\n\n"
        f"──────────────────────\n"
        f"🔗 SIZNING TAKLIF HAVOLANGIZ:\n"
        f"──────────────────────\n"
        f"{ref_link}\n\n"
        f"──────────────────────\n"
        f"📊 STATISTIKA:\n"
        f"Taklif qilganlar: {ref_count} kishi\n"
        f"Jami ball: +{total_bonus} Himmat 💫\n"
        f"──────────────────────"
    )


# ─── Listen ───────────────────────────────────────────────────────────────────

def listen_menu_message() -> str:
    return (
        "🎧 TINGLASH\n\n"
        "Mashhur qorilardan birini tanlang:"
    )


def listen_surah_prompt(reciter_name: str) -> str:
    return (
        f"🎵 {reciter_name}\n\n"
        f"Qaysi surani eshitmoqchisiz?\n"
        f"(Sura raqami yoki nomini yozing, masalan: 1 yoki Al-Fatiha)\n\n"
        f"Yoki Juz bo'yicha tanlang:"
    )


def listen_audio_message(surah_name: str, reciter_name: str, audio_url: str) -> str:
    return (
        f"🎵 {surah_name} — {reciter_name}\n\n"
        f"[▶️ Tinglash]({audio_url})"
    )
