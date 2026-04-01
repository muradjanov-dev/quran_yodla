"""Entry point: initialise DB, start scheduler, launch bot."""
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from aiohttp import web

load_dotenv()

from src.database import db as _db
from src.database.db import init_db
from src.bot import build_app
from src.scheduler.cron import run_reminders, run_motivations, run_xatm_reminders, run_daily_admin_report, run_review_reminders
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

async def _run_health_server():
    """Minimal HTTP server for Railway healthcheck — runs forever."""
    port = int(os.environ.get("PORT", 8080))
    health_app = web.Application()
    health_app.router.add_get("/health", lambda r: web.Response(text="OK"))
    health_app.router.add_get("/",       lambda r: web.Response(text="OK"))
    runner = web.AppRunner(health_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[Health] HTTP server listening on port {port}")
    # Keep running forever alongside the bot
    while True:
        await asyncio.sleep(3600)


async def _run_bot():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set in .env")

    # 1. Init + migrate database
    init_db()
    _db.migrate_db()

    # 1b. One-time Firebase -> SQLite migration (runs only if FIREBASE_CREDENTIALS set
    #     AND users table is empty — safe to leave enabled permanently)
    if os.environ.get("FIREBASE_CREDENTIALS") and _db.get_total_users() == 0:
        print("[Startup] Empty DB + Firebase creds found — running auto-migration...")
        try:
            import runpy
            runpy.run_path("migrate_firebase.py", run_name="__main__")
            print("[Startup] Auto-migration complete.")
        except Exception as e:
            print(f"[Startup] Auto-migration failed: {e}")

    # 2. Build bot application
    app = build_app(token)

    job_queue = app.job_queue

    # 3. Reminder job: every 60 seconds, matches HH:MM to users' reminder times
    job_queue.run_repeating(
        callback=lambda ctx: asyncio.ensure_future(run_reminders(ctx.bot)),
        interval=60, first=5, name="reminder_job",
    )
    # 4. Daily motivation — 09:00 Tashkent = 04:00 UTC
    job_queue.run_daily(
        callback=lambda ctx: asyncio.ensure_future(run_motivations(ctx.bot)),
        time=datetime.strptime("04:00", "%H:%M").time(), name="motivation_job",
    )
    # 5. Xatm reminder — 10:00 Tashkent = 05:00 UTC
    job_queue.run_daily(
        callback=lambda ctx: asyncio.ensure_future(run_xatm_reminders(ctx.bot)),
        time=datetime.strptime("05:00", "%H:%M").time(), name="xatm_reminder_job",
    )
    # 6. Admin daily report — 23:50 Tashkent = 18:50 UTC
    job_queue.run_daily(
        callback=lambda ctx: asyncio.ensure_future(run_daily_admin_report(ctx.bot)),
        time=datetime.strptime("18:50", "%H:%M").time(), name="admin_report_job",
    )
    # 7. Congrats flush — every 30 minutes
    job_queue.run_repeating(
        callback=lambda ctx: asyncio.ensure_future(flush_congrats_queue(ctx.bot)),
        interval=1800, first=30, name="congrats_flush_job",
    )
    # 8. Review reminder — 15:00 Tashkent = 10:00 UTC
    job_queue.run_daily(
        callback=lambda ctx: asyncio.ensure_future(run_review_reminders(ctx.bot)),
        time=datetime.strptime("10:00", "%H:%M").time(), name="review_reminder_job",
    )
    # 9. Weekly top-5 — Sunday 22:00 Tashkent = 17:00 UTC
    job_queue.run_daily(
        callback=lambda ctx: asyncio.ensure_future(run_weekly_announcement(ctx.bot)),
        time=datetime.strptime("17:00", "%H:%M").time(), days=(6,),
        name="weekly_announcement_job",
    )

    print("[Bot] Starting polling...")
    async with app:
        await app.updater.start_polling(allowed_updates=["message", "callback_query"])
        await app.start()
        await _send_startup_notification(app)
        await asyncio.Event().wait()


async def main():
    await asyncio.gather(
        _run_health_server(),
        _run_bot(),
    )

if __name__ == "__main__":
    asyncio.run(main())
