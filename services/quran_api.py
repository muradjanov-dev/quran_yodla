"""
quran_api.py — AlQuran.cloud API wrapper
Provides ayah text (Arabic + Uzbek) and audio URL resolution.
"""

import asyncio
import logging
import re
from typing import Optional
import requests

from config import ALQURAN_API_BASE, AUDIO_CDN_BASE, RECITERS

logger = logging.getLogger(__name__)


def _strip_tafsir(text: str) -> str:
    """Remove parenthetical commentary/tafsir from Uzbek translation text."""
    text = re.sub(r'\s*\([^)]*\)', '', text)
    text = re.sub(r'\s*\[[^\]]*\]', '', text)
    return text.strip()


# Simple in-memory cache: key -> (data, timestamp)
_cache: dict = {}
CACHE_TTL = 3600  # 1 hour


def _cached_get(url: str) -> Optional[dict]:
    import time
    if url in _cache:
        data, ts = _cache[url]
        if time.time() - ts < CACHE_TTL:
            return data
    return None


def _set_cache(url: str, data: dict):
    import time
    _cache[url] = (data, time.time())


def _get(url: str, retries: int = 3) -> Optional[dict]:
    cached = _cached_get(url)
    if cached is not None:
        return cached

    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == 200:
                _set_cache(url, data)
                return data
        except Exception as e:
            logger.warning(f"API attempt {attempt+1}/{retries} failed: {e}")
            if attempt < retries - 1:
                import time; time.sleep(2 ** attempt)
    return None


def get_ayah(surah: int, ayah: int) -> Optional[dict]:
    """
    Returns a dict with:
      - arabic: Arabic text
      - uzbek: Uzbek translation
      - global_number: global ayah number (for audio URL)
      - surah_number: surah number
      - ayah_number: ayah number in surah
    """
    arabic_url = f"{ALQURAN_API_BASE}/ayah/{surah}:{ayah}/quran-uthmani"
    uzbek_url  = f"{ALQURAN_API_BASE}/ayah/{surah}:{ayah}/uz.sodik"

    arabic_data = _get(arabic_url)
    uzbek_data  = _get(uzbek_url)

    if not arabic_data:
        return None

    raw_uzbek = uzbek_data["data"]["text"] if uzbek_data else "(tarjima yo'q)"
    result = {
        "arabic":        arabic_data["data"]["text"] if arabic_data else "",
        "uzbek":         _strip_tafsir(raw_uzbek),
        "global_number": arabic_data["data"]["number"] if arabic_data else 0,
        "surah_number":  surah,
        "ayah_number":   ayah,
    }
    return result


def get_audio_url(global_number: int, reciter_key: str = "husary") -> str:
    """Returns direct mp3 audio URL for a single ayah."""
    reciter = RECITERS.get(reciter_key, RECITERS["husary"])
    api_id = reciter["api_id"]
    return f"{AUDIO_CDN_BASE}/{api_id}/{global_number}.mp3"


def get_surah_audio_url(surah_number: int, reciter_key: str = "afasy") -> str:
    """Returns full-surah download URL from quranicaudio.com."""
    reciter = RECITERS.get(reciter_key, RECITERS["afasy"])
    folder = reciter["folder"]
    return f"https://download.quranicaudio.com/quran/{folder}/{surah_number:03d}.mp3"


def get_surah_info(surah: int) -> Optional[dict]:
    """Returns surah metadata from AlQuran API."""
    url = f"{ALQURAN_API_BASE}/surah/{surah}"
    data = _get(url)
    if data:
        return data.get("data")
    return None


def get_surah_ayahs(surah: int) -> Optional[list]:
    """Returns list of all ayahs in a surah (Arabic + Uzbek merged)."""
    arabic_url = f"{ALQURAN_API_BASE}/surah/{surah}/quran-uthmani"
    uzbek_url  = f"{ALQURAN_API_BASE}/surah/{surah}/uz.sodik"

    arabic_data = _get(arabic_url)
    uzbek_data  = _get(uzbek_url)

    if not arabic_data:
        return None

    arabic_ayahs = arabic_data["data"]["ayahs"]
    uzbek_ayahs  = uzbek_data["data"]["ayahs"] if uzbek_data else []
    uzbek_map    = {a["numberInSurah"]: a["text"] for a in uzbek_ayahs}

    result = []
    for a in arabic_ayahs:
        result.append({
            "arabic":        a["text"],
            "uzbek":         _strip_tafsir(uzbek_map.get(a["numberInSurah"], "(tarjima yo'q)")),
            "global_number": a["number"],
            "surah_number":  surah,
            "ayah_number":   a["numberInSurah"],
        })
    return result
