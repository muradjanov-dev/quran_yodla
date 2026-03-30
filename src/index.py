"""Entry point: initialise DB, start scheduler, launch bot."""
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from src.database.db import init_db
from src.bot import build_app
from src.scheduler.cron import run_reminders, run_motivations, run_xatm_reminders, run_daily_admin_report

async def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set in .env")

    # 1. Init database
    init_db()

    # 2. Build bot application
    app = build_app(token)

    job_queue = app.job_queue

    # 3. Reminder job: runs every 60 seconds, matches HH:MM to users' reminder times
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

    print("[Bot] Starting polling...")
    await app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    asyncio.run(main())
