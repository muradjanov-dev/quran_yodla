"""Entry point: initialise DB, start scheduler, launch bot."""
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

from src.database.db import init_db
from src.bot import build_app
from src.scheduler.cron import run_reminders

async def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set in .env")

    # 1. Init database
    init_db()

    # 2. Build bot application
    app = build_app(token)

    # 3. Setup PTB job queue for scheduler (runs every 60 seconds)
    job_queue = app.job_queue
    job_queue.run_repeating(
        callback=lambda ctx: asyncio.ensure_future(run_reminders(ctx.bot)),
        interval=60,
        first=5,
        name="reminder_job",
    )

    print("[Bot] Starting polling...")
    await app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    asyncio.run(main())
