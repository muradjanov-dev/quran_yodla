"""Tajweed checking feature — admin only for now.

Flow:
1. User sends /tajweed or taps Tajweed menu button
2. If admin: bot asks to send a voice message and specifies which ayah to recite
3. User sends voice → bot transcribes with Groq Whisper (Arabic)
4. Bot fetches the ayah's tajweed-annotated text from alquran.cloud
5. Compares transcript word-by-word against expected text
6. Overlays tajweed rule violations at each misread position
7. Returns detailed feedback report

Non-admin users see "Tez orada" (Coming soon).
"""
import re
import io
import unicodedata
import urllib.request
import json
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
)

from src.database import db
from src.i18n import t

ADMIN_ID = db.ADMIN_ID
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ── Tajweed rule tag → human-readable name ────────────────────────────────────
RULE_NAMES_UZ = {
    "h:1": "Hamza Wasl",
    "h:2": "Hamza Wasl (lam-ta'rif)",
    "h:3": "Hamza Wasl (surah boshi)",
    "h:4": "Hamza Wasl (fe'l)",
    "h:5": "Hamza Wasl",
    "h:6": "Hamza Wasl",
    "h:7": "Hamza Wasl",
    "h:8": "Hamza Wasl",
    "h:9": "Hamza Wasl",
    "h:10": "Hamza Wasl",
    "h:11": "Hamza Wasl",
    "h:13": "Hamza Wasl",
    "h:14": "Hamza Wasl",
    "h:20": "Hamza Wasl",
    "h:9999": "Hamza Wasl",
    "l": "Lam Shamsiyya (quyosh lami)",
    "n": "Madd — cho'zish",
    "p": "Madd Lozim — uzun cho'zish",
    "m": "Madd — cho'zish",
    "g": "Gunnah (shovqin)",
    "s": "Saktah — to'xtash",
    "o": "Waqf — to'xtash belgisi",
    "f:16": "Ikhfa — yashirish",
    "f:17": "Ikhfa Shafawi",
    "f:18": "Ikhfa",
    "q:15": "Idgham — qo'shib o'qish",
    "q:19": "Idgham Shafawi",
    "u:12": "Iqlab — almashtirish",
    "u:22": "Iqlab",
    "a:21": "Izhaar — aniq talaffuz",
}

RULE_NAMES_EN = {
    "h:1": "Hamza Wasl",
    "h:2": "Hamza Wasl (lam al-ta'rif)",
    "h:3": "Hamza Wasl (surah start)",
    "h:4": "Hamza Wasl (verb)",
    "h:5": "Hamza Wasl", "h:6": "Hamza Wasl", "h:7": "Hamza Wasl",
    "h:8": "Hamza Wasl", "h:9": "Hamza Wasl", "h:10": "Hamza Wasl",
    "h:11": "Hamza Wasl", "h:13": "Hamza Wasl", "h:14": "Hamza Wasl",
    "h:20": "Hamza Wasl", "h:9999": "Hamza Wasl",
    "l": "Lam Shamsiyya (solar lam)",
    "n": "Madd — elongation",
    "p": "Madd Lazim — long elongation",
    "m": "Madd — elongation",
    "g": "Ghunnah (nasalization)",
    "s": "Saktah — brief pause",
    "o": "Waqf — stopping mark",
    "f:16": "Ikhfa — concealment",
    "f:17": "Ikhfa Shafawi",
    "f:18": "Ikhfa",
    "q:15": "Idgham — merging",
    "q:19": "Idgham Shafawi",
    "u:12": "Iqlab — substitution",
    "u:22": "Iqlab",
    "a:21": "Izhaar — clear pronunciation",
}

# ── Tajweed text parser ───────────────────────────────────────────────────────

def parse_tajweed_text(raw: str) -> list[tuple[str, str]]:
    """Parse alquran.cloud tajweed-tagged text into [(rule, arabic_text), ...]."""
    segments = []
    i = 0
    buf = ""
    while i < len(raw):
        m = re.match(r'\[([^\[\]]{1,15})\[', raw[i:])
        if m:
            if buf.strip():
                segments.append(("none", buf))
            buf = ""
            rule = m.group(1)
            i += len(m.group(0))
            end = raw.find("]", i)
            if end == -1:
                break
            content = raw[i:end]
            if content.strip():
                segments.append((rule, content))
            i = end + 1
        else:
            buf += raw[i]
            i += 1
    if buf.strip():
        segments.append(("none", buf))
    return segments


def strip_diacritics(text: str) -> str:
    """Remove Arabic diacritics (harakat) for comparison."""
    # Arabic diacritic range: U+0610–U+061A, U+064B–U+065F, U+0670
    return re.sub(r'[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06dc\u06df-\u06e4\u06e7\u06e8\u06ea-\u06ed]', '', text)


def get_clean_text(segments: list[tuple[str, str]]) -> str:
    """Build clean Arabic text from segments (no tags)."""
    return "".join(txt for _, txt in segments)


async def fetch_tajweed_ayah(surah: int, ayah: int) -> tuple[str, list[tuple[str, str]]] | tuple[None, None]:
    """Fetch tajweed-annotated ayah. Returns (clean_text, segments)."""
    import asyncio
    url = f"https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/quran-tajweed"
    try:
        loop = asyncio.get_event_loop()
        def _fetch():
            with urllib.request.urlopen(url, timeout=8) as r:
                return json.loads(r.read().decode("utf-8"))
        data = await loop.run_in_executor(None, _fetch)
        raw = data["data"]["text"]
        segments = parse_tajweed_text(raw)
        clean = get_clean_text(segments)
        return clean, segments
    except Exception as e:
        print(f"[Tajweed] fetch failed: {e}")
        return None, None


# ── Transcript comparison ─────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Strip diacritics and normalize for comparison."""
    t = strip_diacritics(text)
    # Normalize alef variants → alef
    t = re.sub(r'[\u0622\u0623\u0625\u0671]', '\u0627', t)
    return t.strip()


def compare_words(transcript: str, expected_clean: str) -> list[dict]:
    """
    Word-level comparison. Returns list of:
      {"word_expected": str, "word_got": str | None, "ok": bool, "index": int}
    """
    exp_words = _normalize(expected_clean).split()
    got_words = _normalize(transcript).split()
    results = []
    for i, exp in enumerate(exp_words):
        got = got_words[i] if i < len(got_words) else None
        ok = got is not None and (exp == got or exp in got or got in exp)
        results.append({"word_expected": exp, "word_got": got, "ok": ok, "index": i})
    return results


def find_tajweed_violations(word_results: list[dict], segments: list[tuple[str, str]]) -> list[str]:
    """
    For each incorrectly read word, check if it overlaps with a tajweed rule segment.
    Returns list of violated rule names.
    """
    violated = []
    # Build a positional map: char_position -> rule
    clean_full = get_clean_text(segments)
    clean_norm = _normalize(clean_full)
    words_in_clean = clean_norm.split()

    for wr in word_results:
        if wr["ok"]:
            continue
        idx = wr["index"]
        if idx >= len(words_in_clean):
            continue
        # Find which segment this word falls in by scanning segments
        pos = 0
        for rule, seg_text in segments:
            seg_norm = _normalize(seg_text)
            seg_words = seg_norm.split()
            if rule != "none" and any(w == words_in_clean[idx] for w in seg_words if w):
                violated.append(rule)
                break
    return list(dict.fromkeys(violated))  # deduplicate, preserve order


# ── Groq transcription ────────────────────────────────────────────────────────

async def transcribe_arabic(ogg_bytes: bytes) -> str | None:
    if not GROQ_API_KEY:
        return None
    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=GROQ_API_KEY)
        audio_file = io.BytesIO(ogg_bytes)
        audio_file.name = "voice.ogg"
        result = await client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=audio_file,
            language="ar",
            response_format="text",
        )
        return str(result).strip()
    except Exception as e:
        print(f"[Tajweed] transcription error: {e}")
        return None


# ── Report builder ────────────────────────────────────────────────────────────

def build_report(word_results: list[dict], violated_rules: list[str],
                 lang: str, surah: int, ayah: int, transcript: str) -> str:
    total = len(word_results)
    correct = sum(1 for w in word_results if w["ok"])
    accuracy = int(correct / total * 100) if total else 0
    rule_map = RULE_NAMES_UZ if lang == "uz" else RULE_NAMES_EN

    wrong_words = [w["word_expected"] for w in word_results if not w["ok"]]
    rule_names = [rule_map.get(r, r) for r in violated_rules]

    if lang == "uz":
        lines = [
            f"🎙 *Tajvid Tekshiruvi — {surah}:{ayah}*",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"",
            f"📊 *Natija:* {correct}/{total} so'z to'g'ri ({accuracy}%)",
            f"",
        ]
        if not wrong_words:
            lines.append("✅ *Ajoyib! Barcha so'zlar to'g'ri talaffuz qilindi.*")
        else:
            lines.append(f"❌ *Noto'g'ri so'zlar:* {', '.join(wrong_words[:8])}")
            if rule_names:
                lines.append(f"")
                lines.append(f"⚠️ *Tajvid qoidalari e'tibor talab qiladi:*")
                for rn in rule_names[:5]:
                    lines.append(f"  • {rn}")
        lines += ["", f"_Siz o'qigandek:_ _{transcript[:80] if transcript else '—'}_"]
    else:
        lines = [
            f"🎙 *Tajweed Check — {surah}:{ayah}*",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"",
            f"📊 *Result:* {correct}/{total} words correct ({accuracy}%)",
            f"",
        ]
        if not wrong_words:
            lines.append("✅ *Excellent! All words recited correctly.*")
        else:
            lines.append(f"❌ *Incorrect words:* {', '.join(wrong_words[:8])}")
            if rule_names:
                lines.append(f"")
                lines.append(f"⚠️ *Tajweed rules needing attention:*")
                for rn in rule_names[:5]:
                    lines.append(f"  • {rn}")
        lines += ["", f"_You recited:_ _{transcript[:80] if transcript else '—'}_"]

    return "\n".join(lines)


# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_tajweed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = _lang(user.id)
    if user.id != ADMIN_ID:
        text = "🔜 *Tez orada!*\n\n_Bu xususiyat hozirda sinovdan o'tkazilmoqda._" if lang == "uz" \
            else "🔜 *Coming Soon!*\n\n_This feature is currently being tested._"
        await update.message.reply_text(text, parse_mode="Markdown")
        return
    await _show_tajweed_menu(update.message, user.id)


async def cb_tajweed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    lang = _lang(user.id)

    if user.id != ADMIN_ID:
        text = "🔜 *Tez orada!*\n\n_Bu xususiyat hozirda sinovdan o'tkazilmoqda._" if lang == "uz" \
            else "🔜 *Coming Soon!*\n\n_This feature is currently being tested._"
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup([[
                                          InlineKeyboardButton(t(user.id, "btn_main_menu"),
                                                               callback_data="menu:home")
                                      ]]))
        return

    parts = query.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "menu":
        await _show_tajweed_menu(query, user.id)

    elif action == "pick_surah":
        # Store that we're expecting surah:ayah input
        db.update_settings(user.id, awaiting_input="tajweed:surah_ayah")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor qilish" if lang == "uz" else "❌ Cancel",
                                                          callback_data="tajweed:cancel")]])
        text = (
            "📖 Qaysi oyatni tekshirmoqchisiz?\n\n"
            "_Sura va oyat raqamini yozing, masalan:_ `1:1` _(Al-Fotiha, 1-oyat)_"
            if lang == "uz" else
            "📖 Which Ayah do you want to check?\n\n"
            "_Enter surah:ayah, e.g._ `1:1` _(Al-Fatiha, Ayah 1)_"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    elif action == "cancel":
        db.update_settings(user.id, awaiting_input=None)
        await _show_tajweed_menu(query, user.id)


async def handle_tajweed_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice message during tajweed session."""
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    settings = db.get_settings(user.id)
    awaiting = settings["awaiting_input"] if settings else None
    if not awaiting or not awaiting.startswith("tajweed:voice:"):
        return

    # Parse stored surah:ayah
    try:
        _, _, surah_str, ayah_str = awaiting.split(":")
        surah, ayah = int(surah_str), int(ayah_str)
    except Exception:
        await update.message.reply_text("⚠️ Session xatolik. /tajweed bilan qayta boshlang.")
        db.update_settings(user.id, awaiting_input=None)
        return

    lang = _lang(user.id)
    processing_text = "⏳ *Ovoz tahlil qilinmoqda...*" if lang == "uz" else "⏳ *Analyzing audio...*"
    msg = await update.message.reply_text(processing_text, parse_mode="Markdown")

    # Download voice
    try:
        voice_file = await update.message.voice.get_file()
        ogg_bytes = bytes(await voice_file.download_as_bytearray())
    except Exception as e:
        await msg.edit_text(f"⚠️ Ovoz yuklab bo'lmadi: {e}")
        return

    # Transcribe
    transcript = await transcribe_arabic(ogg_bytes)
    if transcript is None:
        no_key = (
            "⚠️ *GROQ_API_KEY sozlanmagan.*\n_Tajvid tekshiruvi ishlamaydi._"
            if lang == "uz" else
            "⚠️ *GROQ_API_KEY not configured.*\n_Tajweed checking unavailable._"
        )
        await msg.edit_text(no_key, parse_mode="Markdown")
        return

    # Fetch tajweed-annotated ayah
    clean_text, segments = await fetch_tajweed_ayah(surah, ayah)
    if clean_text is None:
        await msg.edit_text("⚠️ Oyat ma'lumotlari yuklab bo'lmadi." if lang == "uz"
                             else "⚠️ Could not fetch ayah data.")
        return

    # Compare and analyze
    word_results = compare_words(transcript, clean_text)
    violated_rules = find_tajweed_violations(word_results, segments)
    report = build_report(word_results, violated_rules, lang, surah, ayah, transcript)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Yana tekshirish" if lang == "uz" else "🔄 Check Again",
                              callback_data=f"tajweed:recheck:{surah}:{ayah}")],
        [InlineKeyboardButton("📖 Boshqa oyat" if lang == "uz" else "📖 Different Ayah",
                              callback_data="tajweed:pick_surah")],
        [InlineKeyboardButton(t(user.id, "btn_main_menu"), callback_data="menu:home")],
    ])

    await msg.edit_text(report, parse_mode="Markdown", reply_markup=kb)
    db.update_settings(user.id, awaiting_input=None)


async def handle_tajweed_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Called from the settings text handler to intercept tajweed surah:ayah input.
    Returns True if consumed, False otherwise.
    """
    user = update.effective_user
    settings = db.get_settings(user.id)
    awaiting = settings["awaiting_input"] if settings else None
    if awaiting != "tajweed:surah_ayah":
        return False

    text = update.message.text.strip()
    lang = _lang(user.id)

    m = re.match(r'^(\d+)[:\-\s](\d+)$', text)
    if not m:
        await update.message.reply_text(
            "⚠️ Format noto'g'ri. Masalan: `1:1`" if lang == "uz"
            else "⚠️ Invalid format. Example: `1:1`",
            parse_mode="Markdown"
        )
        return True

    surah, ayah = int(m.group(1)), int(m.group(2))
    if surah < 1 or surah > 114 or ayah < 1:
        await update.message.reply_text(
            "⚠️ Sura 1-114, oyat 1 dan katta bo'lishi kerak." if lang == "uz"
            else "⚠️ Surah must be 1–114, ayah ≥ 1."
        )
        return True

    # Fetch to validate ayah exists
    clean_text, segments = await fetch_tajweed_ayah(surah, ayah)
    if clean_text is None:
        await update.message.reply_text(
            "⚠️ Bu oyat topilmadi. Iltimos qayta kiriting." if lang == "uz"
            else "⚠️ Ayah not found. Please try again."
        )
        return True

    # Store session and prompt for voice
    db.update_settings(user.id, awaiting_input=f"tajweed:voice:{surah}:{ayah}")

    # Show the ayah text to recite
    if lang == "uz":
        prompt = (
            f"📖 *{surah}:{ayah}*\n\n"
            f"`{strip_diacritics(clean_text)}`\n\n"
            f"Yuqoridagi oyatni yod o'qib, *ovoz xabar* yuboring. 🎤"
        )
    else:
        prompt = (
            f"📖 *{surah}:{ayah}*\n\n"
            f"`{strip_diacritics(clean_text)}`\n\n"
            f"Recite the above Ayah from memory and send a *voice message*. 🎤"
        )

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Bekor qilish" if lang == "uz" else "❌ Cancel",
                             callback_data="tajweed:cancel")
    ]])
    await update.message.reply_text(prompt, parse_mode="Markdown", reply_markup=kb)
    return True


async def cb_tajweed_recheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Re-set voice session for same ayah."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if user.id != ADMIN_ID:
        return
    parts = query.data.split(":")
    surah, ayah = int(parts[2]), int(parts[3])
    lang = _lang(user.id)
    db.update_settings(user.id, awaiting_input=f"tajweed:voice:{surah}:{ayah}")
    text = (
        f"🎤 *{surah}:{ayah}* — Ovoz xabar yuboring." if lang == "uz"
        else f"🎤 *{surah}:{ayah}* — Send your voice message."
    )
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup([[
                                      InlineKeyboardButton("❌ Bekor" if lang == "uz" else "❌ Cancel",
                                                           callback_data="tajweed:cancel")
                                  ]]))


async def _show_tajweed_menu(target, user_id: int):
    lang = _lang(user_id)
    if lang == "uz":
        text = (
            "🎙 *Tajvid Tekshiruvi*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Qur'on tilavatingizdagi tajvid xatolarini aniqlang.\n\n"
            "📌 *Qanday ishlaydi:*\n"
            "1. Tekshirmoqchi bo'lgan oyatni tanlang\n"
            "2. Ovozli xabar yuboring\n"
            "3. Bot har bir so'zni tekshirib, qaysi tajvid qoidasi buzilganini aytadi\n\n"
            "_⚠️ Admin rejimi — hozircha faqat admin foydalanishi mumkin_"
        )
    else:
        text = (
            "🎙 *Tajweed Checker*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Detect tajweed errors in your Quran recitation.\n\n"
            "📌 *How it works:*\n"
            "1. Choose the Ayah you want to check\n"
            "2. Send a voice message reciting it\n"
            "3. The bot analyzes each word and reports which tajweed rule was violated\n\n"
            "_⚠️ Admin mode — currently available for admin only_"
        )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Oyat tanlash" if lang == "uz" else "📖 Select Ayah",
                              callback_data="tajweed:pick_surah")],
        [InlineKeyboardButton(t(user_id, "btn_main_menu"), callback_data="menu:home")],
    ])
    try:
        if hasattr(target, "edit_message_text"):
            await target.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
        else:
            await target.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    except Exception:
        try:
            await target.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            pass


def _lang(user_id: int) -> str:
    u = db.get_user(user_id)
    return dict(u).get("language", "en") if u else "en"


def register(app):
    app.add_handler(CommandHandler("tajweed", cmd_tajweed))
    app.add_handler(CallbackQueryHandler(cb_tajweed, pattern=r"^tajweed:(menu|pick_surah|cancel)$"))
    app.add_handler(CallbackQueryHandler(cb_tajweed_recheck, pattern=r"^tajweed:recheck:"))
    # Voice handler for tajweed session (high priority — before flow's voice handler)
    app.add_handler(MessageHandler(filters.VOICE, handle_tajweed_voice), group=1)
