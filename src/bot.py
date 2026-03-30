"""Bot factory — registers all handlers (correct order)."""
from telegram.ext import Application

from src.handlers import (onboarding, profile, navigator, settings,
                          leaderboard, gamification, quiz, flow, premium, xatm)
from src.handlers import achievements

def build_app(token: str) -> Application:
    app = Application.builder().token(token).build()

    # Order matters: specific callback handlers first, text/voice/photo last
    onboarding.register(app)     # lang:, menu: callbacks
    profile.register(app)        # profile: callbacks
    navigator.register(app)      # nav: callbacks
    leaderboard.register(app)    # lb: callbacks
    quiz.register(app)           # quiz: callbacks
    flow.register(app)           # flow: callbacks + VOICE handler
    premium.register(app)        # premium: callbacks + PHOTO handler
    xatm.register(app)           # xatm: callbacks
    achievements.register(app)   # congrats: callbacks
    settings.register(app)       # settings: callbacks + TEXT handler (always last)

    return app
