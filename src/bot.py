"""Bot factory — registers all handlers (correct order)."""
from telegram.ext import Application

from src.handlers import (onboarding, profile, navigator, settings,
                          leaderboard, gamification, quiz, flow, premium, xatm)
from src.handlers import achievements
from src.handlers import tajweed

def build_app(token: str, post_init=None) -> Application:
    builder = Application.builder().token(token)
    if post_init:
        builder = builder.post_init(post_init)
    app = builder.build()

    # Order matters: specific callback handlers first, text/voice/photo last
    onboarding.register(app)     # lang:, menu: callbacks
    profile.register(app)        # profile: callbacks
    navigator.register(app)      # nav: callbacks
    leaderboard.register(app)    # lb: callbacks
    quiz.register(app)           # quiz: callbacks
    tajweed.register(app)        # tajweed: command + callbacks + VOICE (group=1, high priority)
    flow.register(app)           # flow: callbacks + VOICE handler (default group)
    premium.register(app)        # premium: callbacks + PHOTO handler
    xatm.register(app)           # xatm: callbacks
    achievements.register(app)   # congrats: callbacks
    settings.register(app)       # settings: callbacks + TEXT handler (always last)

    return app
