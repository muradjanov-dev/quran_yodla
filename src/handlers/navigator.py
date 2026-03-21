"""Updated Quran Navigator with Back buttons at every level."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from src.database import db
from src.i18n import t, plan_label
from src.api import quran

def _chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

def _get_lang(user_id: int) -> str:
    u = db.get_user(user_id)
    return dict(u).get("language", "en") if u else "en"


def _plan_keyboard(user_id: int, surah_number: int, ayah_number: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(user_id, "plan_gentle"),
                                 callback_data=f"nav:plan:{surah_number}:{ayah_number}:gentle"),
            InlineKeyboardButton(t(user_id, "plan_standard"),
                                 callback_data=f"nav:plan:{surah_number}:{ayah_number}:standard"),
        ],
        [
            InlineKeyboardButton(t(user_id, "plan_intense"),
                                 callback_data=f"nav:plan:{surah_number}:{ayah_number}:intense"),
            InlineKeyboardButton(t(user_id, "plan_custom"),
                                 callback_data=f"nav:plan:{surah_number}:{ayah_number}:custom"),
        ],
        [InlineKeyboardButton(t(user_id, "nav_btn_back"),
                              callback_data=f"nav:surah:{surah_number}")],
        [InlineKeyboardButton(t(user_id, "btn_main_menu"), callback_data="menu:home")],
    ])

async def _show_navigator(query_or_msg, user_id: int):
    resume = db.get_resume_point(user_id)
    rows = []
    if resume:
        rows.append([InlineKeyboardButton(
            "📍 Kelgan joyimdan davom etish" if _get_lang(user_id) == "uz" else "📍 Resume Where I Left Off",
            callback_data="nav:resume")])
    rows += [
        [
            InlineKeyboardButton(t(user_id, "nav_btn_baqara"), callback_data="nav:start:2:1"),
            InlineKeyboardButton(t(user_id, "nav_btn_juz_amma"), callback_data="nav:juz30"),
        ],
        [InlineKeyboardButton(t(user_id, "nav_btn_custom"), callback_data="nav:custom_juz")],
        [InlineKeyboardButton(t(user_id, "btn_main_menu"), callback_data="menu:home")],
    ]
    try:
        await query_or_msg.edit_message_text(
            t(user_id, "nav_welcome"), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))
    except Exception:
        await query_or_msg.message.reply_text(
            t(user_id, "nav_welcome"), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))

async def cmd_start_learning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not db.get_user(user.id):
        from src.i18n.en import STRINGS as EN
        await update.message.reply_text(EN["please_start"])
        return
    resume = db.get_resume_point(user.id)
    lang = _get_lang(user.id)
    rows = []
    if resume:
        rows.append([InlineKeyboardButton(
            "📍 Kelgan joyimdan davom etish" if lang == "uz" else "📍 Resume Where I Left Off",
            callback_data="nav:resume")])
    rows += [
        [
            InlineKeyboardButton(t(user.id, "nav_btn_baqara"), callback_data="nav:start:2:1"),
            InlineKeyboardButton(t(user.id, "nav_btn_juz_amma"), callback_data="nav:juz30"),
        ],
        [InlineKeyboardButton(t(user.id, "nav_btn_custom"), callback_data="nav:custom_juz")],
        [InlineKeyboardButton(t(user.id, "btn_main_menu"), callback_data="menu:learn")],
    ]
    await update.message.reply_text(
        t(user.id, "nav_welcome"), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))

async def cb_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    parts = query.data.split(":")
    action = parts[1]

    if action == "resume":
        # Resume Flow at the last saved position
        resume = db.get_resume_point(user.id)
        if not resume:
            await _show_navigator(query, user.id)
            return
        surah_num = resume["surah_number"]
        ayah_num  = resume["ayah_number"]
        db.init_learning_session(user.id, surah_num, ayah_num)
        # Trigger flow rendering via callback to flow handler
        from src.handlers import flow as flow_handler
        sess = db.get_learning_session(user.id)
        import sqlite3
        sess_dict = dict(sess) if isinstance(sess, sqlite3.Row) else (sess or {})
        await flow_handler._render_state(query, user.id, sess_dict, bot=context.bot)
        return

    if action == "back_to_l1":
        await _show_navigator(query, user.id)

    elif action == "juz30":
        surahs = await quran.get_surah_list()
        juz30_surahs = [s for s in surahs if s["number"] >= 78]
        rows = list(_chunk(juz30_surahs, 3))
        kbd_rows = [[
            InlineKeyboardButton(s["englishName"], callback_data=f"nav:surah:{s['number']}")
            for s in chunk
        ] for chunk in rows]
        kbd_rows.append([InlineKeyboardButton(t(user.id, "nav_btn_back"), callback_data="nav:back_to_l1")])
        kbd_rows.append([InlineKeyboardButton(t(user.id, "btn_main_menu"), callback_data="menu:learn")])
        await query.edit_message_text(
            t(user.id, "nav_juz_amma_header"), parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kbd_rows))

    elif action == "custom_juz":
        rows = list(_chunk(range(1, 31), 5))
        kbd_rows = [[
            InlineKeyboardButton(f"Juz {j}", callback_data=f"nav:juz:{j}")
            for j in chunk
        ] for chunk in rows]
        kbd_rows.append([InlineKeyboardButton(t(user.id, "nav_btn_back"), callback_data="nav:back_to_l1")])
        kbd_rows.append([InlineKeyboardButton(t(user.id, "btn_main_menu"), callback_data="menu:learn")])
        kbd_rows.append([InlineKeyboardButton(t(user.id, "btn_main_menu"), callback_data="menu:home")])
        await query.edit_message_text(
            t(user.id, "nav_custom_juz"), parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kbd_rows))

    elif action == "juz" and len(parts) >= 3:
        juz_number = int(parts[2])
        # Show all surahs in this juz based on known start-of-juz mapping
        JUZ_START = {
            1:(1,1),2:(2,142),3:(2,253),4:(3,93),5:(4,24),
            6:(4,148),7:(5,82),8:(6,111),9:(7,88),10:(8,41),
            11:(9,93),12:(11,6),13:(12,53),14:(15,1),15:(17,1),
            16:(18,75),17:(21,1),18:(23,1),19:(25,21),20:(27,56),
            21:(29,46),22:(33,31),23:(36,28),24:(39,32),25:(41,47),
            26:(46,1),27:(51,31),28:(58,1),29:(67,1),30:(78,1),
        }
        start_surah = JUZ_START.get(juz_number, (1,1))[0]
        end_surah = JUZ_START.get(juz_number + 1, (115,1))[0] - 1
        all_surahs = await quran.get_surah_list()
        surahs = [s for s in all_surahs if start_surah <= s["number"] <= min(end_surah, 114)]
        if not surahs:
            surahs = all_surahs[max(0, start_surah - 2):start_surah + 5]
        rows = list(_chunk(surahs, 3))
        kbd_rows = [[
            InlineKeyboardButton(s["englishName"], callback_data=f"nav:surah:{s['number']}")
            for s in chunk
        ] for chunk in rows]
        kbd_rows.append([InlineKeyboardButton(t(user.id, "nav_btn_back"), callback_data="nav:custom_juz")])
        kbd_rows.append([InlineKeyboardButton(t(user.id, "btn_main_menu"), callback_data="menu:home")])
        await query.edit_message_text(
            f"📂 *Juz {juz_number}:*", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kbd_rows))

    elif action == "surah" and len(parts) >= 3:
        surah_number = int(parts[2])
        surah_info = await quran.get_surah_info(surah_number)
        name = surah_info["englishName"] if surah_info else f"Surah {surah_number}"
        ayah_count = surah_info["numberOfAyahs"] if surah_info else quran.get_ayah_count(surah_number)
        back = "nav:juz30" if surah_number >= 78 else "nav:back_to_l1"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(t(user.id, "nav_btn_start_ayah1"),
                                     callback_data=f"nav:start:{surah_number}:1"),
                InlineKeyboardButton(t(user.id, "nav_btn_choose_ayah"),
                                     callback_data=f"nav:choose_ayah:{surah_number}"),
            ],
            [InlineKeyboardButton(t(user.id, "nav_btn_back"), callback_data=back)],
            [InlineKeyboardButton(t(user.id, "btn_main_menu"), callback_data="menu:home")],
        ])
        await query.edit_message_text(
            t(user.id, "nav_surah_selected", surah_name=name, ayah_count=ayah_count),
            parse_mode="Markdown", reply_markup=keyboard)

    elif action == "choose_ayah" and len(parts) >= 3:
        surah_number = int(parts[2])
        surah_info = await quran.get_surah_info(surah_number)
        name = surah_info["englishName"] if surah_info else f"Surah {surah_number}"
        ayah_count = surah_info["numberOfAyahs"] if surah_info else 1
        db.update_settings(user.id, awaiting_input=f"choose_ayah:{surah_number}")
        await query.edit_message_text(
            t(user.id, "nav_choose_ayah_prompt", surah_name=name, ayah_count=ayah_count),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t(user.id, "nav_btn_back"),
                                     callback_data=f"nav:surah:{surah_number}"),
            ]]))

    elif action == "start" and len(parts) >= 4:
        surah_number = int(parts[2])
        ayah_number = int(parts[3])
        surah_info = await quran.get_surah_info(surah_number)
        name = surah_info["englishName"] if surah_info else f"Surah {surah_number}"
        await query.edit_message_text(
            t(user.id, "nav_choose_plan", surah_name=name, ayah_num=ayah_number),
            parse_mode="Markdown",
            reply_markup=_plan_keyboard(user.id, surah_number, ayah_number))

    elif action == "plan" and len(parts) >= 5:
        surah_number = int(parts[2])
        ayah_number = int(parts[3])
        plan = parts[4]
        plan_ayahs = {"gentle": 1, "standard": 3, "intense": 20, "custom": 0}
        daily = plan_ayahs.get(plan, 3)

        if plan == "custom":
            db.update_settings(user.id, study_plan=plan, awaiting_input="custom_plan")
            await query.edit_message_text(
                t(user.id, "plan_custom_prompt"), parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(t(user.id, "nav_btn_back"),
                                         callback_data=f"nav:start:{surah_number}:{ayah_number}"),
                ]]))
            return

        db.update_settings(user.id, study_plan=plan, daily_goal_ayahs=daily, awaiting_input=None)
        db.mark_ayah(user.id, surah_number, ayah_number, memorized=False)
        surah_info = await quran.get_surah_info(surah_number)
        name = surah_info["englishName"] if surah_info else f"Surah {surah_number}"
        label = plan_label(user.id, plan)
        from src.handlers.onboarding import main_menu_keyboard
        await query.edit_message_text(
            t(user.id, "plan_set", surah_name=name, ayah_num=ayah_number, plan_label=label),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(t(user.id, "btn_profile_short"), callback_data="menu:profile"),
                    InlineKeyboardButton(t(user.id, "btn_flow"), callback_data="menu:flow"),
                ],
                [InlineKeyboardButton(t(user.id, "btn_main_menu"), callback_data="menu:learn")],
            ]))

def register(app):
    app.add_handler(CommandHandler("start_learning", cmd_start_learning))
    app.add_handler(CallbackQueryHandler(cb_nav, pattern=r"^nav:"))
