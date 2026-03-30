"""Entry point: initialise DB, start scheduler, launch bot."""
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from src.database import db as _db
from src.database.db import init_db
from src.bot import build_app
from src.scheduler.cron import run_reminders, run_motivations, run_xatm_reminders, run_daily_admin_report
from src.handlers.achievements import flush_congrats_queue, run_weekly_announcement

RELEASE_NOTES = (
    "🚀 *Bot yangilandi!*\n\n"
    "🆕 *Yangiliklar:*\n"
    "• 🏆 30 ta yutuq (achievement) tizimi qo'shildi\n"
    "• 📊 Haftalik musobaqa — har hafta top-5 e'lon qilinadi\n"
    "• 🤝 Yutuqqa erishganlarga boshqa userlardan tabrik xabarlari (kuniga max 5 ta)\n"
    "• ⭐ Har yutuq uchun qo'shimcha XP bonuslari\n"
    "• 📅 Haftalik XP reyting — haqiqiy XP o'zgarishsiz qoladi\n\n"
    "_Musobaqa har dushanba yangilanadi, natijalar yakshanba kuni e'lon qilinadi._"
)

async def _send_startup_notification(app):
    try:
        await app.bot.send_message(
            chat_id=_db.ADMIN_ID,
            text=RELEASE_NOTES,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"[Startup] Admin notify failed: {e}")

async def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set in .env")

    # 1. Init + migrate database
    init_db()
    _db.migrate_db()

    # 2. Build bot application (post_init sends admin startup notification)
    app = build_app(token, post_init=_send_startup_notification)

    job_queue = app.job_queue

    # 3. Reminder job: every 60 seconds, matches HH:MM to users' reminder times
    job_queue.run_repeating(
        callback=lambda ctx: asyncio.ensure_future(run_reminders(ctx.bot)),
        interval=60,
        first=5,
        name="reminder_job",
    )

    # 4. Daily motivation for inactive users (09:00 Tashkent = 04:00 UTC)
    job_queue.run_daily(
        callback=lambda ctx: asyncio.ensure_future(run_motivations(ctx.bot)),
        time=datetime.strptime("04:00", "%H:%M").time(),
        name="motivation_job",
    )

    # 5. Daily Xatm reminder (10:00 Tashkent = 05:00 UTC)
    job_queue.run_daily(
        callback=lambda ctx: asyncio.ensure_future(run_xatm_reminders(ctx.bot)),
        time=datetime.strptime("05:00", "%H:%M").time(),
        name="xatm_reminder_job",
    )

    # 6. Admin daily stats report at 23:50 Tashkent = 18:50 UTC
    job_queue.run_daily(
        callback=lambda ctx: asyncio.ensure_future(run_daily_admin_report(ctx.bot)),
        time=datetime.strptime("18:50", "%H:%M").time(),
        name="admin_report_job",
    )

    # 7. Congrats queue flush — every 30 minutes
    job_queue.run_repeating(
        callback=lambda ctx: asyncio.ensure_future(flush_congrats_queue(ctx.bot)),
        interval=1800,
        first=30,
        name="congrats_flush_job",
    )

    # 8. Weekly top-5 announcement — Sunday 22:00 Tashkent = 17:00 UTC
    job_queue.run_daily(
        callback=lambda ctx: asyncio.ensure_future(run_weekly_announcement(ctx.bot)),
        time=datetime.strptime("17:00", "%H:%M").time(),
        days=(6,),  # Sunday only
        name="weekly_announcement_job",
    )

    print("[Bot] Starting polling...")
    await app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    asyncio.run(main())
