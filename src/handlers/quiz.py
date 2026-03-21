"""Quiz module — 3 full-Quran game modes with per-answer XP."""
import json
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from src.database import db
from src.i18n import t
from src.api import quran

QUESTIONS_PER_SESSION = 20
XP_PER_CORRECT = 10
XP_BONUS_MASTER = 50
PASS_THRESHOLD = 0.97  # 97%

# ── Menu ────────────────────────────────────────────────────────────────────

def _quiz_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    memorized = db.get_memorized_ayahs(user_id)
    rows = [
        [
            InlineKeyboardButton(t(user_id, "quiz_btn_surah_order"), callback_data="quiz:mode:surah_order"),
            InlineKeyboardButton(t(user_id, "quiz_btn_surah_name"), callback_data="quiz:mode:surah_name"),
        ],
        [InlineKeyboardButton(t(user_id, "quiz_btn_ayah_order"), callback_data="quiz:pick_surah")],
    ]
    if memorized:
        lang = dict(db.get_user(user_id) or {}).get("language", "en")
        label = "🧠 Yodlangan Oyatlardan Test" if lang == "uz" else "🧠 Quiz From Memorized Ayahs"
        rows.append([InlineKeyboardButton(label, callback_data="quiz:mode:memorized_menu")])
    rows.append([InlineKeyboardButton(t(user_id, "btn_main_menu"), callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)

async def _show_quiz_menu(query_or_msg, user_id: int):
    try:
        await query_or_msg.edit_message_text(
            t(user_id, "quiz_menu"), parse_mode="Markdown",
            reply_markup=_quiz_menu_keyboard(user_id))
    except Exception:
        await query_or_msg.message.reply_text(
            t(user_id, "quiz_menu"), parse_mode="Markdown",
            reply_markup=_quiz_menu_keyboard(user_id))

# ── Question builders ──────────────────────────────────────────────────────

async def _build_surah_order_question(user_id: int, surahs: list, asked: list) -> dict:
    """What number is Surah X? — correct answer is the surah number."""
    remaining = [s for s in surahs if s["number"] not in asked]
    if not remaining:
        remaining = surahs
    correct_surah = random.choice(remaining)
    correct_ans = correct_surah["number"]
    # Generate 3 wrong answers: nearby numbers that aren't correct
    all_nums = list(range(1, 115))
    wrong_pool = [n for n in all_nums if n != correct_ans]
    wrongs = random.sample(wrong_pool, 3)
    options = sorted([correct_ans] + wrongs)
    question = t(user_id, "quiz_q_surah_order", surah_name=correct_surah["englishName"])
    return {
        "question": question,
        "options": options,
        "correct": correct_ans,
        "surah_id": correct_surah["number"],
        "type": "number",
    }

async def _build_surah_name_question(user_id: int, surahs: list, asked: list) -> dict:
    """What is the name of Surah #N? — correct answer is the name."""
    remaining = [s for s in surahs if s["number"] not in asked]
    if not remaining:
        remaining = surahs
    correct_surah = random.choice(remaining)
    correct_name = correct_surah["englishName"]
    wrong_pool = [s["englishName"] for s in surahs if s["number"] != correct_surah["number"]]
    wrongs = random.sample(wrong_pool, 3)
    options = [correct_name] + wrongs
    random.shuffle(options)
    question = t(user_id, "quiz_q_surah_name", number=correct_surah["number"])
    return {
        "question": question,
        "options": options,
        "correct": correct_name,
        "surah_id": correct_surah["number"],
        "type": "text",
    }

async def _build_ayah_order_question(user_id: int, surah_number: int) -> dict | None:
    """Which ayah appears at position N in this surah?"""
    ayahs = await quran.get_ayahs(surah_number)
    surah_info = await quran.get_surah_info(surah_number)
    if not ayahs or len(ayahs) < 4:
        return None
    target_idx = random.randint(0, len(ayahs) - 1)
    correct_ayah = ayahs[target_idx]
    # Use first 30 chars of arabic to keep callback_data under 64 bytes
    correct_text = correct_ayah["text"][:30]
    wrong_idxs = random.sample([i for i in range(len(ayahs)) if i != target_idx], min(3, len(ayahs)-1))
    wrongs = [ayahs[i]["text"][:30] for i in wrong_idxs]
    options = [correct_text] + wrongs
    random.shuffle(options)
    name = surah_info["englishName"] if surah_info else f"Surah {surah_number}"
    question = t(user_id, "quiz_q_ayah_order", surah_name=name, position=target_idx + 1)
    return {
        "question": question,
        "options": options,
        "correct": correct_text,
        "surah_id": surah_number,
        "ayah_num": correct_ayah["number"],
        "type": "text",
    }


async def _build_complete_ayah_question(user_id: int, memorized: list[dict]) -> dict | None:
    """Mode: complete_ayah — show start of a memorized ayah, pick the real continuation."""
    if len(memorized) < 2:
        return None
    entry = random.choice(memorized)
    surah, ayah_num = entry["surah_number"], entry["ayah_number"]
    ayahs = await quran.get_ayahs(surah)
    target = next((a for a in ayahs if a["number"] == ayah_num), None)
    if not target or len(target["text"]) < 20:
        return None
    full = target["text"]
    mid = len(full) // 2
    stem   = full[:mid].rsplit(' ', 1)[0]  # show first half
    correct = full[mid:].lstrip()[:50]      # correct: second half snippet
    # Wrongs from other memorized ayahs
    others = [m for m in memorized if not (m["surah_number"] == surah and m["ayah_number"] == ayah_num)]
    wrong_texts = []
    for o in random.sample(others, min(3, len(others))):
        oa = await quran.get_ayahs(o["surah_number"])
        ot = next((a for a in oa if a["number"] == o["ayah_number"]), None)
        if ot:
            wrong_texts.append(ot["text"][:50])
    while len(wrong_texts) < 3:
        wrong_texts.append(f"...{full[:20]}"[:50])
    options = [correct] + wrong_texts[:3]
    random.shuffle(options)
    surah_info = await quran.get_surah_info(surah)
    name = surah_info["englishName"] if surah_info else f"Surah {surah}"
    lang = dict(db.get_user(user_id) or {}).get("language", "en")
    q = (
        f"Keling, davom ettiramiz:\n\n_{stem}..._\n\nDavomini tanlang:"
        if lang == "uz" else
        f"Complete the Ayah:\n\n_{stem}..._\n\nChoose the continuation:"
    )
    return {
        "question": q, "options": options, "correct": correct,
        "surah_id": surah, "ayah_num": ayah_num, "type": "text",
    }


async def _build_which_surah_question(user_id: int, memorized: list[dict], all_surahs: list) -> dict | None:
    """Mode: which_surah — show a memorized ayah, user picks which surah it's from."""
    if not memorized:
        return None
    entry = random.choice(memorized)
    surah, ayah_num = entry["surah_number"], entry["ayah_number"]
    ayahs = await quran.get_ayahs(surah)
    target = next((a for a in ayahs if a["number"] == ayah_num), None)
    if not target:
        return None
    surah_info = await quran.get_surah_info(surah)
    correct_name = surah_info["englishName"] if surah_info else f"Surah {surah}"
    wrong_pool = [s["englishName"] for s in all_surahs if s["number"] != surah]
    wrongs = random.sample(wrong_pool, min(3, len(wrong_pool)))
    options = [correct_name] + wrongs
    random.shuffle(options)
    arabic_snippet = target["text"][:80]
    lang = dict(db.get_user(user_id) or {}).get("language", "en")
    q = (
        f"Ushbu oyat qaysi suradan?\n\n_{arabic_snippet}_"
        if lang == "uz" else
        f"Which Surah is this Ayah from?\n\n_{arabic_snippet}_"
    )
    return {
        "question": q, "options": options, "correct": correct_name,
        "surah_id": surah, "ayah_num": ayah_num, "type": "text",
    }

def _options_keyboard(user_id: int, options: list, correct: str | int, question_num: int) -> InlineKeyboardMarkup:
    rows = []
    for opt in options:
        label = str(opt)
        # Encode answer in callback — prefix with quiz:ans:
        safe_opt = str(opt).replace(":", "§")[:40]  # keep callback short
        rows.append([InlineKeyboardButton(label, callback_data=f"quiz:ans:{safe_opt}")])
    rows.append([InlineKeyboardButton(t(user_id, "quiz_btn_back"), callback_data="quiz:menu")])
    return InlineKeyboardMarkup(rows)

# ── Send next question ─────────────────────────────────────────────────────

async def _send_next_question(query, user_id: int):
    session = db.get_quiz_session(user_id)
    if not session or not session["active"]:
        await _show_quiz_menu(query, user_id)
        return

    surahs = await quran.get_surah_list()
    mode = session["mode"]
    asked = json.loads(session["asked_ids"])
    q_num = session["question_num"] + 1
    total = session["total_count"]
    correct_so_far = session["correct_count"]
    xp_so_far = correct_so_far * XP_PER_CORRECT

    if q_num > total:
        await _finish_quiz(query, user_id, session)
        return

    q = None
    if mode == "surah_order":
        q = await _build_surah_order_question(user_id, surahs, asked)
    elif mode == "surah_name":
        q = await _build_surah_name_question(user_id, surahs, asked)
    elif mode == "ayah_order":
        surah_filter = session["surah_filter"] or random.choice(surahs)["number"]
        q = await _build_ayah_order_question(user_id, surah_filter)
        if not q:
            q = await _build_surah_order_question(user_id, surahs, asked)
    elif mode == "complete_ayah":
        memorized = db.get_memorized_ayahs(user_id)
        q = await _build_complete_ayah_question(user_id, memorized)
        if not q:
            q = await _build_surah_order_question(user_id, surahs, asked)
    elif mode == "which_surah":
        memorized = db.get_memorized_ayahs(user_id)
        q = await _build_which_surah_question(user_id, memorized, surahs)
        if not q:
            q = await _build_surah_order_question(user_id, surahs, asked)

    if not q:
        await _show_quiz_menu(query, user_id)
        return

    asked.append(q["surah_id"])
    db.update_quiz_session(user_id,
                           question_num=q_num,
                           asked_ids=json.dumps(asked))

    import base64
    correct_enc = base64.b64encode(str(q["correct"]).encode()).decode()
    # Store surah+ayah so we can log interaction on answer
    ayah_tag = f":{q.get('surah_id', 0)}:{q.get('ayah_num', 0)}"
    db.update_settings(user_id, awaiting_input=f"quiz_ans:{correct_enc}{ayah_tag}")

    text = t(user_id, "quiz_question",
             num=q_num, total=total,
             question=q["question"],
             correct=correct_so_far, num_done=q_num - 1,
             xp=xp_so_far)
    keyboard = _options_keyboard(user_id, q["options"], q["correct"], q_num)
    try:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
    except Exception:
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

async def _finish_quiz(query, user_id: int, session):
    correct = session["correct_count"]
    total = session["total_count"]
    pct = int((correct / total) * 100)
    xp_earned = correct * XP_PER_CORRECT

    if pct >= 97:
        result_msg = t(user_id, "quiz_passed")
        db.unlock_badge(user_id, "quiz_master")
        xp_earned += XP_BONUS_MASTER
    elif pct >= 70:
        result_msg = t(user_id, "quiz_good")
    else:
        result_msg = t(user_id, "quiz_try_again")

    # Award XP
    new_xp, _, league_changed = db.add_xp(user_id, xp_earned)

    db.update_quiz_session(user_id, active=0)
    db.update_settings(user_id, awaiting_input=None)

    text = t(user_id, "quiz_finished",
             correct=correct, total=total, pct=pct,
             xp=xp_earned, result_msg=result_msg)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(user_id, "quiz_btn_back"), callback_data="quiz:menu"),
            InlineKeyboardButton(t(user_id, "btn_main_menu"), callback_data="menu:learn"),
        ]
    ])
    try:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
    except Exception:
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

# ── Surah picker for ayah_order mode ──────────────────────────────────────

async def _show_surah_picker(query, user_id: int, page: int = 0):
    """Show surahs paginated (36 per page) for ayah_order quiz."""
    surahs = await quran.get_surah_list()
    PER_PAGE = 36
    total = len(surahs)
    start = page * PER_PAGE
    end = min(start + PER_PAGE, total)
    page_surahs = surahs[start:end]
    rows = []
    for chunk in _chunk(page_surahs, 3):
        rows.append([
            InlineKeyboardButton(f"{s['number']}.{s['englishName'][:9]}",
                                 callback_data=f"quiz:start_ayah:{s['number']}")
            for s in chunk
        ])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Prev", callback_data=f"quiz:spage:{page - 1}"))
    if end < total:
        nav.append(InlineKeyboardButton("Next ▶", callback_data=f"quiz:spage:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(t(user_id, "quiz_btn_back"), callback_data="quiz:menu"),
                 InlineKeyboardButton(t(user_id, "btn_main_menu"), callback_data="menu:home")])
    hdr = f"🕌 Sura Tanlash ({start+1}–{end}/{total})"
    try:
        await query.edit_message_text(f"*{hdr}*", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(rows))
    except Exception:
        await query.message.reply_text(f"*{hdr}*", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(rows))

def _chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

# ── Handlers ───────────────────────────────────────────────────────────────

async def cmd_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not db.get_user(user.id):
        from src.i18n.en import STRINGS as EN
        await update.message.reply_text(EN["please_start"])
        return
    await update.message.reply_text(
        t(user.id, "quiz_menu"), parse_mode="Markdown",
        reply_markup=_quiz_menu_keyboard(user.id))

async def cb_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    parts = query.data.split(":")

    if parts[1] == "menu":
        await _show_quiz_menu(query, user.id)

    elif parts[1] == "mode" and len(parts) >= 3:
        mode = parts[2]
        if mode == "memorized_menu":
            # Show sub-menu for memorized-ayah quiz types
            lang = dict(db.get_user(user.id) or {}).get("language", "en")
            rows = [
                [InlineKeyboardButton(
                    "✍️ Davom ettirish (Complete the Ayah)" if lang == "uz" else "✍️ Complete the Ayah",
                    callback_data="quiz:memorized_sub:complete_ayah")],
                [InlineKeyboardButton(
                    "🕌 Qaysi Suradan? (Which Surah?)" if lang == "uz" else "🕌 Which Surah is this Ayah?",
                    callback_data="quiz:memorized_sub:which_surah")],
                [InlineKeyboardButton(t(user.id, "quiz_btn_back"), callback_data="quiz:menu")],
            ]
            hdr = "🧠 *Yodlangan Oyatlardan Test*" if lang == "uz" else "🧠 *Quiz From Memorized Ayahs*"
            try:
                await query.edit_message_text(hdr, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))
            except Exception:
                await query.message.reply_text(hdr, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))
        else:
            db.init_quiz_session(user.id, mode=mode, total=QUESTIONS_PER_SESSION)
            await _send_next_question(query, user.id)

    elif parts[1] == "pick_surah":
        await _show_surah_picker(query, user.id, page=0)

    elif parts[1] == "spage" and len(parts) >= 3:
        page = int(parts[2])
        await _show_surah_picker(query, user.id, page=page)

    elif parts[1] == "start_ayah" and len(parts) >= 3:
        surah_num = int(parts[2])
        db.init_quiz_session(user.id, mode="ayah_order", surah_filter=surah_num, total=QUESTIONS_PER_SESSION)
        await _send_next_question(query, user.id)

    elif parts[1] == "ans" and len(parts) >= 3:
        import base64
        settings = db.get_settings(user.id)
        if not settings or not settings["awaiting_input"] or not settings["awaiting_input"].startswith("quiz_ans:"):
            await query.answer("Session expired. Start a new quiz.")
            await _show_quiz_menu(query, user.id)
            return

        raw = settings["awaiting_input"].split(":", 1)[1]  # correct_enc:surah:ayah or just correct_enc
        # Parse surah/ayah tags appended to encoded answer
        enc_parts = raw.rsplit(":", 2)
        if len(enc_parts) == 3:
            enc, log_surah, log_ayah = enc_parts[0], int(enc_parts[1]), int(enc_parts[2])
        else:
            enc, log_surah, log_ayah = raw, 0, 0
        correct_str = base64.b64decode(enc.encode()).decode()
        user_ans = ":".join(parts[2:]).replace("§", ":")

        session = db.get_quiz_session(user.id)
        correct_count = session["correct_count"] if session else 0
        is_correct = user_ans.strip() == correct_str.strip()

        if is_correct:
            correct_count += 1
            db.update_quiz_session(user.id, correct_count=correct_count)
            new_xp, _, _ = db.add_xp(user.id, XP_PER_CORRECT)
            prefix = t(user.id, "quiz_correct")
            # Log interaction for analytics
            if log_surah and log_ayah:
                db.log_interaction(user.id, log_surah, log_ayah, 'quiz_correct')
        else:
            prefix = t(user.id, "quiz_wrong", answer=correct_str[:60])
            if log_surah and log_ayah:
                db.log_interaction(user.id, log_surah, log_ayah, 'quiz_wrong')

        db.update_settings(user.id, awaiting_input=None)

        session = db.get_quiz_session(user.id)
        q_done = session["question_num"] if session else 0
        total = session["total_count"] if session else QUESTIONS_PER_SESSION

        if q_done >= total:
            await _finish_quiz(query, user.id, session)
        else:
            await _send_next_question(query, user.id)

    elif parts[1] == "memorized_sub" and len(parts) >= 3:
        # Sub-menu for memorized-ayah quiz modes
        sub = parts[2]
        db.init_quiz_session(user.id, mode=sub, total=10)  # shorter 10-question session
        await _send_next_question(query, user.id)

def register(app):
    app.add_handler(CommandHandler("quiz", cmd_quiz))
    app.add_handler(CallbackQueryHandler(cb_quiz, pattern=r"^quiz:"))
