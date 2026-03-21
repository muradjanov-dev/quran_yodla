"""Settings handler with multi-reminder (up to 10) and Back buttons."""
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from src.database import db
from src.i18n import t

TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

def _settings_keyboard(user_id: int) -> InlineKeyboardMarkup:
    from src.handlers.onboarding import main_menu_keyboard
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(user_id, "btn_set_reminder"), callback_data="settings:reminders"),
            InlineKeyboardButton(t(user_id, "btn_set_goal"), callback_data="settings:goal"),
        ],
        [InlineKeyboardButton(t(user_id, "btn_set_language"), callback_data="settings:language")],
        [InlineKeyboardButton(t(user_id, "btn_main_menu"), callback_data="menu:learn")],
    ])

async def _show_settings_menu(query_or_msg, user_id: int, edit: bool = False):
    settings = db.get_settings(user_id)
    goal = settings["daily_goal_ayahs"] if settings else 3
    text = t(user_id, "settings_header") + "\n\n" + t(user_id, "settings_current", goal=goal)
    keyboard = _settings_keyboard(user_id)
    if edit:
        try:
            await query_or_msg.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            await query_or_msg.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await query_or_msg.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

def _reminders_keyboard(user_id: int, reminders: list) -> InlineKeyboardMarkup:
    rows = []
    for r in reminders:
        rows.append([InlineKeyboardButton(
            f"⏰ {r['reminder_time']} — tap to remove",
            callback_data=f"settings:rm_reminder:{r['id']}",
        )])
    from src.handlers.limits import reminder_limit
    if len(reminders) < reminder_limit(user_id):
        rows.append([InlineKeyboardButton(t(user_id, "btn_add_reminder"), callback_data="settings:add_reminder")])
    rows.append([InlineKeyboardButton(t(user_id, "btn_back_settings"), callback_data="settings:back")])
    return InlineKeyboardMarkup(rows)

async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not db.get_user(user.id):
        await update.message.reply_text(t(user.id, "please_start"))
        return
    await _show_settings_menu(update.message, user.id, edit=False)

async def cb_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    parts = query.data.split(":")
    action = parts[1]

    if action == "back":
        await _show_settings_menu(query, user.id, edit=True)

    elif action == "reminders":
        reminders = db.get_reminders(user.id)
        if reminders:
            lst = "\n".join(f"• {r['reminder_time']}" for r in reminders)
            text = t(user_id=user.id, key="settings_reminder_list_header",
                     count=len(reminders), list=lst)
        else:
            text = t(user.id, "settings_reminder_list_empty")
        keyboard = _reminders_keyboard(user.id, reminders)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif action == "add_reminder":
        db.update_settings(user.id, awaiting_input="reminder_time")
        await query.edit_message_text(
            t(user.id, "settings_reminder_prompt"),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t(user.id, "btn_back_settings"), callback_data="settings:reminders"),
            ]]),
        )

    elif action == "rm_reminder" and len(parts) >= 3:
        rid = int(parts[2])
        # Fetch time before deleting for display
        rems = db.get_reminders(user.id)
        rtime = next((r["reminder_time"] for r in rems if r["id"] == rid), "?")
        db.remove_reminder(user.id, rid)
        reminders = db.get_reminders(user.id)
        if reminders:
            lst = "\n".join(f"• {r['reminder_time']}" for r in reminders)
            text = t(user.id, "settings_reminder_removed", time=rtime) + "\n\n" + \
                   t(user_id=user.id, key="settings_reminder_list_header",
                     count=len(reminders), list=lst)
        else:
            text = t(user.id, "settings_reminder_removed", time=rtime) + "\n\n" + \
                   t(user.id, "settings_reminder_list_empty")
        keyboard = _reminders_keyboard(user.id, reminders)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif action == "goal":
        db.update_settings(user.id, awaiting_input="daily_goal")
        await query.edit_message_text(
            t(user.id, "settings_goal_prompt"),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t(user.id, "btn_back_settings"), callback_data="settings:back"),
            ]]),
        )

    elif action == "language":
        from src.i18n.en import STRINGS as EN
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(EN["lang_en"], callback_data="lang:en"),
                InlineKeyboardButton(EN["lang_uz"], callback_data="lang:uz"),
            ]
        ])
        await query.edit_message_text(EN["choose_language"], parse_mode="Markdown", reply_markup=keyboard)

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle wizard text inputs (reminders, goals, ayah numbers, quiz answers via text)."""
    user = update.effective_user
    if not db.get_user(user.id):
        return
    settings = db.get_settings(user.id)
    if not settings or not settings["awaiting_input"]:
        return

    text = update.message.text.strip()
    awaiting = settings["awaiting_input"]
    from src.handlers.onboarding import main_menu_keyboard

    # ── Admin: decline reason ──────────────────────────────────────
    if awaiting and awaiting.startswith("decline_reason:"):
        # Format: decline_reason:<req_id>:<target_user_id>
        parts = awaiting.split(":")
        req_id = int(parts[1])
        target_user_id = int(parts[2])
        db.update_payment_request(req_id, status="declined", decline_reason=text)
        db.update_settings(user.id, awaiting_input=None)
        # Notify target user
        target_user = db.get_user(target_user_id)
        lang = target_user["language"] if target_user else "en"
        user_msg = (
            f"❌ *Your payment request was declined.*\n\nReason: _{text}_\n\n"
            "Please check the payment details and try again with /premium"
            if lang == "en" else
            f"❌ *Sizning to'lov so'rovingiz rad etildi.*\n\nSabab: _{text}_\n\n"
            "Iltimos to'lov ma'lumotlarini tekshiring va /premium orqali qayta urinib ko'ring"
        )
        try:
            await context.bot.send_message(
                chat_id=target_user_id, text=user_msg, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💎 Try Again", callback_data="menu:premium"),
                ]]))
        except Exception:
            pass
        await update.message.reply_text(
            f"✅ Declined and user notified.\nReason sent: _{text}_",
            parse_mode="Markdown")
        return

    if awaiting == "reminder_time":
        if TIME_RE.match(text):
            prem = db.is_premium(user.id)
            ok, reason = db.add_reminder(user.id, text, premium=prem)
            if ok:
                db.update_settings(user.id, awaiting_input=None)
                reminders = db.get_reminders(user.id)
                lst = "\n".join(f"• {r['reminder_time']}" for r in reminders)
                msg_text = t(user.id, "settings_reminder_saved", time=text) + "\n\n" + \
                            t(user_id=user.id, key="settings_reminder_list_header",
                              count=len(reminders), list=lst)
                keyboard = _reminders_keyboard(user.id, reminders)
            else:
                reminders = db.get_reminders(user.id)
                msg_text = t(user.id, "settings_reminder_max")
                keyboard = _reminders_keyboard(user.id, reminders)
            await update.message.reply_text(msg_text, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await update.message.reply_text(
                t(user.id, "settings_reminder_invalid"),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(t(user.id, "btn_back_settings"), callback_data="settings:back"),
                ]]),
            )

    elif awaiting == "daily_goal":
        try:
            goal = int(text)
            if 1 <= goal <= 20:
                db.update_settings(user.id, daily_goal_ayahs=goal, awaiting_input=None)
                await update.message.reply_text(
                    t(user.id, "settings_goal_saved", goal=goal),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(t(user.id, "btn_back_settings"), callback_data="settings:back"),
                        InlineKeyboardButton(t(user.id, "btn_main_menu"), callback_data="menu:learn"),
                    ]]),
                )
            else:
                await update.message.reply_text(t(user.id, "settings_goal_invalid"),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(t(user.id, "btn_back_settings"), callback_data="settings:back"),
                    ]]))
        except ValueError:
            await update.message.reply_text(t(user.id, "settings_goal_invalid"),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(t(user.id, "btn_back_settings"), callback_data="settings:back"),
                ]]))

    elif awaiting == "custom_plan":
        try:
            n = int(text)
            if 1 <= n <= 20:
                db.update_settings(user.id, custom_plan_ayahs=n, study_plan="custom",
                                   daily_goal_ayahs=n, awaiting_input=None)
                await update.message.reply_text(
                    t(user.id, "settings_goal_saved", goal=n),
                    parse_mode="Markdown",
                    reply_markup=main_menu_keyboard(user.id),
                )
            else:
                await update.message.reply_text(t(user.id, "plan_invalid_number"),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(t(user.id, "nav_btn_back"), callback_data="menu:learn"),
                    ]]))
        except ValueError:
            await update.message.reply_text(t(user.id, "plan_invalid_number"))

    elif awaiting and awaiting.startswith("choose_ayah:"):
        # Handle ayah number input from navigator
        surah_number = int(awaiting.split(":")[1])
        from src.api import quran
        import asyncio
        try:
            n = int(text)
            surah_info = await quran.get_surah_info(surah_number)
            ayah_count = surah_info["numberOfAyahs"] if surah_info else 1
            if 1 <= n <= ayah_count:
                db.update_settings(user.id, awaiting_input=None)
                # Show plan selection
                from src.handlers.navigator import _plan_keyboard
                name = surah_info["englishName"] if surah_info else f"Surah {surah_number}"
                await update.message.reply_text(
                    t(user.id, "nav_choose_plan", surah_name=name, ayah_num=n),
                    parse_mode="Markdown",
                    reply_markup=_plan_keyboard(user.id, surah_number, n),
                )
            else:
                await update.message.reply_text(
                    t(user.id, "nav_choose_ayah_prompt",
                      surah_name=surah_info["englishName"],
                      ayah_count=ayah_count),
                    parse_mode="Markdown",
                )
        except (ValueError, TypeError):
            await update.message.reply_text(t(user.id, "plan_invalid_number"))

def register(app):
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CallbackQueryHandler(cb_settings, pattern=r"^settings:"))
    # Text handler must be last
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
