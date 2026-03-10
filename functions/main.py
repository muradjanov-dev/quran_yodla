"""
functions/main.py — Firebase Cloud Functions entry point for webhook.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from firebase_functions import https_fn, scheduler_fn
from firebase_admin import initialize_app

from telegram import Update, Bot
from telegram.ext import Application, ApplicationBuilder

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8770428749:AAEM1frAdej02vdp6LW7wPgvbthXa6idH8o")

# Initialize Firebase Admin SDK once
try:
    initialize_app()
except Exception:
    pass  # Already initialized

# Application singleton (warm between cold starts)
_application: Application | None = None


def _get_application() -> Application:
    global _application
    if _application is None:
        from handlers.start       import build_onboarding_handler
        from handlers.memorize    import build_memorize_handler
        from handlers.premium     import build_premium_handler, register_premium_callbacks
        from handlers.admin       import build_admin_handler, register_admin_callbacks
        from handlers.listen      import build_listen_handler
        from handlers.profile     import register_profile_handlers
        from handlers.leaderboard import register_leaderboard_handlers
        from handlers.referral    import register_referral_handlers
        from handlers.notifications import register_notification_handlers

        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(build_onboarding_handler())
        app.add_handler(build_memorize_handler())
        app.add_handler(build_premium_handler())
        app.add_handler(build_admin_handler())
        app.add_handler(build_listen_handler())
        register_profile_handlers(app)
        register_leaderboard_handlers(app)
        register_referral_handlers(app)
        register_notification_handlers(app)
        register_premium_callbacks(app)
        register_admin_callbacks(app)
        _application = app

    return _application


@https_fn.on_request(region="us-central1", memory=512, timeout_sec=60)
def webhook(req: https_fn.Request) -> https_fn.Response:
    """Main Telegram webhook endpoint."""
    if req.method != "POST":
        return https_fn.Response("OK", status=200)

    try:
        data   = req.get_json(force=True)
        app    = _get_application()
        update = Update.de_json(data, app.bot)

        # Run the async handler in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_process(app, update))
        finally:
            loop.close()

        return https_fn.Response("OK", status=200)
    except Exception as e:
        print(f"Webhook error: {e}")
        return https_fn.Response("Error", status=500)


async def _process(app: Application, update: Update):
    async with app:
        await app.process_update(update)


@https_fn.on_request(region="us-central1")
def set_webhook(req: https_fn.Request) -> https_fn.Response:
    """One-time call to register webhook URL with Telegram."""
    import requests as req_lib
    project_id    = os.environ.get("GCLOUD_PROJECT", "YOUR_PROJECT_ID")
    function_url  = f"https://us-central1-{project_id}.cloudfunctions.net/webhook"
    result = req_lib.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
        params={"url": function_url}
    )
    return https_fn.Response(result.text, status=200)


@scheduler_fn.on_schedule(
    schedule="0 8 * * *",
    timezone=scheduler_fn.Timezone("Asia/Tashkent"),
    region="us-central1"
)
def daily_notifications(event: scheduler_fn.ScheduledEvent) -> None:
    """Runs every day at 08:00 Tashkent to send notifications."""
    from handlers.notifications import send_daily_notifications
    app = _get_application()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(send_daily_notifications(app.bot))
    finally:
        loop.close()
