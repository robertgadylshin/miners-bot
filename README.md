# The Miners — Task Reward Bot

Telegram bot for The Miners coffee shops. Baristas earn tokens by completing cleaning tasks from the daily checklist. Managers approve submissions via photo. Tokens are redeemed for rewards.

---

## Quick Setup (30 minutes total)

### Step 1 — Create the bot (5 min)
1. Open Telegram → find **@BotFather**
2. Send `/newbot`
3. Name: `The Miners Tasks`
4. Username: `theminers_tasks_bot` (or any available name)
5. Copy the token — looks like `7123456789:AAF...`

### Step 2 — GitHub (5 min)
1. Go to [github.com](https://github.com) → Sign up (free)
2. Click **New repository**
3. Name: `miners-bot`, set to **Public**
4. Upload all files from this folder

### Step 3 — Railway (10 min)
1. Go to [railway.app](https://railway.app) → **Sign in with GitHub**
2. Click **New Project** → **Deploy from GitHub repo** → select `miners-bot`
3. Click **+ New** → **Database** → **Add PostgreSQL** (Railway handles the rest)
4. Go to your service → **Variables** tab → add:
   - `BOT_TOKEN` = your token from BotFather
   - `SUPER_ADMIN_ID` = your personal Telegram user ID (get it from [@userinfobot](https://t.me/userinfobot))
5. Click **Deploy**

### Step 4 — Set up your first location (5 min)
1. Create a new Telegram group for the coffee shop
2. Add your bot to the group (search by username)
3. Send `/setup The Miners — Letna` in the group
4. Add a manager: `/addmanager @their_username`

That's it — the bot is live!

---

## How It Works

### For baristas
| Command | What it does |
|---------|-------------|
| `/tasks` | See today's task list with token values |
| `/balance` | Check token balance + recent earnings |
| `/rewards` | Browse all available rewards |
| `/redeem <name>` | Redeem a reward |

**To submit a task:**
1. Complete the task
2. Take a photo
3. Send the photo in the group chat
4. Write the task key as caption (e.g. `mon_fridges`)
5. Wait for manager approval — tokens arrive automatically

### For managers
Managers receive a private message with the photo + Approve/Reject buttons.
They also have:
- `/stats` — today's submissions, pending approvals, weekly leaderboard

### For super-admin
- `/setup <name>` — register a group as a location
- `/locations` — list all locations
- `/addlocation <chat_id> <name>` — add location by chat ID
- `/addmanager @username` — promote a barista to manager

---

## Token System

| Difficulty | Examples | Tokens |
|------------|----------|--------|
| 🟢 Easy | Check toilets, wash thermoses | 1 |
| 🟡 Standard | Wipe fridges, clean glasses | 2 |
| 🔴 Heavy | Deep Clean machine, Ice Maker | 3 |

Each task can only be submitted **once per day per person**.

---

## Rewards

TBA

---

## Anti-Fraud Measures
- Each task key can only be submitted **once per person per day**
- Manager must **manually approve** every photo
- The bot sends the photo directly to the manager for review
- Submission timestamps are recorded and stored
- All history is permanent and auditable

---

## Adding More Locations
For each new coffee shop:
1. Create a new Telegram group
2. Add the bot
3. Send `/setup Location Name` in that group
4. The bot isolates data per location automatically
