"""Flow Learning — Unified Oqim Rejimi.

UNIFIED WORKFLOW:
  User picks Surah ONCE → saved as active_surah → Surah Dashboard appears.
  Both [🔥 Oqim] and [📝 Test] operate on that same surah.

3-7-11 STATE MACHINE (strict):
  READ_3 → READ_7 → READ_11 → VOICE_EXAM → COMBINE_5 → READ_3 (next ayah)

AUDIO: EveryAyah direct CDN (zero API limits, all reciters).
STT:   Groq Whisper via src/stt.py (trust-based fallback if no key).
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from src.database import db
from src.api import quran
from src.api.quran import RECITERS, AYAH_COUNTS, get_everyayah_url
from src import stt
from src.i18n import t

SURAHS_PER_PAGE = 36
HOME_CB = "menu:home"

# ── Helpers ──────────────────────────────────────────────────────────────────

def _home_btn(uid: int) -> InlineKeyboardButton:
    return InlineKeyboardButton(t(uid, "btn_main_menu"), callback_data=HOME_CB)

def _S(row) -> dict:
    return dict(row) if row else {}

def _lang(user_id: int) -> str:
    return _S(db.get_user(user_id)).get("language", "en")

def _reciter(user_id: int) -> str:
    return _S(db.get_settings(user_id)).get("preferred_reciter") or "ar.alafasy"

async def _edit_or_reply(target, text: str, kb: InlineKeyboardMarkup):
    try:
        await target.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    except Exception:
        try:
            await target.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            try:
                await target.reply_text(text, parse_mode="Markdown", reply_markup=kb)
            except Exception as e:
                print(f"[Flow] _edit_or_reply failed: {e}")

def _make_bar(done: int, total: int, length: int = 8) -> str:
    filled = round(done / total * length) if total else 0
    return "🟩" * filled + "⬜" * (length - filled)

# ── Surah Dashboard ──────────────────────────────────────────────────────────

async def _show_surah_dashboard(target, user_id: int):
    """The unified hub: Flow + Quiz both on the same active surah."""
    surah = db.get_active_surah(user_id)
    lang  = _lang(user_id)

    surah_info  = await quran.get_surah_info(surah)
    surah_name  = surah_info["englishName"] if surah_info else f"Surah {surah}"
    total_ayahs = surah_info["numberOfAyahs"] if surah_info else 1
    done        = db.count_memorized_in_surah(user_id, surah)
    bar         = _make_bar(done, total_ayahs)
    pct         = int(done / total_ayahs * 100) if total_ayahs else 0

    game   = _S(db.get_gamification(user_id))
    streak = game.get("current_streak", 0)
    xp     = game.get("total_xp", 0)

    if lang == "uz":
        text = (
            f"📖 *{surah_name}* ({surah}-sura)\n"
            f"{bar} {pct}% yodlandi — {done}/{total_ayahs} oyat\n"
            f"🔥 {streak} kunlik seriya  ⭐ {xp} XP"
        )
        rows = [
            [InlineKeyboardButton("🔥 3-7-11 Oqimni Boshlash", callback_data="flow:start_flow")],
            [InlineKeyboardButton("📝 Shu Suradan Test",       callback_data="flow:start_quiz")],
            [InlineKeyboardButton("📊 Statistika",              callback_data="menu:profile")],
            [InlineKeyboardButton("🔄 Sura O'zgartirish",      callback_data="flow:change_surah")],
            [_home_btn(user_id)],
        ]
    else:
        text = (
            f"📖 *{surah_name}* (Surah {surah})\n"
            f"{bar} {pct}% memorized — {done}/{total_ayahs} Ayahs\n"
            f"🔥 {streak} day streak  ⭐ {xp} XP"
        )
        rows = [
            [InlineKeyboardButton("🔥 Start 3-7-11 Flow",      callback_data="flow:start_flow")],
            [InlineKeyboardButton("📝 Quiz From This Surah",    callback_data="flow:start_quiz")],
            [InlineKeyboardButton("📊 Statistics",              callback_data="menu:profile")],
            [InlineKeyboardButton("🔄 Change Surah",           callback_data="flow:change_surah")],
            [_home_btn(user_id)],
        ]
    await _edit_or_reply(target, text, InlineKeyboardMarkup(rows))

# ── Surah Picker ─────────────────────────────────────────────────────────────

async def _show_surah_picker(target, user_id: int, page: int = 0):
    surahs  = await quran.get_surah_list()
    total   = len(surahs)
    start   = page * SURAHS_PER_PAGE
    end     = min(start + SURAHS_PER_PAGE, total)
    chunk   = surahs[start:end]

    rows = []
    row  = []
    for i, s in enumerate(chunk):
        row.append(InlineKeyboardButton(
            f"{s['number']}.{s['englishName'][:9]}",
            callback_data=f"flow:pick:{s['number']}"
        ))
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Prev", callback_data=f"flow:spage:{page - 1}"))
    if end < total:
        nav.append(InlineKeyboardButton("Next ▶", callback_data=f"flow:spage:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([_home_btn(user_id)])

    lang = _lang(user_id)
    hdr  = f"{'🕌 Sura Tanlash' if lang == 'uz' else '🕌 Select Surah'} ({start+1}–{end}/{total})"
    await _edit_or_reply(target, f"*{hdr}*", InlineKeyboardMarkup(rows))

# ── Reciter Picker ────────────────────────────────────────────────────────────

async def _show_reciter_picker(target, user_id: int, pending_surah: int):
    lang = _lang(user_id)
    rows = []
    for name_en, name_uz, edition in RECITERS:
        label = name_uz if lang == "uz" else name_en
        rows.append([InlineKeyboardButton(f"🎙 {label}", callback_data=f"flow:reciter:{edition}:{pending_surah}")])
    rows.append([_home_btn(user_id)])
    text = (
        "🎙 *Qori tanlang:*\n\nOqim rejimida oyatlar shu qori ovozida yuboriladi."
        if lang == "uz" else
        "🎙 *Choose your reciter:*\n\nAudio will be sent with this reciter's voice."
    )
    await _edit_or_reply(target, text, InlineKeyboardMarkup(rows))

# ── Audio sender (EveryAyah CDN) ──────────────────────────────────────────────

async def _send_audio(bot, chat_id: int, surah: int, ayah: int, edition: str):
    """Send audio from EveryAyah.com — zero API, all reciters work."""
    url = get_everyayah_url(surah, ayah, edition)
    surah_info = await quran.get_surah_info(surah)
    name = surah_info["englishName"] if surah_info else f"Surah {surah}"
    try:
        await bot.send_audio(
            chat_id=chat_id,
            audio=url,
            title=f"{name} — Ayah {ayah}",
            performer="Hifz Bot 🕌",
        )
    except Exception as e:
        print(f"[Flow] Audio error {surah}:{ayah} {edition}: {e}")
        await bot.send_message(chat_id=chat_id, text=f"🔊 [Audio]({url})", parse_mode="Markdown")

# ── XP table & state transitions ──────────────────────────────────────────────
XP   = {"READ_3": 5, "READ_7": 10, "READ_11": 15, "VOICE_EXAM": 25, "COMBINE_5": 20}
NEXT = {"READ_3": "READ_7", "READ_7": "READ_11", "READ_11": "VOICE_EXAM"}
# VOICE_EXAM → COMBINE_5 (handled by voice handler)
# COMBINE_5  → READ_3 of next ayah (handled by _advance)

# ── State renderer ────────────────────────────────────────────────────────────

async def _render_state(target, user_id: int, session: dict, bot=None):
    state  = session.get("state", "READ_3")
    surah  = session.get("surah_number", 1)
    ayah   = session.get("current_ayah", 1)
    lang   = _lang(user_id)
    edition = _reciter(user_id)

    ayah_full  = await quran.get_ayah_full(surah, ayah, edition)
    surah_info = await quran.get_surah_info(surah)
    surah_name = surah_info["englishName"] if surah_info else f"Surah {surah}"
    arabic     = ayah_full.get("arabic", "—")
    translation = ayah_full.get("translation", "—")

    if state == "READ_3":
        text = (
            f"🎧 *{surah_name} — {ayah}-oyat*\n\n"
            f"{arabic}\n\n"
            f"🔤 *Tarjima:* _{translation}_\n\n"
            "📖 Qori ovozini eshiting, so'ng 3 marta ovoz chiqarib o'qing."
            if lang == "uz" else
            f"🎧 *{surah_name} — Ayah {ayah}*\n\n"
            f"{arabic}\n\n"
            f"🔤 *Translation:* _{translation}_\n\n"
            "📖 Listen to the reciter, then read aloud 3 times."
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🗣 3 marta o'qidim" if lang == "uz" else "🗣 Read 3 times",
                callback_data="flow:confirm:READ_3")], [_home_btn(user_id)]])
        # Send audio first (Bismillah 🕌)
        if bot:
            await _send_audio(bot, user_id, surah, ayah, edition)

    elif state == "READ_7":
        text = (
            f"📖 *{surah_name} — {ayah}-oyat*\n\n"
            f"{arabic}\n\n"
            f"🔤 *Tarjima:* _{translation}_\n\n"
            "Yaxshi! Endi tarjima bilan birga 7 marta o'qing (+10 XP)."
            if lang == "uz" else
            f"📖 *{surah_name} — Ayah {ayah}*\n\n"
            f"{arabic}\n\n"
            f"🔤 *Translation:* _{translation}_\n\n"
            "Great! Now read 7 times while understanding the meaning (+10 XP)."
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🗣 7 marta o'qidim" if lang == "uz" else "🗣 Read 7 times",
                callback_data="flow:confirm:READ_7")], [_home_btn(user_id)]])

    elif state == "READ_11":
        text = (
            f"🧠 *{surah_name} — {ayah}-oyat*\n\n"
            f"{arabic}\n\n"
            "Ko'zingizni yuming va 11 marta yoddan aytib ko'ring (+15 XP)."
            if lang == "uz" else
            f"🧠 *{surah_name} — Ayah {ayah}*\n\n"
            f"{arabic}\n\n"
            "Close your eyes — recite from memory 11 times (+15 XP)."
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🗣 11 marta o'qidim" if lang == "uz" else "🗣 Recited 11 times",
                callback_data="flow:confirm:READ_11")], [_home_btn(user_id)]])

    elif state == "VOICE_EXAM":
        text = (
            f"🎤 *{surah_name} — {ayah}-oyat*\n\n"
            "Endi shu oyatni yoddan aytib, *ovozli xabar (voice)* yuboring!\n\n"
            "_Bot sizning tilavatni tekshiradi._"
            if lang == "uz" else
            f"🎤 *{surah_name} — Ayah {ayah}*\n\n"
            "Now recite this Ayah from memory — *send a voice message!*\n\n"
            "_The bot will verify your recitation._"
        )
        kb = InlineKeyboardMarkup([[_home_btn(user_id)]])

    elif state == "COMBINE_5":
        start_ayah = session.get("start_ayah", max(ayah - 1, 1))
        # Build stacked Arabic text from start_ayah to current_ayah
        stacked = ""
        for n in range(start_ayah, ayah + 1):
            ad = await quran.get_ayah(surah, n)
            stacked += f"_{n}._ {ad['text'] if ad else '—'}\n\n"
        text = (
            f"🔗 *{surah_name}: {start_ayah}–{ayah}-oyatlarni birlashtiring*\n\n"
            f"{stacked}"
            f"Mashallah! Endi {start_ayah}—{ayah}-oyatlarni jamlab 5 marta o'qing. (+20 XP)"
            if lang == "uz" else
            f"🔗 *{surah_name}: Combine Ayahs {start_ayah}–{ayah}*\n\n"
            f"{stacked}"
            f"Masha'Allah! Now read Ayahs {start_ayah}–{ayah} together 5 times. (+20 XP)"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🔗 Jamlab 5 marta o'qidim" if lang == "uz" else "🔗 Combined reading ×5",
                callback_data="flow:confirm:COMBINE_5")], [_home_btn(user_id)]])

    else:
        text = "⚠️ State error — restart flow."
        kb   = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Restart" if _lang(user_id) == "en" else "🔄 Qayta boshlash",
                                 callback_data="flow:change_surah"),
            _home_btn(user_id)]])

    await _edit_or_reply(target, text, kb)

# ── Advance state machine ─────────────────────────────────────────────────────

async def _advance(target, user_id: int, confirmed: str, bot=None):
    xp = XP.get(confirmed, 0)
    if xp:
        db.add_xp(user_id, xp)
        db.update_streak(user_id)

    session  = _S(db.get_learning_session(user_id))
    surah    = session.get("surah_number", 1)
    ayah     = session.get("current_ayah", 1)
    start_ayah = session.get("start_ayah", ayah)
    cycle    = session.get("ayah_in_cycle", 0)
    lang     = _lang(user_id)

    if confirmed == "READ_11":
        db.log_interaction(user_id, surah, ayah, 'flow_memorized')

    next_state = NEXT.get(confirmed)

    if confirmed == "COMBINE_5":
        # Advance to next ayah
        ayah_count = AYAH_COUNTS[surah - 1] if 1 <= surah <= 114 else 1
        db.mark_ayah(user_id, surah, ayah, memorized=True)
        db.increment_flow_daily(user_id)
        db.add_weekly_xp(user_id, xp)
        # Check achievements after memorizing
        if bot:
            from src.handlers.achievements import check_and_award
            import asyncio
            asyncio.ensure_future(check_and_award(user_id, bot))
        next_ayah  = ayah + 1

        if next_ayah > ayah_count:
            # Surah complete!
            db.update_learning_session(user_id, active=0)
            db.unlock_badge(user_id, "page_turner")
            info = await quran.get_surah_info(surah)
            name = info["englishName"] if info else f"Surah {surah}"
            gm   = _S(db.get_gamification(user_id))
            done_msg = (
                f"🎉 *Mashallah! {name} surasi yakunlandi!*\n"
                f"✅ Barcha oyatlar yod olindi. 💫 Jami: {gm.get('total_xp', 0)} XP"
                if lang == "uz" else
                f"🎉 *Masha'Allah! Surah {name} complete!*\n"
                f"✅ All Ayahs memorized. 💫 Total: {gm.get('total_xp', 0)} XP"
            )
            await _edit_or_reply(target, done_msg, InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Sura O'zgartirish" if lang == "uz" else "🔄 Change Surah",
                                     callback_data="flow:change_surah"),
                _home_btn(user_id)]]))
            return

        new_cycle = cycle + 1
        new_start = next_ayah  # each new ayah starts its own combine range
        db.update_learning_session(user_id,
                                   current_ayah=next_ayah,
                                   start_ayah=new_start,
                                   ayah_in_cycle=new_cycle,
                                   state="READ_3")
    else:
        db.update_learning_session(user_id, state=next_state)

    session = _S(db.get_learning_session(user_id))
    await _render_state(target, user_id, session, bot=bot)

# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not db.get_user(user.id):
        await update.message.reply_text(t(user.id, "please_start"))
        return
    # Go straight to dashboard (works as entry for both menu:learn and menu:flow)
    await _show_surah_dashboard(update.message, user.id)

async def cb_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    user   = query.from_user
    parts  = query.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "dashboard":
        await _show_surah_dashboard(query, user.id)

    elif action == "change_surah":
        await _show_surah_picker(query, user.id, page=0)

    elif action == "spage" and len(parts) >= 3:
        await _show_surah_picker(query, user.id, page=int(parts[2]))

    elif action == "pick" and len(parts) >= 3:
        surah_num = int(parts[2])
        db.set_active_surah(user.id, surah_num)
        # If reciter already chosen, go straight to dashboard
        reciter = _S(db.get_settings(user.id)).get("preferred_reciter")
        if reciter:
            await _show_surah_dashboard(query, user.id)
        else:
            await _show_reciter_picker(query, user.id, pending_surah=surah_num)

    elif action == "reciter" and len(parts) >= 3:
        # format: flow:reciter:{edition}:{surah}  OR old: flow:reciter:{edition}
        # Use rsplit so extra colons in edition don't break parsing
        raw       = query.data  # e.g. "flow:reciter:ar.alafasy:114"
        rest      = raw[len("flow:reciter:"):]   # "ar.alafasy:114"
        try:
            edition, surah_str = rest.rsplit(":", 1)
            surah_num = int(surah_str)
        except (ValueError, IndexError):
            # Fallback: old format had no surah — use current active_surah
            edition   = rest
            surah_num = db.get_active_surah(user.id) or 1
        db.update_settings(user.id, preferred_reciter=edition)
        db.set_active_surah(user.id, surah_num)
        await _show_surah_dashboard(query, user.id)

    elif action == "start_flow":
        surah = db.get_active_surah(user.id)
        reciter = _S(db.get_settings(user.id)).get("preferred_reciter")
        if not reciter:
            await _show_reciter_picker(query, user.id, pending_surah=surah)
            return
        # Check for active session on same surah
        sess = _S(db.get_learning_session(user.id))
        if sess.get("active") and sess.get("surah_number") == surah:
            await _render_state(query, user.id, sess, bot=context.bot)
        else:
            # Start fresh from first un-memorized ayah
            done = db.count_memorized_in_surah(user.id, surah)
            start = done + 1
            ayah_count = AYAH_COUNTS[surah - 1] if 1 <= surah <= 114 else 1
            if start > ayah_count:
                start = 1  # restart from top if all memorized
            db.init_learning_session(user.id, surah, start_ayah=start)
            db.update_learning_session(user.id, start_ayah=start)
            sess = _S(db.get_learning_session(user.id))
            await _render_state(query, user.id, sess, bot=context.bot)

    elif action == "start_quiz":
        # Delegate to quiz handler with active_surah filter
        surah = db.get_active_surah(user.id)
        db.init_quiz_session(user.id, mode="ayah_order", surah_filter=surah, total=10)
        from src.handlers.quiz import _send_next_question
        await _send_next_question(query, user.id)

    elif action == "confirm" and len(parts) >= 3:
        confirmed = parts[2]
        if confirmed == "READ_11":
            from src.handlers.limits import check_flow_limit
            if not await check_flow_limit(query, user.id):
                return
        await _advance(query, user.id, confirmed, bot=context.bot)

    elif action == "menu":
        await _show_surah_dashboard(query, user.id)

# ── Voice handler (VOICE_EXAM stage) ─────────────────────────────────────────

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    if not db.get_user(user.id):
        return
    session = _S(db.get_learning_session(user.id))
    if not session.get("active") or session.get("state") != "VOICE_EXAM":
        return

    surah = session.get("surah_number", 1)
    ayah  = session.get("current_ayah", 1)
    lang  = _lang(user.id)

    # Download voice OGG
    ogg_bytes = b""
    try:
        voice_file = await update.message.voice.get_file()
        ogg_bytes  = bytes(await voice_file.download_as_bytearray())
    except Exception as e:
        print(f"[Flow] Voice download error: {e}")

    # Groq STT verification (trust-based if no key)
    ayah_data = await quran.get_ayah_full(surah, ayah, _reciter(user.id))
    expected_arabic = ayah_data.get("arabic", "")
    passed, transcript = await stt.verify_voice(ogg_bytes, expected_arabic)

    if not passed:
        retry_text = (
            f"❌ *Tilavat to'g'ri kelmadi.* Yana urinib ko'ring!\n\n"
            f"_{expected_arabic[:80]}_"
            if lang == "uz" else
            f"❌ *Recitation didn't match.* Please try again!\n\n"
            f"_{expected_arabic[:80]}_"
        )
        await update.message.reply_text(retry_text, parse_mode="Markdown")
        return

    # Passed ✅
    db.add_xp(user.id, 25)
    db.update_streak(user.id)
    db.increment_flow_daily(user.id)
    db.log_interaction(user.id, surah, ayah, 'recitation')
    gm = _S(db.get_gamification(user.id))
    praise = (
        f"🌟 *Ajoyib! Tilavatingiz qabul qilindi!*\n+25 XP | Jami: {gm.get('total_xp', 0)} XP"
        if lang == "uz" else
        f"🌟 *Masha'Allah! Recitation accepted!*\n+25 XP | Total: {gm.get('total_xp', 0)} XP"
    )
    await update.message.reply_text(praise, parse_mode="Markdown")

    # Move to COMBINE_5
    start_ayah = session.get("start_ayah", ayah)
    db.update_learning_session(user.id, state="COMBINE_5")
    new_sess = _S(db.get_learning_session(user.id))
    await _render_state(update.message, user.id, new_sess, bot=context.bot)

# ── Review reminder callbacks ─────────────────────────────────────────────────

async def cb_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    lang = _lang(user.id)
    parts = query.data.split(":")  # review:start:{surah} or review:later:{surah}
    action = parts[1]
    surah = int(parts[2])

    if action == "later":
        text = (
            "⏰ *Yaxshi! Keyinroq eslataman.*\n\n"
            "_Takrorlash — hifzni mustahkamlashning asosi._"
            if lang == "uz" else
            "⏰ *Got it! I'll remind you later.*\n\n"
            "_Regular review is the foundation of strong Hifz._"
        )
        try:
            await query.edit_message_text(text, parse_mode="Markdown")
        except Exception:
            pass
        return

    # action == "start": send all memorized ayahs of this surah as audio
    memorized = db.get_memorized_ayahs(user.id)
    ayah_nums = sorted(
        m["ayah_number"] for m in memorized if m["surah_number"] == surah
    )

    if not ayah_nums:
        await query.edit_message_text(
            "⚠️ Bu suradan yod olingan oyat topilmadi." if lang == "uz"
            else "⚠️ No memorized Ayahs found for this Surah."
        )
        return

    surah_info = await quran.get_surah_info(surah)
    surah_name = surah_info["englishName"] if surah_info else f"Surah {surah}"
    edition = _reciter(user.id)

    if lang == "uz":
        intro = (
            f"🎧 *{surah_name} — {len(ayah_nums)} ta yodlangan oyat*\n\n"
            f"Barcha audio ketma-ket yuboriladi. Tinglang va takrorlang!"
        )
    else:
        intro = (
            f"🎧 *{surah_name} — {len(ayah_nums)} memorized Ayah(s)*\n\n"
            f"All audio will be sent in order. Listen and repeat!"
        )

    try:
        await query.edit_message_text(intro, parse_mode="Markdown")
    except Exception:
        pass

    # Send each ayah audio with a small delay to avoid flood limits
    import asyncio
    for ayah_num in ayah_nums:
        await _send_audio(context.bot, user.id, surah, ayah_num, edition)
        await asyncio.sleep(0.4)

    # Mark all ayahs in this surah as reviewed now so next reminder moves to next surah
    db.update_last_reviewed_surah(user.id, surah)

    # Done message
    if lang == "uz":
        done_text = (
            f"✅ *{surah_name} — barcha {len(ayah_nums)} ta oyat yuborildi!*\n\n"
            f"_JazakAllahu khairan. Davom eting!_"
        )
    else:
        done_text = (
            f"✅ *{surah_name} — all {len(ayah_nums)} Ayah(s) sent!*\n\n"
            f"_JazakAllahu Khairan. Keep it up!_"
        )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "🔥 Yodlashni davom etish" if lang == "uz" else "🔥 Continue Memorizing",
            callback_data="flow:start_flow"
        ),
        _home_btn(user.id),
    ]])
    await context.bot.send_message(chat_id=user.id, text=done_text,
                                   parse_mode="Markdown", reply_markup=kb)


# ── Register ──────────────────────────────────────────────────────────────────

def register(app):
    app.add_handler(CommandHandler("flow",    cmd_flow))
    app.add_handler(CommandHandler("oqim",    cmd_flow))  # Uzbek alias
    app.add_handler(CallbackQueryHandler(cb_flow,   pattern=r"^flow:"))
    app.add_handler(CallbackQueryHandler(cb_review, pattern=r"^review:"))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
