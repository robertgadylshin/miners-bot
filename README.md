# The Miners — Task Bot

Telegram bot for The Miners coffee shops. Baristas earn points by completing tasks from the daily checklist. Points go directly to The Miners loyalty card.

---

## How It Works for Baristas

Each shift has a task checklist. Complete a task, take a photo, send it in the group chat with the task key as caption. Your manager reviews the photo and approves it — points land on your loyalty card.

**Why 300 points per shift maximum?**
The cap keeps it fair across the whole team. One person can't stack every task in one shift while others get nothing. 300 points is designed to reward a full, active shift — not a speed run.

### Points per task

| Difficulty | Points | Examples |
|------------|--------|---------|
| 🟢 Quick | 100 | Check toilets, wash thermoses, clean spoons |
| 🟡 Standard | 200 | Wipe fridges, clean glasses, clean sinks |
| 🔴 Heavy | 300 | Ice Maker, EK Grinder, clean BUNN |

One heavy task already fills your shift cap — so pick based on what actually needs doing, not just the points.

---

## Submitting a Task

1. Complete the task
2. Take a photo (or multiple — send as an album)
3. Send in the group chat with the task key as caption
4. Example: `FRIDGES` or `fridges` — any case works

**Custom task:** if you did something not on today's list, send:
`CUSTOM I deep-cleaned the storage shelf`
Your manager will decide the points.

---

## Commands

### Barista
| Command | What it does |
|---------|-------------|
| `/tasks` | Today's checklist with point values |
| `/balance` | Your points, rank, and recent history |
| `/leaderboard` | Team ranking for the week or month |

### Manager
| Command | What it does |
|---------|-------------|
| `/stats` | Today's submissions and weekly top 5 |
| `/addmanager @username` | Promote a barista to manager |

Managers receive every submission as a private message with photo and Approve / Reject buttons. For custom tasks, managers choose the points: 100, 200, or 300.

### Admin
| Command | What it does |
|---------|-------------|
| `/setup <name>` | Register this group as a location |
| `/settimezone Europe/Prague` | Set local timezone for the group |
| `/locations` | List all locations |
| `/addlocation <chat_id> <name>` | Add location by chat ID |
| `/mystats` | Stats overview for all locations |

---

## Loyalty Card Points

Points earned in the bot are The Miners loyalty card points. To have points added to your card, ask your manager — they confirm the transfer manually. The bot tracks the balance; the card reflects it after the manager processes it.

---

## Anti-Fraud

- Each task can only be submitted **once per person per day**
- Every submission requires a **photo**
- Manager **manually approves** every photo before points are awarded
- Managers **cannot approve their own submissions**
- Daily limit of **300 points per person** is enforced at submission time

---

## Adding a New Location

1. Create a new Telegram group
2. Add the bot to the group
3. Send `/setup Location Name` in the group
4. Set timezone: `/settimezone Europe/Prague`
5. Add a manager: `/addmanager @username`
6. Done — data is fully isolated per location
