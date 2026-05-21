from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, date

from db import get_db
from tasks import get_today_tasks, get_tokens_for_task, find_task_by_key


async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    db = get_db()
    location = db.execute(
        "SELECT * FROM locations WHERE chat_id = ?", (chat.id,)
    ).fetchone()
    if not location:
        return
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        db.execute("""
            INSERT OR IGNORE INTO users (telegram_id, username, full_name, location_id, role)
            VALUES (?, ?, ?, ?, 'barista')
        """, (member.id, member.username or '', member.full_name, location['id']))
    db.commit()


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = get_db()

    location = db.execute(
        "SELECT * FROM locations WHERE chat_id = ?", (chat.id,)
    ).fetchone()
    if not location:
        await update.message.reply_text("⚠️ This group is not set up yet. Ask admin to run /setup.")
        return

    db.execute("""
        INSERT OR IGNORE INTO users (telegram_id, username, full_name, location_id, role)
        VALUES (?, ?, ?, ?, 'barista')
    """, (user.id, user.username or '', user.full_name, location['id']))
    db.commit()

    tasks = get_today_tasks()
    today_str = date.today().strftime('%A, %d %B %Y')

    submitted = db.execute("""
        SELECT task_key, status FROM task_submissions
        WHERE user_id = (SELECT id FROM users WHERE telegram_id = ? AND location_id = ?)
        AND date(submitted_at) = date('now')
    """, (user.id, location['id'])).fetchall()
    submitted_keys = {row['task_key']: row['status'] for row in submitted}

    lines = [
        f"Tasks for {today_str}",
        f"📍 {location['name']}",
        "",
    ]

    groups = [
        ("🔴 Heavy — 3 tokens", [t for t in tasks if t['difficulty'] == 'hard']),
        ("🟡 Standard — 2 tokens", [t for t in tasks if t['difficulty'] == 'medium']),
        ("🟢 Quick — 1 token", [t for t in tasks if t['difficulty'] == 'easy']),
    ]

    for label, items in groups:
        if not items:
            continue
        lines.append(f"*{label}*")
        for t in items:
            status = submitted_keys.get(t['key'])
            prefix = '✅' if status == 'approved' else '⏳' if status == 'pending' else '•'
            lines.append(f"{prefix} *{t['key']}*")
            lines.append(f"{t['name']}")
            lines.append("")

    lines.append(
        "📸 *How to submit:*\n"
        "Take a photo → send it here → task key as caption\n"
        "Example: `FRIDGES` or `fridges` or `Fridges`"
    )

    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')


async def handle_task_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    # Accept any case — convert to upper for lookup
    caption = (update.message.caption or '').strip().upper()
    db = get_db()

    location = db.execute(
        "SELECT * FROM locations WHERE chat_id = ?", (chat.id,)
    ).fetchone()
    if not location:
        return

    db.execute("""
        INSERT OR IGNORE INTO users (telegram_id, username, full_name, location_id, role)
        VALUES (?, ?, ?, ?, 'barista')
    """, (user.id, user.username or '', user.full_name, location['id']))
    db.commit()

    db_user = db.execute(
        "SELECT * FROM users WHERE telegram_id = ? AND location_id = ?",
        (user.id, location['id'])
    ).fetchone()

    task = find_task_by_key(caption)
    if not task:
        await update.message.reply_text(
            "❓ Task key not recognized.\n"
            "Send the photo with the task key as caption.\n"
            "Example: `FRIDGES` or `fridges` or `Fridges`\n\n"
            "Use /tasks to see today's list.",
            parse_mode='Markdown'
        )
        return

    existing = db.execute("""
        SELECT * FROM task_submissions
        WHERE user_id = ? AND task_key = ? AND date(submitted_at) = date('now')
    """, (db_user['id'], task['key'])).fetchone()

    if existing:
        msg = "✅ You already completed this task today!" if existing['status'] == 'approved' \
            else "⏳ Already submitted — waiting for approval."
        await update.message.reply_text(msg)
        return

    photo_file_id = update.message.photo[-1].file_id
    tokens = get_tokens_for_task(task['key'])

    db.execute("""
        INSERT INTO task_submissions (user_id, location_id, task_key, task_name, photo_file_id, tokens_awarded, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
    """, (db_user['id'], location['id'], task['key'], task['name'], photo_file_id, tokens))
    submission_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.commit()

    await update.message.reply_text(
        f"📸 *Submitted!*\n\n"
        f"*{task['key']}* — {task['name']}\n"
        f"+{tokens} 🪙\n\n"
        f"⏳ Waiting for manager approval...",
        parse_mode='Markdown'
    )

    managers = db.execute("""
        SELECT telegram_id FROM users
        WHERE location_id = ? AND role = 'manager'
    """, (location['id'],)).fetchall()

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{submission_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{submission_id}"),
    ]])

    notify_text = (
        f"📋 *New submission*\n"
        f"📍 {location['name']}\n"
        f"👤 {user.full_name} (@{user.username or '—'})\n\n"
        f"*{task['key']}* — {task['name']}\n"
        f"🪙 +{tokens} tokens\n"
        f"🕐 {datetime.now().strftime('%H:%M')}"
    )

    for manager in managers:
        try:
            await context.bot.send_photo(
                chat_id=manager['telegram_id'],
                photo=photo_file_id,
                caption=notify_text,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
        except Exception:
            pass


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = get_db()

    location = db.execute(
        "SELECT * FROM locations WHERE chat_id = ?", (chat.id,)
    ).fetchone()
    if not location:
        return

    db_user = db.execute(
        "SELECT * FROM users WHERE telegram_id = ? AND location_id = ?",
        (user.id, location['id'])
    ).fetchone()
    if not db_user:
        await update.message.reply_text("Send /start first to register.")
        return

    rank = db.execute("""
        SELECT COUNT(*) + 1 as r FROM users
        WHERE location_id = ? AND tokens > ? AND role = 'barista'
    """, (location['id'], db_user['tokens'])).fetchone()['r']

    total_staff = db.execute(
        "SELECT COUNT(*) as c FROM users WHERE location_id = ? AND role = 'barista'",
        (location['id'],)
    ).fetchone()['c']

    today_done = db.execute("""
        SELECT COUNT(*) as c FROM task_submissions
        WHERE user_id = ? AND status = 'approved' AND date(submitted_at) = date('now')
    """, (db_user['id'],)).fetchone()['c']

    week_done = db.execute("""
        SELECT COUNT(*) as c FROM task_submissions
        WHERE user_id = ? AND status = 'approved'
        AND date(submitted_at) >= date('now', '-7 days')
    """, (db_user['id'],)).fetchone()['c']

    recent = db.execute("""
        SELECT task_key, task_name, tokens_awarded, submitted_at FROM task_submissions
        WHERE user_id = ? AND status = 'approved'
        ORDER BY submitted_at DESC LIMIT 5
    """, (db_user['id'],)).fetchall()

    lines = [
        f"💰 *{user.first_name}'s balance*",
        f"📍 {location['name']}",
        "",
        f"🪙 *{db_user['tokens']} tokens*",
        f"📈 Total ever earned: {db_user['total_earned']}",
        f"🏆 Rank: *#{rank}* of {total_staff}",
        "",
        f"📅 Today: {today_done} tasks",
        f"📆 This week: {week_done} tasks",
    ]

    if recent:
        lines.append("")
        lines.append("*Recent:*")
        for r in recent:
            dt = r['submitted_at'][5:10]
            lines.append(f"• *{r['task_key']}* +{r['tokens_awarded']}🪙 _{dt}_")

    lines.append("")
    lines.append("👀 /leaderboard — see how you compare with the team")

    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')


async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = get_db()

    location = db.execute(
        "SELECT * FROM locations WHERE chat_id = ?", (chat.id,)
    ).fetchone()
    if not location:
        return

    text = _build_leaderboard(db, location, user.id, 'week')

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📅 This week", callback_data=f"lb_{location['id']}_week"),
        InlineKeyboardButton("📆 This month", callback_data=f"lb_{location['id']}_month"),
    ]])

    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=keyboard)


def _build_leaderboard(db, location, viewer_telegram_id, period):
    if period == 'month':
        since = "date('now', 'start of month')"
        period_label = "This month"
    else:
        since = "date('now', '-7 days')"
        period_label = "This week"

    rows = db.execute(f"""
        SELECT
            u.telegram_id,
            u.full_name,
            COALESCE(SUM(s.tokens_awarded), 0) as period_tokens,
            COUNT(s.id) as period_tasks
        FROM users u
        LEFT JOIN task_submissions s
            ON s.user_id = u.id
            AND s.status = 'approved'
            AND date(s.submitted_at) >= {since}
        WHERE u.location_id = ? AND u.role = 'barista'
        GROUP BY u.id
        ORDER BY period_tokens DESC, period_tasks DESC
    """, (location['id'],)).fetchall()

    medals = ['🥇', '🥈', '🥉']
    lines = [
        f"🏆 *Leaderboard — {period_label}*",
        f"📍 {location['name']}",
        "",
    ]

    for i, row in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i + 1}."
        is_you = "  ← you" if row['telegram_id'] == viewer_telegram_id else ""
        name = row['full_name'].split()[0]
        lines.append(f"{medal} *{name}*{is_you}")
        lines.append(f"🪙 {row['period_tokens']} tokens · ✅ {row['period_tasks']} tasks")
        lines.append("")

    if not rows:
        lines.append("No activity yet this period.")

    return '\n'.join(lines)


async def handle_leaderboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split('_')
    location_id = int(parts[1])
    period = parts[2]

    db = get_db()
    location = db.execute(
        "SELECT * FROM locations WHERE id = ?", (location_id,)
    ).fetchone()
    if not location:
        return

    text = _build_leaderboard(db, location, query.from_user.id, period)

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📅 This week", callback_data=f"lb_{location_id}_week"),
        InlineKeyboardButton("📆 This month", callback_data=f"lb_{location_id}_month"),
    ]])

    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)
