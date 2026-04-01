import os
from dotenv import load_dotenv

load_dotenv()

# ─── Bot Settings ─────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "8770428749:AAEM1frAdej02vdp6LW7wPgvbthXa6idH8o")
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "917456291"))

# ─── Webhook / Server ─────────────────────────────────────────────────────────
WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
PORT: int = int(os.getenv("PORT", "8080"))

# ─── Bot Logic Constants ───────────────────────────────────────────────────────
DAILY_FREE_LIMIT: int = 5          # free users: max new ayahs per day
TRIAL_DAYS: int = 1               # free trial duration
REFERRAL_BONUS: int = 15          # Himmat points per referral
ONBOARDING_BONUS: int = 50        # bonus for completing onboarding
FIRST_AYAH_BONUS: int = 25        # bonus for first ayah memorized
DAILY_LOGIN_BONUS: int = 5        # bonus for daily first session

# ─── Himmat Ball Rules ─────────────────────────────────────────────────────────
HIMMAT_PER_3_REPS: int = 2
HIMMAT_PER_7_REPS: int = 5
HIMMAT_PER_11_REPS: int = 8
HIMMAT_PER_ACCUMULATION: int = 3   # per ayah in accumulation round
HIMMAT_PER_AYAH_COMPLETE: int = 15
HIMMAT_PER_SURAH_COMPLETE_MULTIPLIER: int = 5   # × ayah count
HIMMAT_PER_JUZ_COMPLETE: int = 500

# ─── Streak Bonuses ────────────────────────────────────────────────────────────
STREAK_BONUSES: dict = {
    3: 20,
    7: 100,
    14: 250,
    30: 500,
    100: 2000,
}

# ─── Level Thresholds ─────────────────────────────────────────────────────────
LEVELS: list = [
    (0,    "🌱 Mubtadi"),
    (100,  "📖 Tolibul Ilm"),
    (500,  "🔆 Mushtoq"),
    (1000, "⭐ Hafiz Yo'li"),
    (2500, "🌙 Qur'on Muhhibi"),
    (5000, "🌟 Aziz Hofiz"),
    (10000,"👑 Qur'on Sultoni"),
]

# ─── Quran API ─────────────────────────────────────────────────────────────────
ALQURAN_API_BASE = "https://api.alquran.cloud/v1"
AUDIO_CDN_BASE   = "https://cdn.islamic.network/quran/audio/128"
QURANICAUDIO_BASE = "https://download.quranicaudio.com/quran"

# ─── Reciter Identifiers ───────────────────────────────────────────────────────
RECITERS = {
    "husary":    {"name": "🎵 Husary (Muallim)",      "api_id": "ar.husarymujawwad",          "folder": "husary_muallim"},
    "afasy":     {"name": "🎵 Al-Afasy",               "api_id": "ar.alafasy",                 "folder": "mishaari_raashid_al_3afaasee"},
    "ghamdi":    {"name": "🎵 Al-Ghamdi",              "api_id": "ar.alghamdi",                "folder": "sa3d_al-ghaamidi"},
    "sudais":    {"name": "🎵 As-Sudais",              "api_id": "ar.abdurrahmaansudais",      "folder": "abdurrahmaan_as-sudays"},
    "minshawi":  {"name": "🎵 Minshawi (Muallim)",     "api_id": "ar.minshawimujawwad",        "folder": "minshawi"},
    # Listening reciters (full surah download)
    "abdulbasit":{"name": "🎵 Abdul Basit Abdus-Samad","api_id": "ar.abdulbasitmurattal",     "folder": "abdulbaset/mujawwad"},
    "muaiqly":   {"name": "🎵 Maher Al-Muaiqly",       "api_id": "ar.mahermuaiqly",            "folder": "maher_al_muaiqly"},
    "matrood":   {"name": "🎵 Abdullah Al-Matrood",    "api_id": "ar.abdullaahmatrood",        "folder": "abdullaah_3awwaad_al-juhaynee"},
    "shatri":    {"name": "🎵 Abu Bakr Ash-Shatri",    "api_id": "ar.ahmadibnali",             "folder": "abu_bakr_ash-shaatree"},
}

# ─── Notification Types ───────────────────────────────────────────────────────
NOTIFICATION_TYPES = ["motivational", "quote", "reward", "streak", "weekly"]

# ─── Timezone ─────────────────────────────────────────────────────────────────
LOCAL_TZ = "Asia/Tashkent"

# ─── Conversation States ──────────────────────────────────────────────────────
# Onboarding
ONBOARDING_START    = 0
ONBOARDING_NAME     = 1
ONBOARDING_LEVEL    = 2
ONBOARDING_SURAHS   = 3
ONBOARDING_LOCATION = 4
ONBOARDING_GOAL     = 5
ONBOARDING_TIME     = 6

# Memorize
MEMO_SELECT_JUZ       = 10
MEMO_SELECT_DIRECTION = 11
MEMO_SELECT_RECITER   = 12
MEMO_SELECT_SURAH     = 13
MEMO_IN_PROGRESS      = 14
MEMO_REP_3            = 15
MEMO_REP_7            = 16
MEMO_REP_11           = 17
MEMO_ACCUMULATION     = 18
MEMO_ACC_7            = 19

# Admin
ADMIN_BROADCAST      = 20
ADMIN_USER_SEARCH    = 21
ADMIN_REJECT_REASON  = 22
ADMIN_PREMIUM_MONTHS = 23

# Premium
PREMIUM_AWAIT_RECEIPT = 30

# Listen
LISTEN_SELECT_SURAH  = 40

# Admin ayah photo
ADMIN_AYAH_PHOTO_SURAH        = 50
ADMIN_AYAH_PHOTO_AYAH         = 51
ADMIN_AYAH_PHOTO_UPLOAD       = 52
ADMIN_AYAH_PHOTO_SURAH_SELECT = 55   # inline surah picker
ADMIN_AYAH_PHOTO_AYAH_SELECT  = 56   # inline ayah picker

# Admin notification time / count
ADMIN_NOTIF_TIME  = 53
ADMIN_NOTIF_COUNT = 54

# Contact Admin
CONTACT_AWAIT_MSG = 60

# Settings
SETTINGS_NOTIF_COUNT = 70
