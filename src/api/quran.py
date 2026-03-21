"""Quran API v2 — multi-edition single call: Arabic + Uzbek + audio per ayah.

Key endpoint: GET /v1/ayah/{S}:{A}/editions/ar.alquran,uz.sodik,{qari}
Returns list: [0]=arabic text, [1]=uzbek translation, [2]=audio URL from qari
"""
import httpx
from typing import Optional

BASE = "https://api.alquran.cloud/v1"

# 5 famous reciters: (display_en, display_uz, edition_id)
RECITERS = [
    ("Mishary Al-Afasy",       "Mishary Al-Afasy",       "ar.alafasy"),
    ("Abdul Basit (Murattal)", "Abdul Basit (Murattal)", "ar.abdulbasitmurattal"),
    ("Maher Al-Muaiqly",       "Maher Al-Muaiqly",       "ar.mahermuaiqly"),
    ("Minshawi (Murattal)",    "Minshawi (Murattal)",    "ar.minshawi"),
    ("Saad Al-Ghamdi",         "Saad Al-Ghamdi",          "ar.saadalghamdi"),
]

# EveryAyah.com direct CDN — zero API limits, instant audio
# Format: https://everyayah.com/data/{folder}/{surah:03d}{ayah:03d}.mp3
EVERYAYAH_RECITERS: dict[str, str] = {
    "ar.alafasy":            "Alafasy_128kbps",
    "ar.abdulbasitmurattal": "Abdul_Basit_Murattal_192kbps",
    "ar.mahermuaiqly":       "Maher_AlMuaiqly_128kbps",
    "ar.minshawi":           "Minshawi_Murattal_128kbps",
    "ar.saadalghamdi":       "Saad_Al-Ghamdi_128kbps",
}

def get_everyayah_url(surah: int, ayah: int, edition: str = "ar.alafasy") -> str:
    """Return direct CDN MP3 URL from everyayah.com (no API, no rate limits)."""
    folder = EVERYAYAH_RECITERS.get(edition, "Alafasy_128kbps")
    return f"https://everyayah.com/data/{folder}/{surah:03d}{ayah:03d}.mp3"

# Complete Quran ayah counts (114 surahs, 1-indexed)
AYAH_COUNTS = [
    7,13,200,176,120,165,206,75,129,109,
    123,111,43,52,99,128,111,110,98,135,
    112,78,118,64,77,227,93,88,69,60,
    34,30,73,54,45,83,182,88,75,85,
    54,53,89,59,37,35,38,29,18,45,
    60,49,62,55,78,96,29,22,24,13,
    14,11,11,18,12,12,30,52,52,28,
    28,20,56,40,31,50,45,6,29,22,
    88,41,23,31,36,13,14,11,11,18,
    12,12,30,11,11,29,6,6,17,23,
    11,19,5,8,8,19,5,8,8,11,
    16,4,5,2,2,3,2,
]

def get_ayah_count(surah: int) -> int:
    return AYAH_COUNTS[surah - 1] if 1 <= surah <= 114 else 0

# ── In-memory cache ─────────────────────────────────────────────────────────
_surah_list_cache: list[dict] | None = None
_ayah_full_cache: dict[str, dict] = {}   # key: "surah:ayah:edition"
_ayah_list_cache: dict[int, list[dict]] = {}  # key: surah_number

async def get_surah_list() -> list[dict]:
    global _surah_list_cache
    if _surah_list_cache:
        return _surah_list_cache
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{BASE}/surah")
    d = r.json()
    if d.get("code") == 200:
        _surah_list_cache = d["data"]
    return _surah_list_cache or []

async def get_surah_info(surah_number: int) -> dict | None:
    surahs = await get_surah_list()
    return next((s for s in surahs if s["number"] == surah_number), None)

async def get_ayah_full(surah: int, ayah: int, qari: str = "ar.alafasy") -> dict:
    """Fetch Arabic text + Uzbek translation + audio URL in ONE API call.

    Returns dict:
        arabic, translation, audio_url, global_num
    """
    key = f"{surah}:{ayah}:{qari}"
    if key in _ayah_full_cache:
        return _ayah_full_cache[key]

    editions = f"ar.alquran,uz.sodik,{qari}"
    url = f"{BASE}/ayah/{surah}:{ayah}/editions/{editions}"

    result = {"arabic": "—", "translation": "—", "audio_url": None}
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(url)
        d = r.json()
        if d.get("code") == 200 and isinstance(d.get("data"), list):
            data = d["data"]
            if len(data) >= 1:
                result["arabic"] = data[0].get("text", "—")
                result["global_num"] = data[0].get("number", 0)
            if len(data) >= 2:
                result["translation"] = data[1].get("text", "—")
            if len(data) >= 3:
                result["audio_url"] = data[2].get("audio") or data[2].get("audioSecondary", [None])[0]
    except Exception as e:
        print(f"[Quran API] get_ayah_full {surah}:{ayah} error: {e}")

    _ayah_full_cache[key] = result
    return result

async def get_ayahs(surah_number: int, qari: str = "ar.alafasy") -> list[dict]:
    """All ayahs in a surah with Arabic + uz.sodik translation."""
    if surah_number in _ayah_list_cache:
        return _ayah_list_cache[surah_number]
    editions = f"ar.alquran,uz.sodik"
    url = f"{BASE}/surah/{surah_number}/editions/{editions}"
    result = []
    try:
        async with httpx.AsyncClient(timeout=25) as c:
            r = await c.get(url)
        d = r.json()
        if d.get("code") == 200 and isinstance(d.get("data"), list):
            ar_ayahs = d["data"][0].get("ayahs", [])
            uz_ayahs = d["data"][1].get("ayahs", []) if len(d["data"]) > 1 else []
            uz_map = {a["numberInSurah"]: a["text"] for a in uz_ayahs}
            for a in ar_ayahs:
                num = a["numberInSurah"]
                result.append({
                    "number": num,
                    "text": a["text"],
                    "translation": uz_map.get(num, ""),
                    "globalNum": a.get("number", 0),
                    "surah": surah_number,
                })
    except Exception as e:
        print(f"[Quran API] get_ayahs {surah_number} error: {e}")
    if result:
        _ayah_list_cache[surah_number] = result
    return result

async def get_ayah(surah_number: int, ayah_number: int) -> dict | None:
    ayahs = await get_ayahs(surah_number)
    return next((a for a in ayahs if a["number"] == ayah_number), None)
