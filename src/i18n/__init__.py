"""i18n helper — resolves user language and returns the correct string."""
from src.i18n import en, uz
from src.database import db

_MODULES = {"en": en, "uz": uz}

def t(user_id: int, key: str, **kwargs) -> str:
    """Get translated string for user_id."""
    user = db.get_user(user_id)
    lang = user["language"] if user else "en"
    module = _MODULES.get(lang, en)
    template = module.STRINGS.get(key, en.STRINGS.get(key, f"[{key}]"))
    try:
        return template.format(**kwargs)
    except KeyError:
        return template

def badge_display(user_id: int, badge_key: str) -> str:
    user = db.get_user(user_id)
    lang = user["language"] if user else "en"
    module = _MODULES.get(lang, en)
    return module.BADGE_DISPLAY.get(badge_key, badge_key)

def league_display(user_id: int, league_key: str) -> str:
    user = db.get_user(user_id)
    lang = user["language"] if user else "en"
    module = _MODULES.get(lang, en)
    return module.LEAGUE_DISPLAY.get(league_key, league_key)

def plan_label(user_id: int, plan_key: str) -> str:
    user = db.get_user(user_id)
    lang = user["language"] if user else "en"
    module = _MODULES.get(lang, en)
    return module.PLAN_LABELS.get(plan_key, plan_key)
