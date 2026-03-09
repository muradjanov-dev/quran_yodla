"""
keyboards.py — All InlineKeyboard and ReplyKeyboard builders.
"""

import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import RECITERS


# ─── Main Menu ────────────────────────────────────────────────────────────────

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["📗 Yodlash",  "📊 Sahifam"],
            ["🎧 Tinglash", "🏆 Reyting"],
            ["💎 Premium",  "👥 Do'st taklif"],
            ["📞 Murojaat"],
        ],
        resize_keyboard=True,
    )


# ─── Onboarding ───────────────────────────────────────────────────────────────

def onboarding_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Boshlash ✅", callback_data="onboarding_start")
    ]])


def onboarding_level_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("0 juz",     callback_data="level_0"),
            InlineKeyboardButton("1-5 juz",   callback_data="level_5"),
            InlineKeyboardButton("6-15 juz",  callback_data="level_15"),
        ],
        [
            InlineKeyboardButton("16-29 juz", callback_data="level_29"),
            InlineKeyboardButton("30 juz (Hofiz)", callback_data="level_30"),
        ],
        [
            InlineKeyboardButton("Aniq suralarni yozaman", callback_data="level_custom"),
        ],
    ])


def onboarding_time_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("15 daqiqa", callback_data="time_15"),
            InlineKeyboardButton("30 daqiqa", callback_data="time_30"),
        ],
        [
            InlineKeyboardButton("1 soat",    callback_data="time_60"),
            InlineKeyboardButton("2 soat+",   callback_data="time_120"),
        ],
    ])


# ─── Memorize ─────────────────────────────────────────────────────────────────

def juz_selection_keyboard(has_active_session: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    if has_active_session:
        buttons.append([InlineKeyboardButton("▶️ Davom etish", callback_data="memo_continue")])

    row = []
    for juz in range(1, 31):
        row.append(InlineKeyboardButton(f"{juz}-juz", callback_data=f"juz_{juz}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def direction_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬆️ Naba → Nos (Klassik)",    callback_data="dir_forward")],
        [InlineKeyboardButton("⬇️ Nos → Naba (Oson boshlash)", callback_data="dir_backward")],
    ])


def reciter_keyboard(for_memorize: bool = True, is_premium: bool = False) -> InlineKeyboardMarkup:
    if not for_memorize:
        reciters = ["abdulbasit", "afasy", "muaiqly", "matrood", "husary", "ghamdi", "sudais", "shatri"]
        buttons = [[InlineKeyboardButton(RECITERS[r]["name"], callback_data=f"reciter_{r}")]
                   for r in reciters if r in RECITERS]
    elif is_premium:
        reciters = ["husary", "afasy", "ghamdi", "sudais", "minshawi"]
        buttons = [[InlineKeyboardButton(RECITERS[r]["name"], callback_data=f"reciter_{r}")]
                   for r in reciters if r in RECITERS]
    else:
        # Free: Husary only, others show as locked
        buttons = [[InlineKeyboardButton(RECITERS["husary"]["name"] + " ✅", callback_data="reciter_husary")]]
        for r in ["afasy", "ghamdi", "sudais", "minshawi"]:
            if r in RECITERS:
                buttons.append([InlineKeyboardButton(
                    RECITERS[r]["name"] + " 💎 Premium",
                    callback_data="reciter_locked"
                )])
    return InlineKeyboardMarkup(buttons)


def surah_selection_keyboard(surah_list: list) -> InlineKeyboardMarkup:
    """surah_list: list of dicts with 'number', 'name'"""
    buttons = [[InlineKeyboardButton("▶️ Boshidan boshlash", callback_data="surah_start")]]
    row = []
    for s in surah_list:
        btn = InlineKeyboardButton(
            f"{s['name']} ({s['number']})",
            callback_data=f"surah_{s['number']}"
        )
        row.append(btn)
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def repetition_keyboard(count: int, stage: str) -> InlineKeyboardMarkup:
    emoji_map = {3: "3️⃣", 7: "7️⃣", 11: "🔟"}
    emoji = emoji_map.get(count, str(count))
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"✅ {count} marotaba o'qidim",
            callback_data=f"rep_done_{stage}"
        )
    ]])


def accumulation_keyboard(ayah_count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"✅ {ayah_count} oyatni 5 marta o'qidim",
            callback_data="acc_done"
        )
    ]])


def checkpoint_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ Davom etish", callback_data="memo_go"),
            InlineKeyboardButton("💾 Saqlash va chiqish", callback_data="memo_save_exit"),
        ]
    ])


def limit_reached_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Premium olish",         callback_data="open_premium")],
        [InlineKeyboardButton("⏰ Ertaga davom etish",     callback_data="memo_tomorrow")],
    ])


# ─── Profile ──────────────────────────────────────────────────────────────────

def profile_period_keyboard(active: str = "today") -> InlineKeyboardMarkup:
    periods = [("Bugun", "today"), ("Hafta", "week"), ("Oy", "month"), ("Yil", "year")]
    row = []
    for label, key in periods:
        text = f"[{label}]" if key == active else label
        row.append(InlineKeyboardButton(text, callback_data=f"profile_period_{key}"))
    return InlineKeyboardMarkup([
        row,
        [
            InlineKeyboardButton("📤 Natijani ulashish", callback_data="profile_share"),
            InlineKeyboardButton("⚙️ Sozlamalar",         callback_data="profile_settings"),
        ]
    ])


# ─── Listen ───────────────────────────────────────────────────────────────────

def listen_reciter_keyboard() -> InlineKeyboardMarkup:
    listen_reciters = ["abdulbasit", "afasy", "muaiqly", "matrood", "husary", "ghamdi", "sudais", "shatri"]
    buttons = [[InlineKeyboardButton(RECITERS[r]["name"], callback_data=f"listen_reciter_{r}")]
               for r in listen_reciters if r in RECITERS]
    return InlineKeyboardMarkup(buttons)


def listen_juz_keyboard() -> InlineKeyboardMarkup:
    row = []
    buttons = []
    for juz in range(1, 31):
        row.append(InlineKeyboardButton(f"{juz}", callback_data=f"listen_juz_{juz}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


# ─── Premium ──────────────────────────────────────────────────────────────────

def premium_keyboard(trial_available: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    if trial_available:
        buttons.append([InlineKeyboardButton(
            "🎁 Bepul Premiumni faollashtirish",
            callback_data="premium_trial"
        )])
    buttons.append([InlineKeyboardButton(
        "📸 Chekni yuborish",
        callback_data="premium_send_receipt"
    )])
    return InlineKeyboardMarkup(buttons)


def admin_premium_decision_keyboard(req_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tasdiqlash — 1 oy",  callback_data=f"admin_approve_{req_id}"),
            InlineKeyboardButton("❌ Rad etish",           callback_data=f"admin_reject_{req_id}"),
        ]
    ])


# ─── Leaderboard ──────────────────────────────────────────────────────────────

def leaderboard_period_keyboard(active: str = "month") -> InlineKeyboardMarkup:
    periods = [("📅 Haftalik", "week"), ("📆 Oylik", "month"),
               ("📅 Yillik", "year"), ("🏆 Umumiy", "all")]
    row = []
    for label, key in periods:
        text = f"[{label}]" if key == active else label
        row.append(InlineKeyboardButton(text, callback_data=f"lb_{key}"))
    return InlineKeyboardMarkup([row])


# ─── Referral ─────────────────────────────────────────────────────────────────

def referral_share_keyboard(ref_link: str) -> InlineKeyboardMarkup:
    share_text = (
        f"🕌 Qur'onni ilmiy usulda yodlashga yordam beruvchi bot! "
        f"Men ham foydalamoqdaman. Siz ham ko'ring: {ref_link}"
    )
    url = f"https://t.me/share/url?url={ref_link}&text={share_text}"
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📤 Havolani ulashish", url=url)
    ]])


# ─── Admin ────────────────────────────────────────────────────────────────────

def admin_main_keyboard(pending_count: int = 0, notif_time: str = "08:00") -> InlineKeyboardMarkup:
    premium_label = f"📋 Premium so'rovlar ({pending_count} ta kutilmoqda)" if pending_count else "📋 Premium so'rovlar"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Barcha foydalanuvchilar",      callback_data="admin_users_0")],
        [InlineKeyboardButton("👤 User boshqarish",              callback_data="admin_user_mgmt")],
        [InlineKeyboardButton("💎 Premium berish",               callback_data="admin_give_premium")],
        [InlineKeyboardButton("📢 Xabar yuborish",               callback_data="admin_broadcast")],
        [InlineKeyboardButton(premium_label,                     callback_data="admin_pending_requests")],
        [InlineKeyboardButton("🖼 Oyatga rasm qo'shish",         callback_data="admin_ayah_photo")],
        [InlineKeyboardButton(f"⏰ Bildirishnoma: {notif_time}", callback_data="admin_notif_time")],
        [InlineKeyboardButton("📊 Batafsil statistika",          callback_data="admin_stats")],
    ])


def admin_user_actions_keyboard(target_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💎 Premium ber (30 kun)", callback_data=f"admin_prem30_{target_id}"),
            InlineKeyboardButton("💎 7 kun",               callback_data=f"admin_prem7_{target_id}"),
        ],
        [InlineKeyboardButton("❌ Premiumni o'chir",         callback_data=f"admin_rem_prem_{target_id}")],
        [InlineKeyboardButton("↩️ Orqaga",                   callback_data="admin_back")],
    ])


# ─── Notifications ────────────────────────────────────────────────────────────

def snooze_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📗 Yodlash",               callback_data="open_memorize"),
            InlineKeyboardButton("⏰ Keyinroq eslatish",      callback_data="snooze_2h"),
        ]
    ])


def open_memorize_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📗 Yodlashni boshlash", callback_data="open_memorize")
    ]])


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Ha, yuborish",   callback_data="broadcast_confirm"),
        InlineKeyboardButton("❌ Bekor qilish",   callback_data="broadcast_cancel"),
    ]])


def contact_reply_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("↩️ Javob qaytarish", callback_data=f"contact_reply_{user_id}"),
    ]])
