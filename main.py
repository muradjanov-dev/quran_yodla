"""
main.py — Application entry point with health server and APScheduler.
Uses Firebase Firestore as the primary data store.
"""

import asyncio
import logging
import os
from datetime import datetime
import pytz
from aiohttp import web

from telegram import BotCommand, Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler

from config import (
    BOT_TOKEN, WEBHOOK_URL, PORT, ADMIN_ID, LOCAL_TZ
)
import firebase_config  # noqa — ensures Firebase is initialized at startup
from services.firebase_service import get_notification_settings, get_notification_times_list, backfill_xatm_numbers  # noqa

# ─── Release Notes (sent to admin on every startup) ───────────────────────────
RELEASE_NOTES = """
🚀 BOT YANGILANDI!

🆕 YANGI:
• 🏆 30 ta yutuq (achievement) tizimi
• 📊 Haftalik musobaqa — har hafta top-5
• 🤝 Yutuqlarga boshqa userlardan tabrik
• ⭐ Har yutuq uchun qo'shimcha XP
"""

# ─── Handlers ──────────────────────────────────────────────────────────────────
from handlers.start    import build_onboarding_handler
from handlers.memorize import build_memorize_handler
from handlers.premium  import build_premium_handler, register_premium_callbacks
from handlers.admin    import build_admin_handler, register_admin_callbacks
from handlers.listen   import build_listen_handler
from handlers.profile  import register_profile_handlers
from handlers.leaderboard import register_leaderboard_handlers
from handlers.referral import register_referral_handlers
from handlers.notifications import (
    register_notification_handlers, send_daily_notifications,
    send_xatm_invitation, send_daily_top5,
    send_weekly_top10, send_monthly_top10, send_admin_daily_report,
)
from handlers.contact import build_contact_handler, register_contact_callbacks
from handlers.xatm import register_xatm_handlers
from handlers.achievements import register_achievement_handlers

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ─── APScheduler ──────────────────────────────────────────────────────────────

def setup_scheduler(app: Application):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    TZ = pytz.timezone(LOCAL_TZ)
    scheduler = AsyncIOScheduler(timezone=TZ)

    # Read saved notification settings (time + count)
    _, _, notif_count = get_notification_settings()
    notif_times = get_notification_times_list()
    logger.info(f"Notifications: {notif_times} x {notif_count}/day")

    async def _daily_notif():
        await send_daily_notifications(app.bot)

    app.bot_data["_daily_notif_fn"] = _daily_notif

    for i, (job_hour, job_minute) in enumerate(notif_times):
        scheduler.add_job(
            _daily_notif,
            CronTrigger(hour=job_hour, minute=job_minute, timezone=TZ),
            id=f"daily_notifications_{i}",
            replace_existing=True,
        )

    # Hourly leaderboard update
    async def _update_leaderboard():
        from services.firebase_service import get_all_users, update_leaderboard_entry
        users = get_all_users()
        for u in users:
            stats = u.get("stats", {})
            update_leaderboard_entry(
                u["telegram_id"],
                u.get("full_name", ""),
                u.get("username", ""),
                stats.get("total_verses_read", 0),
                stats.get("himmat_points", 0),
            )
        logger.info("Leaderboard updated")

    scheduler.add_job(
        _update_leaderboard,
        "interval", hours=1,
        id="leaderboard_update",
        replace_existing=True,
    )

    # Daily premium expiry check at 00:05
    async def _expire_premiums():
        from services.premium_service import check_and_expire_premiums
        check_and_expire_premiums()

    scheduler.add_job(
        _expire_premiums,
        CronTrigger(hour=0, minute=5, timezone=TZ),
        id="premium_expiry",
        replace_existing=True,
    )

    # Daily top-5 — 22:00 Tashkent = 17:00 UTC
    async def _daily_top5():
        await send_daily_top5(app.bot)

    scheduler.add_job(
        _daily_top5,
        CronTrigger(hour=17, minute=0, timezone=TZ),
        id="daily_top5",
        replace_existing=True,
    )

    # Admin detailed daily report — 23:00 Tashkent = 18:00 UTC
    async def _admin_report():
        await send_admin_daily_report(app.bot, admin_id=ADMIN_ID)

    scheduler.add_job(
        _admin_report,
        CronTrigger(hour=18, minute=0, timezone=TZ),
        id="admin_daily_report",
        replace_existing=True,
    )

    # Weekly top-10 — Sunday 21:00 Tashkent = 16:00 UTC
    async def _weekly_top10():
        await send_weekly_top10(app.bot)

    scheduler.add_job(
        _weekly_top10,
        CronTrigger(day_of_week="sun", hour=16, minute=0, timezone=TZ),
        id="weekly_top10",
        replace_existing=True,
    )

    # Monthly top-10 — last day of month 20:00 Tashkent = 15:00 UTC
    async def _monthly_top10():
        await send_monthly_top10(app.bot)

    scheduler.add_job(
        _monthly_top10,
        CronTrigger(day="last", hour=15, minute=0, timezone=TZ),
        id="monthly_top10",
        replace_existing=True,
    )

    # Xatm invitation — every Wednesday 12:00 Tashkent = 07:00 UTC
    async def _xatm_invite():
        await send_xatm_invitation(app.bot)

    scheduler.add_job(
        _xatm_invite,
        CronTrigger(day_of_week="wed", hour=7, minute=0, timezone=TZ),
        id="xatm_invitation",
        replace_existing=True,
    )

    # Flush achievement broadcast queue — every 30 minutes
    async def _flush_congrats():
        from handlers.achievements import flush_congrats_queue
        await flush_congrats_queue(app.bot)

    scheduler.add_job(
        _flush_congrats,
        "interval", minutes=30,
        id="flush_congrats_queue",
        replace_existing=True,
    )

    scheduler.start()
    app.bot_data["scheduler"] = scheduler
    logger.info("APScheduler started")
    return scheduler


# ─── Application Builder ──────────────────────────────────────────────────────

def build_application() -> Application:
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Conversation handlers first (they take priority)
    application.add_handler(build_onboarding_handler())
    application.add_handler(build_memorize_handler())
    application.add_handler(build_premium_handler())
    application.add_handler(build_admin_handler())
    application.add_handler(build_listen_handler())
    application.add_handler(build_contact_handler())

    # Simple handlers
    register_profile_handlers(application)
    register_leaderboard_handlers(application)
    register_referral_handlers(application)
    register_notification_handlers(application)
    register_premium_callbacks(application)
    register_admin_callbacks(application)
    register_contact_callbacks(application)
    register_xatm_handlers(application)
    register_achievement_handlers(application)

    return application


# ─── Startup notification ──────────────────────────────────────────────────────

async def notify_admin_startup(bot, mode: str):
    TZ = pytz.timezone(LOCAL_TZ)
    now = datetime.now(TZ).strftime("%d.%m.%Y %H:%M")
    from firebase_config import db as fb_db
    db_status = "✅ Firebase ulangan" if fb_db else "❌ Firebase ulanmadi"
    text = (
        f"{RELEASE_NOTES}\n"
        f"━━━━━━━━━━━━━━━━"
        f"\n🕐 Vaqt: {now} (Toshkent)"
        f"\n⚙️ Rejim: {'Webhook' if mode == 'webhook' else 'Polling'}"
        f"\n🔥 {db_status}"
    )
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text)
        logger.info(f"Admin startup notification sent to {ADMIN_ID}")
    except Exception as e:
        logger.warning(f"Could not notify admin on startup: {e}")


# ─── Health Server ─────────────────────────────────────────────────────────────

async def run_health_server():
    async def health(request):
        return web.Response(text="OK")

    aio_app = web.Application()
    aio_app.router.add_get("/health", health)
    aio_app.router.add_get("/", health)
    runner = web.AppRunner(aio_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Health server running on port {PORT}")


# ─── Polling Mode ──────────────────────────────────────────────────────────────

async def run_polling_async():
    await run_health_server()

    application = build_application()

    async with application:
        await application.bot.set_my_commands([
            BotCommand("start", "Boshlash / Asosiy menyu"),
            BotCommand("admin", "Admin panel"),
        ])
        backfill_xatm_numbers()
        setup_scheduler(application)
        await notify_admin_startup(application.bot, "polling")

        await application.start()
        logger.info("Starting bot in polling mode...")
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()
        await application.updater.stop()
        await application.stop()


# ─── Webhook Mode ──────────────────────────────────────────────────────────────

async def run_webhook():
    application = build_application()

    async def health(request):
        return web.Response(text="OK")

    async def webhook_handler(request: web.Request):
        try:
            data = await request.json()
            update = Update.de_json(data, application.bot)
            await application.process_update(update)
        except Exception as e:
            logger.error(f"Webhook handler error: {e}")
        return web.Response(text="OK")

    webhook_path = f"/webhook/{BOT_TOKEN}"
    full_url = f"{WEBHOOK_URL}{webhook_path}"

    await application.initialize()
    await application.start()
    await application.bot.set_webhook(full_url)
    logger.info(f"Webhook set: {full_url}")

    backfill_xatm_numbers()
    setup_scheduler(application)
    await notify_admin_startup(application.bot, "webhook")

    aio_app = web.Application()
    aio_app.router.add_get("/health", health)
    aio_app.router.add_post(webhook_path, webhook_handler)

    runner = web.AppRunner(aio_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Server running on port {PORT}")

    try:
        await asyncio.Event().wait()
    finally:
        await application.stop()
        await application.shutdown()


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if WEBHOOK_URL:
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling_async())
