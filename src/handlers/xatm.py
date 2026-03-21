"""Jamoaviy Xatm (Group Quran Reading) module."""
import math
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, helpers
from telegram.ext import ContextTypes, CallbackQueryHandler

from src.database import db
from src.i18n import t

HOME_CB = "menu:home"

def _home_btn(uid: int) -> InlineKeyboardButton:
    return InlineKeyboardButton(t(uid, "btn_main_menu"), callback_data=HOME_CB)

async def _edit_or_reply(target, text: str, kb: InlineKeyboardMarkup):
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

async def _show_xatm_dashboard(target, user_id: int):
    stats = db.get_xatm_stats()
    
    # Format times safely
    def fmt_time(secs: int) -> str:
        if secs <= 0: return "0 kun"
        days = math.floor(secs / 86400)
        hrs = math.floor((secs % 86400) / 3600)
        res = []
        if days > 0: res.append(f"{days} kun")
        if hrs > 0: res.append(f"{hrs} soat")
        return " ".join(res) if res else "< 1 soat"
    
    avg_time = fmt_time(int(stats.get("avg_seconds", 0)))
    fast_time = fmt_time(int(stats.get("fastest_seconds", 0)))
    long_time = fmt_time(int(stats.get("longest_seconds", 0)))

    text = t(
        user_id, "xatm_dashboard_header",
        total_xatms=stats.get("total_xatms", 0),
        total_participants=stats.get("total_participants", 0),
        avg_time=avg_time,
        fastest=fast_time,
        longest=long_time
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(t(user_id, "xatm_btn_join_active"), callback_data="xatm:join")],
        [InlineKeyboardButton(t(user_id, "xatm_btn_create_custom"), callback_data="xatm:create")],
        [_home_btn(user_id)]
    ])

    await _edit_or_reply(target, text, kb)

async def _show_xatm_view(target, user_id: int, xatm_id: int, alert_msg: str | None = None):
    xatm = db.get_xatm(xatm_id)
    if not xatm:
        return
        
    juzs = db.get_xatm_juzs(xatm_id)
    juz_map = {j["juz_number"]: j for j in juzs}
    
    status_msg = t(user_id, f"xatm_status_{xatm['status']}")
    text = t(user_id, "xatm_view_header", xatm_id=xatm_id, status_text=status_msg)
    
    # Generating 5 rows of 6 buttons
    rows = []
    for row_idx in range(5):
        row = []
        for col_idx in range(1, 7):
            j_num = row_idx * 6 + col_idx
            state = juz_map.get(j_num)
            
            # Button appearance
            label = str(j_num)
            cb_data = "xatm:void" # Default unclickable unless specific condition
            
            if state:
                if state["user_id"] == user_id:
                    # Owned by me
                    if state["status"] == "completed":
                        label = f"{j_num} ✅"
                    else:
                        label = f"{j_num} 🟢"
                        # Only allow completion clicking if marathon started
                        if xatm["status"] in ("active", "completed"):
                            cb_data = f"xatm:complete_juz:{xatm_id}:{j_num}"
                else:
                    # Owned by someone else
                    label = f"{j_num} 🔒" if state["status"] != "completed" else f"{j_num} ✅"
            else:
                if xatm["status"] == "recruiting":
                    cb_data = f"xatm:assign_juz:{xatm_id}:{j_num}"
            
            row.append(InlineKeyboardButton(label, callback_data=cb_data))
        rows.append(row)

    # Actions based on my assigned juzs
    my_assigned = [j for j in juz_map.values() if j["user_id"] == user_id and j["status"] == "assigned"]
    if xatm["status"] == "active" and my_assigned:
        # Give a big button for the first uncompleted juz 
        first_juz = my_assigned[0]["juz_number"]
        rows.append([InlineKeyboardButton(
            t(user_id, "xatm_btn_mark_completed", juz=first_juz), 
            callback_data=f"xatm:complete_juz:{xatm_id}:{first_juz}"
        )])

    # Invite URL (using switch inline query to share)
    bot_username = "HifzBot"  # You'd ideally get this from context.bot.username, but this works nicely for sharing deep links inline if setup. 
    # Or we can just use a regular URL switch button.
    share_url = f"https://t.me/share/url?url=https://t.me/hifz_bot?start=xatm_{xatm_id}&text=" + t(user_id, "xatm_share_text")
    rows.append([InlineKeyboardButton(t(user_id, "xatm_share_btn"), url=share_url)])
    
    rows.append([InlineKeyboardButton("🔙", callback_data="xatm:dashboard")])

    kb = InlineKeyboardMarkup(rows)
    try:
        if alert_msg and hasattr(target, "answer"):
            await target.answer(alert_msg, show_alert=True)
        await _edit_or_reply(target, text, kb)
    except Exception as e:
        print(f"Xatm View Edit Error: {e}")

async def _notify_all_participants(xatm_id: int, translation_key: str, bot):
    """Sends a notification message to all unique participants of a given Xatm."""
    juzs = db.get_xatm_juzs(xatm_id)
    participants = list(set([j["user_id"] for j in juzs]))
    
    for uid in participants:
        msg = t(uid, translation_key, xatm_id=xatm_id)
        try:
            await bot.send_message(chat_id=uid, text=msg, parse_mode="Markdown")
        except Exception:
            pass

async def cb_xatm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else ""

    if action == "dashboard":
        await query.answer()
        await _show_xatm_dashboard(query, user.id)

    elif action == "join":
        await query.answer()
        xatm_id = db.get_or_create_recruiting_xatm()
        await _show_xatm_view(query, user.id, xatm_id)
        
    elif action == "create":
        await query.answer()
        xatm_id = db.create_custom_xatm(user.id)
        await _show_xatm_view(query, user.id, xatm_id)
        
    elif action == "assign_juz":
        _, _, xatm_id, juz = data
        xatm_id, juz = int(xatm_id), int(juz)
        
        success = db.assign_xatm_juz(xatm_id, juz, user.id)
        if not success:
            await _show_xatm_view(query, user.id, xatm_id, alert_msg=t(user.id, "xatm_already_taken"))
            return
        else:
            await query.answer()
            
        # Check if full -> "active"
        new_status = db.check_and_update_xatm_status(xatm_id)
        await _show_xatm_view(query, user.id, xatm_id)
        
        # Dispatch notifications if marathon started
        if new_status == "active":
            await _notify_all_participants(xatm_id, "xatm_marathon_started_notify", context.bot)

    elif action == "complete_juz":
        _, _, xatm_id, juz = data
        xatm_id, juz = int(xatm_id), int(juz)
        
        db.complete_xatm_juz(xatm_id, juz, user.id)
        await query.answer()
        
        new_status = db.check_and_update_xatm_status(xatm_id)
        await _show_xatm_view(query, user.id, xatm_id)
        
        if new_status == "completed":
            await _notify_all_participants(xatm_id, "xatm_marathon_completed_notify", context.bot)

    elif action == "void":
        await query.answer()

def register(app):
    app.add_handler(CallbackQueryHandler(cb_xatm, pattern=r"^xatm:"))
