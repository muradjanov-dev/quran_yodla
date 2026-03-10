"""
helpers.py — Miscellaneous helper functions.
"""

import json
import os
import logging
import re
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"

_surahs_data: Optional[list] = None
_juz_map: Optional[dict]     = None


def load_surahs() -> list:
    global _surahs_data
    if _surahs_data is None:
        with open(DATA_DIR / "surahs.json", encoding="utf-8") as f:
            _surahs_data = json.load(f)
    return _surahs_data


def load_juz_map() -> dict:
    global _juz_map
    if _juz_map is None:
        with open(DATA_DIR / "juz_map.json", encoding="utf-8") as f:
            _juz_map = json.load(f)
    return _juz_map


def get_surah_by_number(number: int) -> Optional[dict]:
    for s in load_surahs():
        if s["number"] == number:
            return s
    return None


def get_surah_by_name(name: str) -> Optional[dict]:
    name_lower = name.lower()
    for s in load_surahs():
        if name_lower in s["name"].lower() or name_lower in s.get("name_arabic", "").lower():
            return s
    return None


def search_surah(query: str) -> Optional[dict]:
    """Search by number or name."""
    if query.isdigit():
        return get_surah_by_number(int(query))
    return get_surah_by_name(query)


def get_surahs_in_juz(juz_number: int) -> list:
    """Returns list of surah dicts for a given juz."""
    juz_data = load_juz_map().get(str(juz_number), {})
    surah_numbers = juz_data.get("surahs", [])
    surahs = load_surahs()
    return [s for s in surahs if s["number"] in surah_numbers]


def get_juz_for_surah(surah_number: int) -> list:
    """Returns juz numbers that contain this surah."""
    surah = get_surah_by_number(surah_number)
    return surah["juz"] if surah else []


def get_next_surah_in_juz(juz_number: int, current_surah: int, direction: str = "forward") -> Optional[dict]:
    surahs = get_surahs_in_juz(juz_number)
    if direction == "backward":
        surahs = list(reversed(surahs))
    found = False
    for s in surahs:
        if found:
            return s
        if s["number"] == current_surah:
            found = True
    return None


def sanitize_text(text: str) -> str:
    """Remove HTML tags and limit length."""
    text = re.sub(r"<[^>]+>", "", text)
    return text[:4096]


def generate_referral_code(telegram_id: int) -> str:
    import hashlib
    return hashlib.md5(str(telegram_id).encode()).hexdigest()[:8].upper()


def format_large_number(n: int) -> str:
    return f"{n:,}"


def time_until_midnight() -> int:
    """Returns seconds until next midnight (Asia/Tashkent)."""
    import pytz
    from datetime import datetime, timedelta
    TZ = pytz.timezone("Asia/Tashkent")
    now = datetime.now(TZ)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((midnight - now).total_seconds())


def truncate(text: str, max_len: int = 30) -> str:
    return text[:max_len] + "..." if len(text) > max_len else text


def is_valid_telegram_id(text: str) -> bool:
    return text.lstrip("@").isdigit() or text.startswith("@")
