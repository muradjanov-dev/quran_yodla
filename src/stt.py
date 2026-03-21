"""Speech-to-Text via Groq Whisper.

verify_voice(ogg_bytes, expected_arabic) -> (passed: bool, transcript: str)

Falls back to trust-based (True, '') if GROQ_API_KEY is not set or API fails.
"""
import os
import io
import unicodedata

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

def _arabic_chars(text: str) -> set[str]:
    """Return set of Arabic Unicode characters in text (ignore diacritics)."""
    return {c for c in text if unicodedata.category(c) in ("Lo", "Ll", "Lu") and ord(c) > 0x600}

def _similarity(a: str, b: str) -> float:
    """Character overlap ratio between two strings (Arabic-aware)."""
    sa = _arabic_chars(a)
    sb = _arabic_chars(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    overlap = len(sa & sb)
    return overlap / max(len(sa), len(sb))

async def verify_voice(ogg_bytes: bytes, expected_arabic: str, threshold: float = 0.35) -> tuple[bool, str]:
    """
    Transcribe voice message using Groq Whisper and check against expected Arabic text.

    Returns:
        (True, transcript) if passed
        (False, transcript) if failed
        (True, '') if no API key or error (trust-based fallback)
    """
    if not GROQ_API_KEY:
        return True, ""

    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=GROQ_API_KEY)

        audio_file = io.BytesIO(ogg_bytes)
        audio_file.name = "voice.ogg"

        transcription = await client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=audio_file,
            language="ar",
            response_format="text",
        )
        transcript = str(transcription).strip()
        score = _similarity(transcript, expected_arabic)
        passed = score >= threshold
        print(f"[STT] Score={score:.2f} (threshold={threshold}) | transcript[:40]={transcript[:40]!r}")
        return passed, transcript

    except Exception as e:
        print(f"[STT] Groq error, falling back to trust-based: {e}")
        return True, ""
