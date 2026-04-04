"""
notifications.py - Daily notification sender (called by APScheduler).
Includes: rich Quran/Hadith quotes, xatm daily reminder, pinned message,
premium badge, 2x premium reminder, motivational Uzbek quotes.
"""

import logging
import random
import asyncio
from pathlib import Path
from datetime import datetime
import pytz

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from services.firebase_service import (
    get_all_notification_enabled_users, get_user,
    get_daily_stats, get_period_stats, log_notification,
    get_user_percentile
)
from utils.keyboards import snooze_keyboard, open_memorize_keyboard

TOTAL_AYAHS = 6236
AVG_LETTERS_PER_AYAH = 40
HASANA_PER_LETTER = 10

logger = logging.getLogger(__name__)
TZ = pytz.timezone("Asia/Tashkent")


def _calc_hafiz_projection(daily_ayahs: float) -> str:
    if daily_ayahs <= 0:
        return ""
    days_needed = TOTAL_AYAHS / daily_ayahs
    months = days_needed / 30
    if months < 1:
        return "1 oydan kam"
    return f"{int(months)} oy"


def _calc_daily_ajr(daily_ayahs: int) -> str:
    if daily_ayahs <= 0:
        return "0"
    total = daily_ayahs * AVG_LETTERS_PER_AYAH * HASANA_PER_LETTER
    if total >= 1_000_000:
        return f"{total / 1_000_000:.1f} million"
    if total >= 1000:
        return f"{total:,}"
    return str(total)


# ─── Uzbek motivational quotes ────────────────────────────────────────────────

UZBEK_MOTIVATIONAL_QUOTES = [
    "Har bir oyat — qalbga nur, hayotga baraka. Davom eting!",
    "Buyuk ishlar kichik qadamlardan boshlanadi. Bugun 1 oyat ham galaba!",
    "Eng muborak savdo — vaqtingizni Alloh yolida sarflash. Yodlashni davom eting!",
    "Streak — faqat raqam emas, u sizning sobitqadamligingizdir!",
    "Ilm daraxti sekin osadi, lekin mevalari aziz boladi. Sabr bilan davom eting!",
    "Yodlash qiyin tuyulsa — bu sizning osayotganingizning belgisi!",
    "Quron yodlagan tildan farishtalar yiqilmaydi — bu yolda davom eting!",
    "Dunyo tirikligida oqiydigan oyatlaringiz oxiratda siz uchun yoruglik boladi.",
    "Ruhingizni ozuqlantirishga hech qachon vaqt kech emas. Hozir boshlang!",
    "Quron — ruhing qoriqchisi, qalbing darmoni. Uni yaqin tuting!",
    "Dunyo fanodir, ammo qilgan yaxshiliqlaringiz abadiydir. Yodlashni davom eting!",
    "Har kun bir oyat — bir yilda 365 oyat. Hofizlik yoli shu bilan boshlanadi!",
    "Bazida hayot shoshqaloq boladi. Lekin 5 daqiqa — Alloh uchun topsa boladi.",
    "Birga yodlayotgan jamoa — bir-biriga gayrat beruvchi quvvat!",
    "Quron muhabbati — yurakdan chiqib, butun hayotni ozgartiradi.",
    "Oz narsani muntazam qilish, kop narsani bir marta qilishdan afzal.",
    "Nafsingizga ruhingizning ozugini bering — Quron tilovat qiling!",
    "Har bir sabah yangi bir imkoniyat — bugun bitta yangi oyat yodlang!",
    "Qiyomat kuni amal daftaringizda Quron sahifasi tursin.",
    "Inson eng qiyin palla Allohga eng yaqin boladi — yodlashda ham shunday!",
]


# ─── Rich Islamic quotes pool ─────────────────────────────────────────────────

QURAN_REWARDS_QUOTES = [
    {
        "text": "\"Quron yodda saqlaydigan kishi aziz va motabar farishtalarga hamroh boladi\" "
                "— Buxoriy va Muslim",
        "type": "hadith"
    },
    {
        "text": "\"Ichlaringizning eng yaxshisi Quronni organuvchi va orgatuvchisidir\" "
                "— Buxoriy",
        "type": "hadith"
    },
    {
        "text": "\"Alloh taolo bu kitob bilan kop qavmlarni koтarib, kop qavmlarni pastlatadi\" "
                "— Muslim",
        "type": "hadith"
    },
    {
        "text": "\"Har kim Allohning Kitobidan bitta harf oqisa, unga bitta hasana yoziladi, "
                "va bitta hasana on hasanaga teng boladi\" — Termiziy",
        "type": "hadith"
    },
    {
        "text": "\"Hoffizul Quron — Jennat ahlining sarvariga aylanadi. "
                "U ota-onasini ham jannatga kiritadi\" — Ibn Mojih",
        "type": "hadith"
    },
    {
        "text": "\"Quron bilan mashgul bolish Allohga tasbih va hamd aytishdan ham afzal\" "
                "— Salaf al-Solih sozi",
        "type": "quote"
    },
    {
        "text": "\"Kim Quron oqishni boshlasa, u Alloh bilan muloqot qilayotgan boladi.\" "
                "— Ibn al-Qayyim",
        "type": "quote"
    },
    {
        "text": "Biz Quronni eslatma uchun oson qildik, unda teran oylaydiganlar bormi? "
                "— Qamar surasi, 17-oyat",
        "type": "ayah"
    },
    {
        "text": "Albatta, bu Quron eng togri yolga boshlab boradi "
                "— Isro surasi, 9-oyat",
        "type": "ayah"
    },
    {
        "text": "\"Qiyomat kuni Quron oquvchilarga: 'Oqi va kotar, dunyo hayotida "
                "qanday tartil bilan oqigan bolsang, shunday oqi. "
                "Zero, sening maqomingiz oxirgi oqigan oyatingizdadir'\" — Abu Dovud",
        "type": "hadith"
    },
    {
        "text": "\"Hafiz kishi uchun jannatda 10 ta yaqiniga shafoat qilish haqqi beriladi\" "
                "— Abu Dovud",
        "type": "hadith"
    },
    {
        "text": "\"Quronni kecha-kunduz yodlang — u sizning qalbingizni nur bilan toldiradi, "
                "ruhingizni poklab, hayotingizga baraka bagishlaydi\" — Ibn Masud",
        "type": "quote"
    },
    {
        "text": "\"Quron oqigan kishiga har bir harf uchun on ta savob yoziladi\" (Termiziy)\n"
                "Va bu savob Allohning marhamati bilan ziyoda bolishi mumkin!",
        "type": "hadith"
    },
    {
        "text": "\"Quronni yodlagan kishi oxiratda tojdor bo'ladi, "
                "ota-onasiga nur sochib turuvchi toj kiydiradi\" — Abu Dovud",
        "type": "hadith"
    },
    {
        "text": "\"Quron — shifodur. Qalb kasalliklariga davoudur\" — Ibn al-Qayyim",
        "type": "quote"
    },
]


def _get_rich_quote() -> dict:
    return random.choice(QURAN_REWARDS_QUOTES)


def _premium_reminder(user: dict) -> str:
    """Returns a short premium reminder line for non-memorize notifications."""
    from services.premium_service import is_premium, get_premium_expiry_str
    if is_premium(user):
        expiry = get_premium_expiry_str(user) or ""
        expiry_str = f" | {expiry} gacha" if expiry else ""
        return f"\n\n\U0001f48e Premium a'zo | \u26a1 2x Himmat ball{expiry_str}"
    return ""


def _build_motivation_text(user: dict) -> str:
    name = user.get("full_name", "Do'stim")
    uid = user.get("telegram_id")
    stats = user.get("stats", {})
    total_verses = stats.get("total_verses_read", 0)
    remaining = max(TOTAL_AYAHS - total_verses, 0)

    reg_date = user.get("registration_date")
    now = datetime.now(TZ)
    if reg_date and hasattr(reg_date, "astimezone"):
        days_active = max((now - reg_date.astimezone(TZ)).days, 1)
    else:
        days_active = 1
    avg_daily = total_verses / days_active if days_active > 0 else 0

    try:
        percentile = get_user_percentile(uid) if uid else 0
    except Exception:
        percentile = 0

    lines = [f"\U0001f4ca {name}, sizning shaxsiy hisobingiz:\n"]

    if total_verses == 0:
        lines.append("Siz hali yodlashni boshlamadingiz.\n")
        lines.append("\U0001f4cc Agar har kuni shuncha oyat yodlasangiz:\n")
        for daily in [3, 5, 10, 20]:
            proj = _calc_hafiz_projection(daily)
            ajr  = _calc_daily_ajr(daily)
            lines.append(f"  \u2022 {daily} oyat/kun \u2192 Hofiz {proj}da | umid qilingan ~{ajr} hasana")
        lines.append(
            f"\n\U0001f4bf Hadis: \"Quron oqigan kishiga har bir harf uchun "
            f"10 ta savob yoziladi\" (Termiziy)\n"
            f"   (Alloh istaganicha, ixlosga qarab kam yoki ziyoda qilishga qodir)"
        )
        lines.append(f"\n\U0001f4aa Birinchi qadamni qo'ying \u2014 1 oyat ham katta boshlang'ich!")
    else:
        if avg_daily >= 1:
            proj = _calc_hafiz_projection(avg_daily)
            lines.append(f"\U0001f4d6 Jami yodlangan: {total_verses:,} / {TOTAL_AYAHS:,} oyat")
            lines.append(f"\U0001f4c8 O'rtacha tezlik: {avg_daily:.1f} oyat/kun")
            lines.append(f"\U0001f54c Shu tezlikda Hofiz bo'lasiz: ~{proj}")
        else:
            lines.append(f"\U0001f4d6 Jami yodlangan: {total_verses:,} oyat")
            lines.append(f"\u23f3 Qolgan: {remaining:,} oyat")

        daily_pace = max(avg_daily, 1)
        ajr = _calc_daily_ajr(int(daily_pace))
        lines.append(
            f"\n\U0001f4bf Umid qilingan kunlik savob: ~{ajr} hasana"
            f"\n   (Termiziy rivoyati asosida; Alloh istaganicha,"
            f"\n    ixlosga qarab kam yoki ziyoda qilishga qodir)"
        )

        if percentile > 0:
            lines.append(f"\n\U0001f3c5 Siz foydalanuvchilarning {percentile}% dan oldinda!")

        if avg_daily < 10:
            faster_daily = min(int(avg_daily) + 5, 20)
            faster_proj = _calc_hafiz_projection(faster_daily)
            lines.append(f"\n\U0001f4a1 Agar kuniga {faster_daily} oyat yodlasangiz \u2192 Hofiz {faster_proj}da!")

    return "\n".join(lines)


def _build_notification(user: dict) -> tuple:
    """Returns (text, keyboard, notif_type) for the notification."""
    name     = user.get("full_name", "Do'stim")
    stats    = user.get("stats", {})
    streak   = stats.get("current_streak_days", 0)
    today    = get_daily_stats(user["telegram_id"])
    t_verses = today.get("verses_read", 0)

    now = datetime.now(TZ)
    if now.weekday() == 0 and now.hour < 10:
        notif_type = "weekly"
    elif streak >= 3 and random.random() < 0.35:
        notif_type = "streak"
    elif random.random() < 0.2:
        notif_type = "motivation"
    else:
        notif_type = random.choice([
            "motivational_uz", "quote", "hadith", "ayah",
            "reward", "quran_reward", "quran_reward",
        ])

    if notif_type == "streak" and streak >= 1:
        streak_emojis = ["\U0001f525", "\u2b50", "\U0001f4aa", "\U0001f31f", "\U0001f3c6"]
        emoji = streak_emojis[min(streak // 7, len(streak_emojis) - 1)]
        prem_line = _premium_reminder(user)
        text = (
            f"{emoji} {name}, {streak}-kunlik streakingiz bor!\n\n"
            f"Bugun ham bir oyat yodlasangiz streak saqlanadi.\n"
            f"Uzmaslik uchun hoziroq 1 daqiqa vaqt ajrating!\n\n"
            f"\U0001f4bf \"Ichlaringizning eng yaxshisi Quronni organuvchi "
            f"va orgatuvchisidir\" \u2014 Buxoriy"
            f"{prem_line}"
        )
        keyboard = snooze_keyboard()

    elif notif_type == "motivation":
        text = _build_motivation_text(user)
        keyboard = open_memorize_keyboard()

    elif notif_type == "motivational_uz":
        mot = random.choice(UZBEK_MOTIVATIONAL_QUOTES)
        prem_line = _premium_reminder(user)
        text = (
            f"\U0001f305 Assalomu alaykum, {name}!\n\n"
            f"{mot}\n\n"
            f"Bugun ham davom etamizmi? \U0001f4aa"
            f"{prem_line}"
        )
        keyboard = open_memorize_keyboard()

    elif notif_type == "quran_reward":
        q = _get_rich_quote()
        ajr_line = ""
        total_v = stats.get("total_verses_read", 0)
        if total_v > 0:
            total_ajr = total_v * AVG_LETTERS_PER_AYAH * HASANA_PER_LETTER
            ajr_str = f"{total_ajr:,}" if total_ajr < 1_000_000 else f"{total_ajr/1_000_000:.1f} mln"
            ajr_line = (
                f"\n\n\U0001f4d6 Siz {total_v:,} oyat yodladingiz!"
                f"\n\U0001f4bf Umid qilingan savob: ~{ajr_str} hasana"
                f"\n   \u2192 Alloh istaganicha, ixlosga qarab kam yoki ziyoda qilishga qodir"
            )
        prem_line = _premium_reminder(user)
        text = (
            f"\U0001f319 Assalomu alaykum, {name}!\n\n"
            f"\U0001f48e Quron ahliga berilgan in'om:\n\n"
            f"{q['text']}"
            f"{ajr_line}\n\n"
            f"Bugun ham davom eting \u2014 har oyat sizning oxiratingizga nurdur! \U0001f932"
            f"{prem_line}"
        )
        keyboard = open_memorize_keyboard()

    elif notif_type == "quote":
        q = random.choice([x for x in QURAN_REWARDS_QUOTES if x["type"] == "quote"]
                          or QURAN_REWARDS_QUOTES)
        prem_line = _premium_reminder(user)
        text = (
            f"\U0001f319 Assalomu alaykum, {name}!\n\n"
            f"\U0001f4ac {q['text']}\n\n"
            f"Bugun ham davom etamizmi? \U0001f4aa"
            f"{prem_line}"
        )
        keyboard = open_memorize_keyboard()

    elif notif_type == "hadith":
        pool = [x for x in QURAN_REWARDS_QUOTES if x["type"] == "hadith"]
        q = random.choice(pool) if pool else _get_rich_quote()
        prem_line = _premium_reminder(user)
        text = (
            f"\U0001f4bf Assalomu alaykum, {name}!\n\n"
            f"Hadisi sharif:\n\n"
            f"{q['text']}\n\n"
            f"Bugun ham Quron yodlashni davom eting! \U0001f932"
            f"{prem_line}"
        )
        keyboard = open_memorize_keyboard()

    elif notif_type == "ayah":
        pool = [x for x in QURAN_REWARDS_QUOTES if x["type"] == "ayah"]
        q = random.choice(pool) if pool else _get_rich_quote()
        prem_line = _premium_reminder(user)
        text = (
            f"\U0001f4d6 Assalomu alaykum, {name}!\n\n"
            f"Quron oyati:\n\n"
            f"{q['text']}\n\n"
            f"Alloh bizni Quron ahllaridan qilsin! \U0001f31f"
            f"{prem_line}"
        )
        keyboard = open_memorize_keyboard()

    elif notif_type == "weekly":
        week_stats = get_period_stats(user["telegram_id"], "week")
        prem_line = _premium_reminder(user)
        text = (
            f"\U0001f4ca HAFTALIK HISOBOT, {name}!\n\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"Bu hafta:\n"
            f"\U0001f4d6 Oyatlar: {week_stats.get('verses_read', 0)}\n"
            f"\U0001f504 Takrorlar: {week_stats.get('repetitions', 0)}\n"
            f"\u23f1 Vaqt: {week_stats.get('minutes', 0)} daqiqa\n"
            f"\U0001f48e Himmat: +{week_stats.get('himmat_earned', 0)}\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
            f"{prem_line}"
        )
        keyboard = open_memorize_keyboard()

    elif notif_type == "reward":
        total_v = stats.get("total_verses_read", 0)
        total_ajr = total_v * AVG_LETTERS_PER_AYAH * HASANA_PER_LETTER
        ajr_str = f"{total_ajr:,}" if total_ajr < 1_000_000 else f"{total_ajr/1_000_000:.1f} million"
        q = _get_rich_quote()
        prem_line = _premium_reminder(user)
        text = (
            f"\u2b50 Assalomu alaykum, {name}!\n\n"
            f"\U0001f4bf Alloh taolo va'da qilgan:\n"
            f"\"Quron oqigan kishiga har bir harf uchun "
            f"10 ta savob yoziladi\" (Termiziy)\n\n"
            f"\U0001f4d6 Siz {total_v:,} oyat yodladingiz\n"
            f"\U0001f4bf Umid qilingan savob: ~{ajr_str} hasana\n"
            f"   (Alloh istaganicha, ixlosga qarab kam yoki ziyoda qilishga qodir)\n\n"
            f"\U0001f48e Qo'shimcha ilhom:\n{q['text']}\n\n"
            f"Bugun ham bir oyat yodlang \u2014 ajr bekor ketmaydi! \U0001f932"
            f"{prem_line}"
        )
        keyboard = open_memorize_keyboard()

    else:
        mot = random.choice(UZBEK_MOTIVATIONAL_QUOTES)
        prem_line = _premium_reminder(user)
        text = (
            f"\U0001f305 Assalomu alaykum, {name}!\n\n"
            f"{mot}\n\n"
            f"Bugun ham davom etamizmi? \U0001f4aa"
            f"{prem_line}"
        )
        keyboard = open_memorize_keyboard()

    return text, keyboard, notif_type


# ─── Main scheduled jobs ──────────────────────────────────────────────────────

async def send_daily_notifications(bot=None):
    if bot is None:
        logger.warning("send_daily_notifications called without bot instance")
        return

    users  = get_all_notification_enabled_users()
    sent   = 0
    failed = 0

    for user in users:
        uid = user.get("telegram_id")
        if not uid:
            continue
        try:
            text, keyboard, notif_type = _build_notification(user)
            await bot.send_message(chat_id=uid, text=text, reply_markup=keyboard)
            log_notification(uid, notif_type, text[:80])
            sent += 1
        except Exception as e:
            logger.warning(f"Notification failed for {uid}: {e}")
            failed += 1
        await asyncio.sleep(0.05)

    logger.info(f"Daily notifications: sent={sent}, failed={failed}")


async def handle_snooze(update: Update, context):
    query = update.callback_query
    await query.answer("2 soatdan so'ng eslatiladi \u2705")
    user_id = query.from_user.id
    user    = get_user(user_id)
    if not user:
        return
    name = user.get("full_name", "Do'stim")

    async def send_snooze():
        await asyncio.sleep(7200)
        try:
            await context.bot.send_message(
                chat_id      = user_id,
                text         = f"\u23f0 {name}, 2 soat otdi! Yodlashni davom ettirishingiz mumkin \U0001f4d6",
                reply_markup = open_memorize_keyboard()
            )
        except Exception:
            pass

    asyncio.create_task(send_snooze())


async def handle_memo_tomorrow(update: Update, context):
    query = update.callback_query
    await query.answer()
    try:
        await query.message.edit_text(
            "\u2705 Ertaga davom etamiz! In shaa ALLOH \U0001f319\n\n"
            "Qolgan oyatlaringiz sizni kutmoqda \U0001f4d6"
        )
    except Exception:
        pass


async def send_xatm_invitation(bot=None):
    if bot is None:
        return
    from services.firebase_service import get_all_users, get_xatm_stats
    try:
        stats = get_xatm_stats()
    except Exception:
        stats = {}

    active_xatms  = stats.get("active_xatms", 0)
    total_readers = stats.get("total_readers", 0)

    text = (
        "\U0001f465 JAMOAVIY XATM\n\n"
        "Quron xatmini jamoa bo'lib birgalikda o'qiymizmi?\n\n"
        "Har bir ishtirokchi 1 ta juz o'qiydi \u2014 birgalikda 30 juz!\n"
        f"\U0001f4ca Hozir faol xatmlar: {active_xatms}\n"
        f"\U0001f54c Jami ishtirokchilar: {total_readers}\n\n"
        "Alloh barcha Quron o'quvchilarni sevadi! \U0001f932"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("\U0001f465 Jamoaviy Xatmga qo'shilish", callback_data="open_xatm")
    ]])

    from services.firebase_service import get_all_users
    users = get_all_users()
    sent = failed = 0
    for u in users:
        uid = u.get("telegram_id")
        if not uid:
            continue
        try:
            await bot.send_message(chat_id=uid, text=text, reply_markup=keyboard)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    logger.info(f"Xatm invitation: sent={sent}, failed={failed}")


async def send_daily_xatm_reminder(bot=None):
    """
    Daily xatm reminder for active participants — sent once per day at 09:00.
    Shows overall progress bar, user's remaining juzs, and encouragement.
    """
    if bot is None:
        return
    from services.firebase_service import get_user, get_xatm_juzs
    from firebase_config import db

    if not db:
        return

    try:
        active_docs = db.collection("group_xatms").where("status", "==", "active").stream()
        active_xatms = [d.to_dict() for d in active_docs]
    except Exception as e:
        logger.error(f"send_daily_xatm_reminder: {e}")
        return

    for xatm in active_xatms:
        xatm_id  = xatm.get("xatm_id")
        xatm_num = xatm.get("xatm_number", "?")
        juzs     = get_xatm_juzs(xatm_id)

        total_done = sum(1 for j in juzs if j["status"] == "completed")

        by_user = {}
        for j in juzs:
            uid = j.get("user_id")
            if uid:
                by_user.setdefault(uid, []).append(j)

        for uid, user_juzs in by_user.items():
            my_done      = sum(1 for j in user_juzs if j["status"] == "completed")
            my_remaining = len(user_juzs) - my_done
            if my_remaining == 0:
                continue

            user = get_user(uid)
            name = user.get("full_name", "Do'stim") if user else "Do'stim"

            pct = int(total_done / 30 * 100)
            bar_filled = int(pct / 5)
            bar = "\U0001f7e9" * bar_filled + "\u2b1c" * (20 - bar_filled)

            encouragements = [
                "Tezroq ulushingizni bajarsangiz xatm yanada tezroq yakunlanadi!",
                "Birgalikda harakat qilsak kuchimiz yanada ortadi!",
                "Har bir o'qilgan juz 30 kishi nomidan Allohga taqdim etiladi!",
                "Xatmdoshlaringiz sizni kutmoqda \u2014 birga yakunlaymiz!",
                "Quron o'qigan tildan farishtalar yiqilmaydi \u2014 davom eting!",
            ]

            my_juz_nums = sorted(j["juz_number"] for j in user_juzs if j["status"] != "completed")
            my_juzs_str = ", ".join(str(n) for n in my_juz_nums) if my_juz_nums else "\u2014"
            enc = random.choice(encouragements)

            text = (
                f"\U0001f4d6 JAMOAVIY XATM #{xatm_num} \u2014 KUNLIK ESLATMA\n\n"
                f"Umumiy progress: {total_done}/30 juz \u2705\n"
                f"[{bar}] {pct}%\n\n"
                f"Sizda qolgan juzlar: {my_juzs_str} ({my_remaining} ta)\n\n"
                f"\U0001f4aa {enc}\n\n"
                f"\U0001f932 Alloh barcha Quron o'quvchilarni sevadi!"
            )
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("\U0001f4d6 Xatmni davom ettirish", callback_data="open_xatm")
            ]])

            try:
                await bot.send_message(chat_id=uid, text=text, reply_markup=keyboard)
            except Exception as e:
                logger.warning(f"Xatm reminder to {uid} failed: {e}")
            await asyncio.sleep(0.05)

    logger.info(f"Daily xatm reminders sent for {len(active_xatms)} active xatm(s)")


async def send_pinned_progress_message(bot, user_id: int):
    """Send or refresh a pinned progress message for the user."""
    user = get_user(user_id)
    if not user:
        return

    from services.premium_service import is_premium
    stats      = user.get("stats", {})
    total_v    = stats.get("total_verses_read", 0)
    himmat     = stats.get("himmat_points", 0)
    pct        = round(total_v / TOTAL_AYAHS * 100, 2) if total_v else 0
    bar_filled = int(pct / 5)
    bar        = "\u2588" * bar_filled + "\u2591" * (20 - bar_filled)
    name       = user.get("full_name", "Foydalanuvchi")
    premium    = is_premium(user)
    badge      = " \U0001f48e Premium" if premium else ""
    xp_badge   = " (2x \u26a1)" if premium else ""

    text = (
        f"\U0001f4cc QURON YODLASH PROGRESSI{badge} \u2014 {name}\n\n"
        f"\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510\n"
        f"\u2502  {pct:.2f}% yodlandi\n"
        f"\u2502  [{bar}]\n"
        f"\u2502  {total_v:,} / {TOTAL_AYAHS:,} oyat\n"
        f"\u2502  \U0001f48e Himmat: {himmat:,} ball{xp_badge}\n"
        f"\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518\n\n"
        f"Davom eting \u2014 Hofiz bo'lish mumkin! \U0001f31f"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("\U0001f4d7 Yodlashni davom ettirish", callback_data="open_memorize")
    ]])

    try:
        msg = await bot.send_message(chat_id=user_id, text=text, reply_markup=keyboard)
        try:
            await bot.pin_chat_message(chat_id=user_id, message_id=msg.message_id,
                                       disable_notification=True)
            from services.firebase_service import update_user
            update_user(user_id, {"pinned_progress_msg_id": msg.message_id})
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"send_pinned_progress_message error for {user_id}: {e}")


async def refresh_all_pinned_messages(bot=None):
    if bot is None:
        return
    from services.firebase_service import get_all_users

    users = get_all_users()
    updated = 0
    for u in users:
        uid = u.get("telegram_id")
        if not uid:
            continue
        old_msg_id = u.get("pinned_progress_msg_id")
        if old_msg_id:
            try:
                await bot.delete_message(chat_id=uid, message_id=old_msg_id)
            except Exception:
                pass
        await send_pinned_progress_message(bot, uid)
        updated += 1
        await asyncio.sleep(0.1)
    logger.info(f"Refreshed pinned progress for {updated} users")


async def send_daily_top5(bot=None):
    """Send top-5 users of the day to all users. Runs daily at 22:00."""
    if bot is None:
        return
    from services.firebase_service import get_all_users
    now_str = datetime.now(TZ).strftime("%Y-%m-%d")

    users = get_all_users()
    daily = []
    for u in users:
        uid = u.get("telegram_id")
        if not uid:
            continue
        try:
            st = get_daily_stats(uid, now_str)
            v  = st.get("verses_read", 0)
            if v > 0:
                daily.append({
                    "name":    u.get("full_name", "Anonim"),
                    "verses":  v,
                    "himmat":  st.get("himmat_earned", 0),
                    "is_anon": u.get("lb_anonymous", False),
                })
        except Exception:
            pass

    if not daily:
        return

    daily.sort(key=lambda x: x["verses"], reverse=True)
    top5   = daily[:5]
    medals = ["\U0001f947", "\U0001f948", "\U0001f949", "4\ufe0f\u20e3", "5\ufe0f\u20e3"]
    lines  = [
        "\U0001f3c6 BUGUNGI TOP-5",
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
        datetime.now(TZ).strftime("%d.%m.%Y"),
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
    ]
    for i, e in enumerate(top5):
        name = "\U0001f9be Anonim" if e.get("is_anon") else e["name"][:18]
        lines.append(f"{medals[i]} {name} \u2014 {e['verses']} oyat")
    lines.append("\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    lines.append(f"Jami {len(daily)} kishi bugun yodladi \U0001f4d6")
    text = "\n".join(lines)

    sent = 0
    for u in users:
        uid = u.get("telegram_id")
        if not uid:
            continue
        try:
            await bot.send_message(chat_id=uid, text=text)
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)
    logger.info(f"Daily top-5 sent to {sent} users")


async def send_weekly_top10(bot=None):
    if bot is None:
        return
    from services.firebase_service import get_all_users
    now = datetime.now(TZ)
    users = get_all_users()

    weekly = []
    for u in users:
        uid = u.get("telegram_id")
        if not uid:
            continue
        try:
            st = get_period_stats(uid, "week")
            v  = st.get("verses_read", 0)
            if v > 0:
                weekly.append({
                    "name":    u.get("full_name", "Anonim"),
                    "verses":  v,
                    "himmat":  st.get("himmat_earned", 0),
                    "is_anon": u.get("lb_anonymous", False),
                })
        except Exception:
            pass

    if not weekly:
        return

    weekly.sort(key=lambda x: x["verses"], reverse=True)
    top10  = weekly[:10]
    medals = ["\U0001f947", "\U0001f948", "\U0001f949",
              "4\ufe0f\u20e3", "5\ufe0f\u20e3", "6\ufe0f\u20e3",
              "7\ufe0f\u20e3", "8\ufe0f\u20e3", "9\ufe0f\u20e3", "\U0001f51f"]
    week_label = now.strftime("%d.%m") + " hafta"
    lines = [
        "\U0001f3c6 HAFTALIK TOP-10",
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
        week_label,
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
    ]
    for i, e in enumerate(top10):
        name = "\U0001f9be Anonim" if e.get("is_anon") else e["name"][:18]
        lines.append(f"{medals[i]} {name} \u2014 {e['verses']} oyat")
    lines.append("\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    lines.append(f"Jami {len(weekly)} kishi bu hafta yodladi \U0001f4d6")
    lines.append("Alloh barchadan qabul qilsin! \U0001f932")
    text = "\n".join(lines)

    sent = 0
    for u in users:
        uid = u.get("telegram_id")
        if not uid:
            continue
        try:
            await bot.send_message(chat_id=uid, text=text)
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)
    logger.info(f"Weekly top-10 sent to {sent} users")


async def send_monthly_top10(bot=None):
    if bot is None:
        return
    from services.firebase_service import get_all_users
    now   = datetime.now(TZ)
    users = get_all_users()

    monthly = []
    for u in users:
        uid = u.get("telegram_id")
        if not uid:
            continue
        try:
            st = get_period_stats(uid, "month")
            v  = st.get("verses_read", 0)
            if v > 0:
                monthly.append({
                    "name":    u.get("full_name", "Anonim"),
                    "verses":  v,
                    "himmat":  st.get("himmat_earned", 0),
                    "is_anon": u.get("lb_anonymous", False),
                })
        except Exception:
            pass

    if not monthly:
        return

    monthly.sort(key=lambda x: x["verses"], reverse=True)
    top10  = monthly[:10]
    medals = ["\U0001f947", "\U0001f948", "\U0001f949",
              "4\ufe0f\u20e3", "5\ufe0f\u20e3", "6\ufe0f\u20e3",
              "7\ufe0f\u20e3", "8\ufe0f\u20e3", "9\ufe0f\u20e3", "\U0001f51f"]
    month_label = now.strftime("%B %Y")
    lines = [
        "\U0001f3c6 OYLIK TOP-10",
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
        month_label,
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
    ]
    for i, e in enumerate(top10):
        name = "\U0001f9be Anonim" if e.get("is_anon") else e["name"][:18]
        lines.append(f"{medals[i]} {name} \u2014 {e['verses']} oyat")
    lines.append("\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    lines.append(f"Jami {len(monthly)} kishi bu oy yodladi \U0001f4d6")
    lines.append("Alloh barchadan qabul qilsin! \U0001f932")
    text = "\n".join(lines)

    sent = 0
    for u in users:
        uid = u.get("telegram_id")
        if not uid:
            continue
        try:
            await bot.send_message(chat_id=uid, text=text)
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)
    logger.info(f"Monthly top-10 sent to {sent} users")


async def send_admin_daily_report(bot=None, admin_id: int = None):
    """Detailed per-user daily report to admin with up-to-date stats."""
    if bot is None or admin_id is None:
        return
    from services.firebase_service import get_all_users, get_xatm_stats
    now_str  = datetime.now(TZ).strftime("%Y-%m-%d")
    now_disp = datetime.now(TZ).strftime("%d.%m.%Y %H:%M")

    users = get_all_users()
    active_rows = []

    for u in users:
        uid = u.get("telegram_id")
        if not uid:
            continue
        try:
            st = get_daily_stats(uid, now_str)
        except Exception:
            continue
        verses = st.get("verses_read", 0)
        reps   = st.get("repetitions", 0)
        mins   = st.get("minutes", 0)
        himmat = st.get("himmat_earned", 0)
        if verses == 0 and reps == 0:
            continue
        name = (u.get("full_name") or "Anonim")[:18]
        username = u.get("username", "")
        uname_str = f"@{username}" if username else f"#{uid}"
        is_premium_flag = u.get("premium", {}).get("is_active", False)
        streak = u.get("stats", {}).get("current_streak_days", 0)
        total_verses_all = u.get("stats", {}).get("total_verses_read", 0)
        active_rows.append({
            "name":         name,
            "uname":        uname_str,
            "verses":       verses,
            "reps":         reps,
            "mins":         mins,
            "himmat":       himmat,
            "premium":      is_premium_flag,
            "streak":       streak,
            "total_verses": total_verses_all,
        })

    active_rows.sort(key=lambda x: x["verses"], reverse=True)

    premium_users = [u for u in users if u.get("premium", {}).get("is_active")]
    total_users   = len(users)
    total_active  = len(active_rows)
    total_verses  = sum(r["verses"] for r in active_rows)
    total_mins    = sum(r["mins"]   for r in active_rows)
    total_premium = len(premium_users)

    try:
        xatm_stats = get_xatm_stats()
    except Exception:
        xatm_stats = {}

    lines = [
        f"\U0001f4ca ADMIN KUNLIK HISOBOT \u2014 {now_disp}",
        "\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550",
        f"\U0001f465 Jami foydalanuvchilar: {total_users}",
        f"\U0001f48e Premium: {total_premium}",
        f"\u2705 Bugun faol: {total_active}",
        f"\U0001f4d6 Bugun yangi oyatlar: {total_verses}",
        f"\u23f1 Jami vaqt: {total_mins} daqiqa",
        f"\U0001f54c Yakunlangan xatmlar: {xatm_stats.get('total_xatms', 0)}",
        "\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550",
        "\U0001f464 FAOL FOYDALANUVCHILAR:",
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
    ]

    for r in active_rows:
        acc_reps  = max(0, r["reps"] - r["verses"] * 21)
        acc_count = acc_reps // 5
        detail    = f"\U0001f4d6 {r['verses']} yangi oyat"
        if acc_count > 0:
            detail += f" | \U0001f501 {acc_count} takrorlash"
        mins_str    = f" | \u23f1 {r['mins']}d" if r["mins"] > 0 else ""
        streak_str  = f" | \U0001f525{r['streak']}" if r["streak"] > 1 else ""
        premium_str = " \U0001f48e" if r["premium"] else ""
        total_str   = f" | jami: {r['total_verses']:,}" if r["total_verses"] > 0 else ""
        lines.append(
            f"\u2022 {r['name']}{premium_str} ({r['uname']})\n"
            f"  {detail}{mins_str}{streak_str}{total_str} | +{r['himmat']} XP"
        )

    lines.append("\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550")
    text = "\n".join(lines)

    chunk_size = 4000
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    for chunk in chunks:
        try:
            await bot.send_message(chat_id=admin_id, text=chunk)
        except Exception as e:
            logger.error(f"Admin daily report send error: {e}")
    logger.info(f"Admin daily report sent: {total_active} active users")


async def _refer_for_premium(update, context):
    """Show referral link when user taps 'Invite friend for 1-day Premium'."""
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user    = get_user(user_id)
    if not user:
        return
    ref_code = user.get("referral_code", "")
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"
    text = (
        "\U0001f381 DO'ST TAKLIF QILING \u2014 1 KUN PREMIUM OLING!\n\n"
        "Quyidagi havolani do'stingizga yuboring.\n"
        "Do'stingiz botga qo'shilsa, sizga avtomatik ravishda\n"
        "\U0001f48e 1 kunlik BEPUL Premium faollashadi!\n\n"
        f"\U0001f517 Sizning havolangiz:\n{ref_link}\n\n"
        "\U0001f4de Har bir taklif uchun +15 Himmat ball ham beriladi!"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "\U0001f4e4 Havolani ulashish",
            url=f"https://t.me/share/url?url={ref_link}&text=Quronni+ilmiy+usulda+yodlash!"
        )
    ]])
    try:
        await query.message.reply_text(text, reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"refer_for_premium send failed: {e}")


def register_notification_handlers(app):
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(handle_snooze,        pattern="^snooze_2h$"))
    app.add_handler(CallbackQueryHandler(handle_memo_tomorrow, pattern="^memo_tomorrow$"))
    app.add_handler(CallbackQueryHandler(_refer_for_premium,   pattern="^refer_for_premium$"))

    async def _open_xatm(update, context):
        query = update.callback_query
        await query.answer()
        from handlers.xatm import show_xatm_dashboard
        await show_xatm_dashboard(update, context)

    app.add_handler(CallbackQueryHandler(_open_xatm, pattern="^open_xatm$"))
