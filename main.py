"""
main.py — Application entry point with webhook setup and APScheduler.
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
import firebase_config  # noqa: E402 — ensures Firebase is initialized at startup
from services.firebase_service import get_notification_settings, get_notification_times_list  # noqa

# ─── Release Notes (sent to admin on every startup) ───────────────────────────
RELEASE_NOTES = """
🚀 BOT ISHGA TUSHDI — v1.0.0

✅ YANGI XUSUSIYATLAR:
• /start onboarding — 5 qadam, referral tizimi
• Yodlash: 3→7→11→jamlash algoritmi (to'liq)
• Audio: AlQuran.cloud CDN (128kbps mp3)
• Tinglash: 8 ta qori, to'liq suralari
• Sahifam: bugun/hafta/oy/yil statistika
• Reyting: Top 50 + foydalanuvchi o'rni
• Premium: chek → admin tasdiqlash/rad etish
• Trial: 3 kunlik bepul sinov
• Gamification: 7 daraja, 40+ himmat qoidasi
• Streak: 3/7/14/30/100 kun bonuslari
• Referal: +15 himmat ball ikki tomonga
• Kunlik xabar: 5 tur (soat 08:00 Toshkent)
• Admin panel: broadcast, user boshqarish
• Firebase: Firestore + APScheduler
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
from handlers.notifications import register_notification_handlers, send_daily_notifications
from handlers.contact import build_contact_handler, register_contact_callbacks

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
    logger.info(f"Notifications: {notif_times} × {notif_count}/day")

    # Daily notifications — support 1-5 per day with explicit or auto-spaced times
    async def _daily_notif():
        await send_daily_notifications(app.bot)

    # Store fn reference so admin count-change handler can re-use it
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

    scheduler.start()
    app.bot_data["scheduler"] = scheduler  # accessible from admin handler
    logger.info("APScheduler started")
    return scheduler


# ─── Application Builder ──────────────────────────────────────────────────────

def build_application(post_init=None) -> Application:
    builder = ApplicationBuilder().token(BOT_TOKEN)
    if post_init:
        builder = builder.post_init(post_init)
    application = builder.build()

    # Conversation handlers (must be added first — they take priority)
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

    return application


# ─── Webhook Mode (Production) ─────────────────────────────────────────────────

async def run_webhook():
    application = build_application()

    async def health(request):
        return web.Response(text="OK")

    async def webhook_handler(request: web.Request):
        try:
            data   = await request.json()
            update = Update.de_json(data, application.bot)
            await application.process_update(update)
        except Exception as e:
            logger.error(f"Webhook handler error: {e}")
        return web.Response(text="OK")

    # Set bot commands
    await application.bot.set_my_commands([
        BotCommand("start",   "Boshlash / Asosiy menyu"),
        BotCommand("admin",   "Admin panel"),
    ])

    # Set webhook
    webhook_path = f"/webhook/{BOT_TOKEN}"
    full_url     = f"{WEBHOOK_URL}{webhook_path}"

    await application.initialize()
    await application.start()
    await application.bot.set_webhook(full_url)
    logger.info(f"Webhook set: {full_url}")

    setup_scheduler(application)
    await notify_admin_startup(application.bot, "webhook")

    # aiohttp server
    aio_app = web.Application()
    aio_app.router.add_get("/health", health)
    aio_app.router.add_post(webhook_path, webhook_handler)

    runner = web.AppRunner(aio_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Server running on port {PORT}")

    # Keep running
    try:
        await asyncio.Event().wait()
    finally:
        await application.stop()
        await application.shutdown()


# ─── Polling Mode (Development/Testing) ───────────────────────────────────────

async def notify_admin_startup(bot, mode: str):
    """Send a startup message ONLY to the admin with release notes."""
    TZ  = pytz.timezone(LOCAL_TZ)
    now = datetime.now(TZ).strftime("%d.%m.%Y %H:%M")
    from firebase_config import db
    db_status = "✅ Firebase ulangan" if db else "❌ Firebase ulanmadi"
    text = (
        f"{RELEASE_NOTES}\n"
        f"━━━━━━━━━━━━━━━━"
        f"\n🕐 Vaqt: {now} (Toshkent)"
        f"\n⚙️ Rejim: {'Webhook' if mode == 'webhook' else 'Polling (lokal)'}"
        f"\n🔥 {db_status}"
    )
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text)
        logger.info(f"Admin startup notification sent to {ADMIN_ID}")
    except Exception as e:
        logger.warning(f"Could not notify admin on startup: {e}")


async def run_health_server():
    """Minimal HTTP server for Railway/Render healthchecks (polling mode only)."""
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


async def run_polling_async():
    """Polling mode with background health server for Railway healthchecks."""
    await run_health_server()

    application = build_application()

    async with application:
        await application.bot.set_my_commands([
            BotCommand("start", "Boshlash / Asosiy menyu"),
            BotCommand("admin", "Admin panel"),
        ])
        setup_scheduler(application)
        await notify_admin_startup(application.bot, "polling")

        await application.start()
        logger.info("Starting bot in polling mode...")
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()  # run forever
        await application.updater.stop()
        await application.stop()


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if WEBHOOK_URL:
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling_async())
