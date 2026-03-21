"""Top-level entry point. Run with: python main.py"""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from src.database.db import init_db
from src.bot import build_app
from src.scheduler.cron import run_reminders, run_motivations

async def reminder_job(context):
    await run_reminders(context.bot)

async def motivation_job(context):
    await run_motivations(context.bot)

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set in .env")

    # 1. Init database
    init_db()

    # 2. Build bot application
    app = build_app(token)

    # 3. Reminder job — every 60 seconds
    app.job_queue.run_repeating(
        callback=reminder_job,
        interval=60,
        first=5,
        name="reminder_job",
    )

    # 4. Motivation job — once a day at 09:00 local time (fallback: first run after 30min)
    import datetime
    app.job_queue.run_daily(
        callback=motivation_job,
        time=datetime.time(hour=9, minute=0),
        name="motivation_job",
    )

    print("[Hifz Bot] Database ready")
    print("[Hifz Bot] Reminders: every 60s | Motivation: daily 09:00")
    print("[Hifz Bot] Polling... Press Ctrl+C to stop.")

    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
