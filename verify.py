import sys
sys.path.insert(0, '.')

from src.database.db import init_db
init_db()
print("DB migration OK")

from src.bot import build_app
print("Bot import OK")

from src.handlers import quiz, flow
print("Quiz + Flow import OK")

from src.database import db
db.upsert_user(999, "TestUser")
db.ensure_settings(999)
db.ensure_gamification(999)

ok = db.add_reminder(999, "08:04")
print(f"Reminder add: {ok}")

rems = db.get_reminders(999)
times = [r["reminder_time"] for r in rems]
print(f"Reminders: {times}")

users = db.get_all_users_for_reminder("08:04")
names = [u["name"] for u in users]
print(f"Users at 08:04: {names}")

# Cleanup test user
import sqlite3
from pathlib import Path
conn = sqlite3.connect("hifz.db")
conn.execute("DELETE FROM gamification WHERE user_id=999")
conn.execute("DELETE FROM reminders WHERE user_id=999")
conn.execute("DELETE FROM settings WHERE user_id=999")
conn.execute("DELETE FROM users WHERE id=999")
conn.commit()
conn.close()

print("ALL CHECKS PASSED!")
