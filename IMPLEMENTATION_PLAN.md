# Hifz Bot — Full Technical Implementation Plan

**Project:** Qur'on Yodlaymiz Telegram Bot  
**Language:** Python 3.11+  
**Platform:** Telegram + Railway + Firebase  
**Interface language:** Uzbek (O'zbek Latin)  
**Date:** April 2026  

---

## 1. Project Overview

A Telegram bot that helps Muslims memorize the Quran (Hifz). Users work through ayahs with a spaced-repetition-style workflow (3 → 7 → 11 → accumulation rounds), earn Himmat points, unlock achievements, compete on leaderboards, and participate in group Quran completions (Jamoaviy Xatm). A premium tier unlocks unlimited daily ayahs and additional reciters.

---

## 2. Technology Stack

### Core Runtime
| Technology | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Primary language |
| python-telegram-bot | ≥21.0 | Telegram Bot API client (async) |
| aiohttp | 3.9.3 | Health server (Railway keepalive) |
| asyncio | stdlib | Async event loop |
| pytz | 2024.1 | Timezone handling (Asia/Tashkent) |

### Data Storage
| Technology | Version | Purpose |
|---|---|---|
| Firebase Firestore | Admin SDK 6+ | Primary database (NoSQL, real-time) |
| Firebase Cloud Storage | Admin SDK 6+ | Ayah photo storage |
| firebase-admin | ≥6.0.0 | Python SDK for Firebase |

### Scheduling
| Technology | Version | Purpose |
|---|---|---|
| APScheduler | 3.10.4 | In-process async job scheduler |

### External APIs
| Service | Purpose |
|---|---|
| mp3quran.net | Audio files for Quran recitation |
| qurancdn.com | Fallback audio CDN |
| Custom/internal | Arabic + Uzbek ayah text |

### Deployment
| Technology | Purpose |
|---|---|
| Railway | Cloud hosting, auto-deploy from git |
| GitHub | Version control, Railway trigger |
| nixpacks | Railway build system (auto-detect Python) |

### Dev Tools
| Technology | Purpose |
|---|---|
| python-dotenv | Load .env for local development |
| logging (stdlib) | Structured app logging |

---

## 3. Architecture

```
main.py
├── run_webhook()          ← Production (Railway)
│   ├── aiohttp web server (PORT 8080)
│   │   ├── GET  /health   ← Railway healthcheck
│   │   └── POST /webhook/<token>  ← Telegram updates
│   └── APScheduler (9 cron jobs)
└── run_polling_async()    ← Local development
    ├── aiohttp health server
    └── Updater.start_polling()

handlers/          ← Telegram update handlers
services/          ← Business logic + Firebase CRUD
utils/             ← Keyboards, message templates, helpers
config.py          ← All constants and env vars
firebase_config.py ← Firebase SDK init
```

### Data Flow (typical user action)
```
Telegram → webhook POST → Update.de_json()
  → ConversationHandler state machine
    → handler function
      → services/firebase_service.py (read/write Firestore)
      → services/gamification.py (points, streak, level)
      → bot.send_message() → Telegram API
```

---

## 4. Firebase Firestore Schema

### Collection: `users`
Document ID: `{telegram_id}` (string)

```
{
  telegram_id:       int,
  full_name:         str,
  username:          str,
  created_at:        timestamp,
  onboarding_complete: bool,
  referred_by:       str | null,
  referral_code:     str,        // 8-char unique code
  referral_count:    int,

  stats: {
    total_verses_read:   int,
    total_repetitions:   int,
    total_minutes:       int,
    himmat_points:       int,
    current_streak_days: int,
    longest_streak_days: int,
    last_activity_date:  str,    // "YYYY-MM-DD"
    daily_verses_today:  int,
    daily_date:          str,
    weekly_verses:       int,
    weekly_date:         str,
    monthly_verses:      int,
    monthly_date:        str,
  },

  premium: {
    is_active:   bool,
    expires_at:  timestamp | null,
    trial_used:  bool,
    activated_at: timestamp | null,
  },

  memorization_progress: {
    current_juz:         int,
    current_surah:       int,
    current_ayah:        int,
    completed_surahs:    [int],
    completed_juz:       [int],
    surah_{N}_ayah:      int,    // last stopped ayah per surah
  },

  notification_settings: {
    enabled:    bool,
    count:      int,             // 1-3 per day
    times:      [[hour, min]],
  },

  reciter: str,                  // default: "husary"
  location: str,
  daily_goal_minutes: int,
  initial_level: { juz_count: int, surahs: [] },
}
```

### Sub-collection: `users/{uid}/achievements`
Document ID: `{achievement_id}`

```
{
  unlocked_at:    timestamp,
  notified:       bool,
  congrats_count: int,
}
```

### Collection: `sessions`
Document ID: auto-generated

```
{
  user_id:    int,
  is_active:  bool,
  juz:        int,
  surah:      int,
  ayah:       int,
  started_at: timestamp,
}
```

### Collection: `leaderboard`
Document ID: `{telegram_id}`

```
{
  telegram_id:        int,
  full_name:          str,
  username:           str,
  total_verses_read:  int,
  himmat_points:      int,
  updated_at:         timestamp,
}
```

### Collection: `xatm_groups`
Document ID: auto-generated

```
{
  title:        str,
  created_by:   int,
  created_at:   timestamp,
  status:       "active" | "completed",
  total_juz:    30,
  members: {
    {telegram_id}: {
      full_name: str,
      juz_list: [int],
      status: "pending" | "completed",
    }
  },
}
```

### Collection: `premium_requests`
Document ID: auto-generated

```
{
  user_id:     int,
  username:    str,
  full_name:   str,
  file_id:     str,            // Telegram photo file_id
  status:      "pending" | "approved" | "rejected",
  created_at:  timestamp,
  admin_message_id: int,
}
```

### Collection: `achievement_broadcast_queue`
Document ID: auto-generated

```
{
  recipient_id:  int,
  achiever_id:   int,
  achiever_name: str,
  ach_id:        str,
  created_at:    timestamp,
  sent:          bool,
}
```

### Collection: `achievement_queue_daily`
Document ID: `{user_id}_{YYYY-MM-DD}`

```
{
  count: int,    // notifications sent today to this user
}
```

### Collection: `notification_settings` (global)
Document ID: `main`

```
{
  times:    [[hour, min]],
  count:    int,
}
```

---

## 5. Handler Modules

### 5.1 `handlers/start.py` — Onboarding
**ConversationHandler** with 7 states:

| State | Trigger | Handler |
|---|---|---|
| `ONBOARDING_START` | Button tap | `onboarding_begin()` |
| `ONBOARDING_NAME` | Text message | `onboarding_name()` |
| `ONBOARDING_LEVEL` | Callback (level_X) | `onboarding_level()` |
| `ONBOARDING_SURAHS` | Text message | `onboarding_surahs()` |
| `ONBOARDING_LOCATION` | Text message | `onboarding_location()` |
| `ONBOARDING_GOAL` | Text message | `onboarding_goal()` |
| `ONBOARDING_TIME` | Callback (time_X) | `onboarding_time()` |

On completion:
1. Save profile to Firestore
2. Auto-activate 1-day trial
3. Award onboarding Himmat points
4. Process referral (if any) — award both users REFERRAL_BONUS points
5. Send admin alert: new user name, ID, total user count

### 5.2 `handlers/memorize.py` — Memorization Flow
**ConversationHandler** — the core loop:

```
📚 Yodlash button
  → Juz selection (1-30)
    → Direction (forward/backward)
      → Reciter selection (premium only if non-Husary)
        → Surah selection (list for that juz)
          → Resume from surah_{N}_ayah if > 1
            ┌─ Show ayah (Arabic + Uzbek)
            │   └─ 3 repetitions (✅×3)
            │       └─ 7 repetitions (✅×7)
            │           └─ 11 repetitions (✅×11)
            │               └─ Accumulation round (all ayahs so far)
            └─ Next ayah → loop (or surah complete)
```

**Daily limit:** Free users — 5 ayahs/day. Premium — unlimited.  
**Per-surah resume:** `memorization_progress.surah_{N}_ayah` stores last ayah, resumes on re-entry.  
**On each ayah complete:** Award Himmat, update streak, check achievements (async).  
**On surah complete:** Award bonus Himmat (`surah_ayah_count × HIMMAT_PER_SURAH_COMPLETE_MULTIPLIER`), store in `completed_surahs`.

### 5.3 `handlers/premium.py` — Subscriptions
- **Trial:** 1-day free, one-time per user. Button in premium menu.
- **Purchase:** User sends payment screenshot → queued for admin review.
- **Admin approval:** Admin sees photo + user info in private chat, approves/rejects via inline buttons.
- **On approval:** 30-day premium activated, user notified.

### 5.4 `handlers/admin.py` — Admin Panel
Entry: `/admin` command (ADMIN_ID only). Features:
- View bot stats (total users, active today, premium count, total ayahs read)
- Search user by username/ID
- Grant premium (7 or 30 days)
- Broadcast message to all users
- Upload ayah photos to Firebase Storage
- Configure notification times/count
- Approve/reject pending premium requests

### 5.5 `handlers/profile.py` — User Profile
Accessible via "👤 Sahifam" button. Shows:
- Name, level, Himmat points
- Stats by period: today / this week / this month / this year
- Streak days
- Button: "🏆 Yutuq va Mukofotlarim" → achievements page
- Settings: notifications on/off, daily count

### 5.6 `handlers/leaderboard.py` — Rankings
- Tabs: Haftalik / Oylik / Yillik / Umum
- Top 50 users ranked by Himmat points
- User's own rank shown at bottom even if outside top 50
- Updated hourly by APScheduler

### 5.7 `handlers/xatm.py` — Jamoaviy Xatm (Group Quran Completion)
- Create a new Xatm group, assign juz to members
- Members mark their juz as complete
- Group progress bar
- On full completion: group celebration message
- Share invite link via deep link: `t.me/bot?start=xatm_{id}`

### 5.8 `handlers/achievements.py` — Achievements System
**35 achievements** across 10 categories:

| Category | Count | Examples |
|---|---|---|
| Oyat Yodlash | 9 | First ayah, 10/50/100/300/500/1000/3000/6236 ayahs |
| Surahlar | 4 | 1/5/10/20 surahs completed |
| Juzlar | 4 | 1/5/15/30 juz completed |
| Streak | 5 | 3/7/14/30/100 day streak |
| Himmat Ball | 4 | 500/2000/5000/10000 points |
| Takrorlar | 3 | 100/1000/10000 repetitions |
| Vaqt | 3 | 1/10/100 hours memorizing |
| Ijtimoiy | 3 | 1/5/10 referrals |
| Jamoaviy Xatm | 2 | Joined / Completed xatm |
| Premium | 1 | Activated premium |

**Unlock flow:**
1. `check_and_notify_achievements(bot, user_id)` called after any activity
2. `check_new_achievements()` evaluates all unearned achievements against user data
3. New achievements saved to `users/{uid}/achievements/`
4. Bonus XP awarded immediately
5. User notified directly (personal message)
6. `broadcast_achievement()` writes one queue doc per other user into `achievement_broadcast_queue`

**Broadcast queue flush (every 30 min):**
1. Query all unsent docs, group by recipient
2. Skip recipients with active memorize session (`get_active_session()`)
3. Send max 10 notifications per user per day
4. Track daily count in `achievement_queue_daily/{uid}_{date}`
5. Mark sent docs as `sent: true`

**Congrats counter:**
- Each "🤝 Tabriklash" tap increments `congrats_count` on the achievement doc
- Button updates to "✅ Tabrikladingiz! (N)" showing real-time count
- Count also shown in achievements page next to unlocked achievements

### 5.9 `handlers/notifications.py` — Scheduled Broadcasts
- `send_daily_notifications(bot)` — Personalized daily reminder with user's progress
- `send_daily_top5(bot)` — Top 5 users of the day sent to everyone (22:00 Tashkent)
- `send_weekly_top10(bot)` — Weekly top 10 (Sunday 21:00 Tashkent)
- `send_monthly_top10(bot)` — Monthly top 10 (last day of month 20:00 Tashkent)
- `send_xatm_invitation(bot)` — Invite all to join active xatm (Wednesdays 12:00)
- `send_admin_daily_report(bot, admin_id)` — Per-user activity digest (23:00 Tashkent)
- `flush_congrats_queue(bot)` — Achievement notification delivery (every 30 min)

### 5.10 `handlers/listen.py` — Audio Listening
- Choose reciter and surah
- Bot sends audio file from mp3quran.net CDN
- Does not count toward daily memorization limit

### 5.11 `handlers/referral.py`
- Generate/display user's referral link: `t.me/bot?start=ref_{code}`
- Referral code is 8-char random string created at user signup
- Both referrer and new user earn `REFERRAL_BONUS` Himmat points

### 5.12 `handlers/contact.py`
- User sends message → forwarded to admin
- Admin can reply via bot (reply button on forwarded message)

---

## 6. Services

### `services/firebase_service.py`
All Firestore reads/writes. Key responsibilities:
- User CRUD (`get_user`, `create_user`, `update_user`, `set_onboarding_complete`)
- Stats update (`update_user_stats` — updates today/week/month/year counters)
- Leaderboard (`update_leaderboard_entry`, `get_leaderboard`)
- Memorization progress (`save_memorization_progress`, `get_memorization_progress`)
- Sessions (`get_active_session`, `create_session`, `end_session`)
- Notifications config (`get_notification_settings`, `get_notification_times_list`)
- Premium requests (`create_premium_request`, `update_premium_request`)
- Referrals (`find_user_by_referral_code`, `increment_referral_count`)
- Xatm groups (`get_xatm_group`, `update_xatm_member`)
- Backfill utilities (`backfill_xatm_numbers`)

### `services/gamification.py`
Pure business logic, no async:
- **Level system:** 7 levels from 0 to 10000 Himmat. `get_level(points)` returns (number, name).
- **Streak system:** Checks `last_activity_date`. Same day = no change. Yesterday = +1. Gap = reset. Milestones at 3/7/14/30/100 days award bonus Himmat.
- **Points schedule:**
  - 3 reps: 2 points
  - 7 reps: 5 points
  - 11 reps: 8 points
  - Accumulation: 3 points
  - Ayah complete: 15 points
  - Surah complete: `ayah_count × 5` points
  - Juz complete: 500 points
  - Onboarding: defined by `ONBOARDING_BONUS`
- `award_points(user_id, points, reason)` — writes to Firestore, returns level-up info if applicable

### `services/premium_service.py`
- `activate_trial()` — sets `premium.is_active = True`, `expires_at = now + 1 day`, `trial_used = True`
- `activate_premium(days)` — extends from `expires_at` or from now; sets `is_active = True`
- `is_premium(user_dict)` — checks `is_active AND expires_at > now`
- `check_and_expire_premiums()` — scans all users, sets `is_active = False` if `expires_at < now`. Called daily at 00:05.

### `services/quran_api.py`
- Fetch ayah text (Arabic + Uzbek translation) from internal/external source
- Build audio URL for reciter: `https://cdn.islamic.network/quran/audio/128/{reciter_id}/{global_ayah_number}.mp3`
- Map (surah, ayah) → global ayah number
- Surah metadata: names, ayah counts, juz mapping

---

## 7. APScheduler Jobs

| Job ID | Schedule | Function | Description |
|---|---|---|---|
| `daily_notifications_0..N` | Configurable cron | `send_daily_notifications` | Daily reminders (time/count from Firestore settings) |
| `leaderboard_update` | Every 1 hour | `_update_leaderboard` | Sync all users' stats to leaderboard collection |
| `premium_expiry` | Daily 00:05 | `check_and_expire_premiums` | Expire overdue premium subscriptions |
| `daily_top5` | Daily 17:00 UTC (22:00 Tashkent) | `send_daily_top5` | Broadcast top 5 of the day to all users |
| `admin_daily_report` | Daily 18:00 UTC (23:00 Tashkent) | `send_admin_daily_report` | Detailed per-user activity digest to admin |
| `weekly_top10` | Sunday 16:00 UTC (21:00 Tashkent) | `send_weekly_top10` | Weekly top 10 announcement |
| `monthly_top10` | Last day of month 15:00 UTC (20:00 Tashkent) | `send_monthly_top10` | Monthly top 10 announcement |
| `xatm_invitation` | Wednesday 07:00 UTC (12:00 Tashkent) | `send_xatm_invitation` | Invite all users to active xatm group |
| `flush_congrats_queue` | Every 30 minutes | `flush_congrats_queue` | Deliver queued achievement notifications |

All jobs use `AsyncIOScheduler` with `timezone=Asia/Tashkent`.

---

## 8. Gamification Design

### Himmat Points (XP)
The single currency. Earned by:
- Repetition rounds (2 / 5 / 8 points per round)
- Ayah completion (15 points)
- Surah completion (ayah_count × 5)
- Juz completion (500 points)
- Streak milestones (20 to 2000 points)
- Achievements (50 to 50,000 bonus points)
- Referrals (15 points each side)
- Onboarding completion

### Level Progression
```
Level 1 🌱 Mubtadi         — 0 pts
Level 2 📖 Tolibul Ilm     — 100 pts
Level 3 🔆 Mushtoq         — 500 pts
Level 4 ⭐ Hafiz Yo'li     — 1,000 pts
Level 5 🌙 Qur'on Muhhibi  — 2,500 pts
Level 6 🌟 Aziz Hofiz      — 5,000 pts
Level 7 👑 Qur'on Sultoni  — 10,000 pts
```
Level-up is detected on every `award_points()` call and notified to the user inline.

### Streak System
- Tracked via `last_activity_date` field
- Consecutive day activity extends streak
- Missing a day resets streak to 0
- Longest streak is always preserved
- Streak milestones: 3, 7, 14, 30, 100 days → bonus Himmat

### Free vs Premium
| Feature | Free | Premium |
|---|---|---|
| Daily ayahs | 5 | Unlimited |
| Reciters | Husary only | All 5 reciters |
| Price | — | Manual payment (30 days) |
| Trial | 1 day (one-time) | — |

---

## 9. Deployment

### Railway Configuration
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python main.py"
restartPolicyType = "always"
```

### Environment Variables (Railway secrets)
| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram bot token |
| `WEBHOOK_URL` | Full Railway app URL (e.g. `https://app.up.railway.app`) |
| `ADMIN_ID` | Telegram user ID of admin |
| `FIREBASE_CREDENTIALS` | Firebase service account JSON (inline string) |
| `PORT` | 8080 (default) |

### Startup Sequence
1. `firebase_config.py` imported → Firebase Admin SDK initialized
2. `build_application()` → all handlers registered
3. `backfill_xatm_numbers()` — data migration if needed
4. `setup_scheduler(app)` → 9 jobs registered, scheduler started
5. `application.bot.set_webhook(url)` — webhook registered with Telegram
6. `notify_admin_startup()` — send startup message + release notes to admin
7. `aiohttp` server starts on PORT 8080
8. Event loop runs forever

### Local Development
- Set `WEBHOOK_URL=""` in `.env` → polling mode activated
- Run `python main.py`
- Uses `Updater.start_polling()` instead of webhook

---

## 10. Security & Access Control

- **Admin commands** check `query.from_user.id == ADMIN_ID` before any action
- **Premium gating** in memorize flow: daily limit enforced before each new ayah
- **Reciter gating**: only Husary available for free users; callback pattern enforced in handler
- **Self-referral prevention**: referral code ignored if `referrer_id == new_user_id`
- **Photo receipts**: stored as Telegram `file_id` only — no direct file download on bot side
- **No sensitive data in logs**: user IDs logged, never tokens or credentials

---

## 11. Key Design Decisions

### Why Firestore (not SQLite/Postgres)?
- Serverless pricing — no always-on DB cost
- Real-time capabilities for potential future web dashboard
- Sub-collections for achievements keep schema clean
- Railway doesn't provide persistent disk by default

### Why APScheduler (not Telegram JobQueue)?
- More control over cron expressions (last day of month, etc.)
- Can be paused/inspected at runtime
- `AsyncIOScheduler` integrates cleanly with python-telegram-bot v21's async loop

### Why webhook (not polling) in production?
- Lower latency (Telegram pushes updates instantly)
- No polling overhead (Railway saves CPU/RAM)
- Cleaner shutdown — no dangling connections

### Why queue for achievement broadcasts?
- Burst protection: a single user completing 10 achievements would otherwise flood all users simultaneously
- Respects memorization sessions — notifications wait until user exits
- Rate-limited to 10/day per recipient regardless of activity spikes
- Queue survives bot restarts (Firestore-backed)

### Why per-surah resume (`surah_{N}_ayah`)?
- Previous design only resumed `current_surah` — switching surahs reset progress
- Per-surah key allows user to work on multiple surahs in parallel
- Backward-compatible: falls back to `current_ayah` if per-surah key missing

---

## 12. File Structure

```
hifz-bot/
├── main.py                     # Entry point: webhook/polling + scheduler
├── config.py                   # All constants, env vars, conversation states
├── firebase_config.py          # Firebase Admin SDK initialization
├── requirements.txt
├── railway.toml
│
├── handlers/
│   ├── start.py                # /start + 7-step onboarding ConversationHandler
│   ├── memorize.py             # Core memorization loop ConversationHandler
│   ├── listen.py               # Audio listening ConversationHandler
│   ├── premium.py              # Premium menu + receipt submission ConversationHandler
│   ├── admin.py                # Admin panel ConversationHandler + callbacks
│   ├── profile.py              # Profile + stats + settings
│   ├── leaderboard.py          # Leaderboard display (4 periods)
│   ├── referral.py             # Referral link generation + sharing
│   ├── notifications.py        # Scheduled send functions + user notification prefs
│   ├── xatm.py                 # Jamoaviy Xatm group management
│   ├── achievements.py         # 35 achievements + broadcast queue + congrats UI
│   └── contact.py              # User ↔ admin messaging
│
├── services/
│   ├── firebase_service.py     # All Firestore CRUD (100+ functions)
│   ├── gamification.py         # Points, levels, streaks (pure logic, no async)
│   ├── premium_service.py      # Trial/premium activation + expiry
│   ├── quran_api.py            # Ayah text, audio URL, surah metadata
│   └── stats_service.py        # Aggregate stats helpers
│
└── utils/
    ├── keyboards.py            # All InlineKeyboardMarkup + ReplyKeyboardMarkup builders
    ├── messages.py             # All message text templates (Uzbek)
    ├── helpers.py              # Misc utility functions
    └── decorators.py           # Handler decorators (e.g. premium_required)
```

---

## 13. Data Flow Examples

### Example: User completes an ayah
```
memorize.py: rep_11_done() callback
  → services/gamification.py: award_points(user_id, 8, "rep_11")
      → firebase_service.py: update_user(user_id, {stats.himmat_points: +8})
      → returns level_up if crossed threshold
  → firebase_service.py: update_user_stats(user_id, verses=1, reps=11, minutes=3)
  → firebase_service.py: save_memorization_progress(user_id, surah=X, ayah=Y+1)
      → also writes memorization_progress.surah_X_ayah = Y+1
  → asyncio.ensure_future(
        check_and_notify_achievements(bot, user_id)
    )
      → check_new_achievements() evaluates all 35 conditions
      → if unlocked: save_achievement(), award_points(bonus_xp)
      → notify user directly
      → broadcast_achievement() → writes N queue docs to Firestore
  → bot.send_message(next ayah)
```

### Example: flush_congrats_queue runs (every 30 min)
```
APScheduler triggers _flush_congrats()
  → query achievement_broadcast_queue WHERE sent == false ORDER BY created_at LIMIT 2000
  → group docs by recipient_id
  → for each recipient:
      → get_active_session(recipient_id) — skip if memorizing
      → check achievement_queue_daily/{uid}_{today} — skip if already sent 10 today
      → for each doc (up to 10 remaining):
          → read congrats_count from achiever's achievement doc
          → build message with "🤝 Tabriklash (N)" button
          → bot.send_message(recipient_id, ...)
          → mark doc sent = true
          → increment achievement_queue_daily count
```

---

## 14. Limitations & Known Constraints

| Constraint | Details |
|---|---|
| Firestore free tier | 50k reads / 20k writes / 20k deletes per day. Heavy broadcast can exhaust write quota quickly with large user base. |
| Telegram rate limit | 30 messages/second global, 1 message/second per chat. Broadcasts to 1000+ users need delay/batching. |
| APScheduler in-process | Scheduler lives in the same process as the bot. If Railway restarts the process, all in-memory state is lost (but jobs reload from config on restart). |
| No persistent local storage | Railway does not guarantee persistent disk. All state must live in Firestore. |
| Manual payment verification | Receipt verification is manual (admin approves photo). No payment gateway integration. |
| Audio from third-party CDN | Audio URLs from mp3quran.net/qurancdn — subject to CDN availability. |

---

## 15. Future Improvements (Out of Scope for Current Version)

- Stripe / PayMe / Click payment gateway integration
- Webhook-based Firestore triggers (Cloud Functions) instead of in-process polling for achievements
- Web dashboard for admin (Firebase Hosting + React)
- Multi-language support (Russian, English)
- Voice message recognition for recitation verification
- Spaced repetition scheduling (SM-2 algorithm) for review sessions
- Push notifications via Firebase Cloud Messaging (for users who leave Telegram)
