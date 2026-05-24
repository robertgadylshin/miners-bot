import json
import logging
from datetime import datetime, date
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes

from db import get_db
from tasks import (
    get_today_tasks, get_today_task_keys, get_points_for_task,
    find_task_by_key, DAILY_LIMIT, CUSTOM_TASK_KEY, CUSTOM_TASK,
)

logger = logging.getLogger(__name__)

MEDIA_GROUP_DELAY = 2.5


def _first_name(full_name, username=''):
    s = (full_name or '').strip()
    if s:
        return s.split()[0]
    return username or 'Unknown'


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
        """, (member.id, member.username or '', member.full_name or '', location['id']))
    db.commit()


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = get_db()

    location = db.execute(
        "SELECT * FROM locations WHERE chat_id = ?", (chat.id,)
    ).fetchone()
    if not location:
        await update.message.reply_text("This group is not set up yet. Ask admin to run /setup.")
        return

    db.execute("""
        INSERT OR IGNORE INTO users (telegram_id, username, full_name, location_id, role)
        VALUES (?, ?, ?, ?, 'barista')
    """, (user.id, user.username or '', user.full_name or '', location['id']))
    db.commit()

    tasks = get_today_tasks()
    today_str = date.today().strftime('%A, %d %B %Y')

    submitted = db.execute("""
        SELECT task_key, status FROM task_submissions
        WHERE user_id = (SELECT id FROM users WHERE telegram_id = ? AND location_id = ?)
        AND date(submitted_at) = date('now')
    """, (user.id, location['id'])).fetchall()
    submitted_keys = {row['task_key']: row['status'] for row in submitted}

    earned_today = db.execute("""
        SELECT COALESCE(SUM(tokens_awarded), 0) as total FROM task_submissions
        WHERE user_id = (SELECT id FROM users WHERE telegram_id = ? AND location_id = ?)
        AND status = 'approved' AND date(submitted_at) = date('now')
    """, (user.id, location['id'])).fetchone()['total']

    lines = [
        f"Tasks for {today_str}",
        f"📍 {location['name']}",
        f"Today: {earned_today}/{DAILY_LIMIT} points",
        "",
    ]

    groups = [
        ("🔴 Heavy — 300 points", [t for t in tasks if t['difficulty'] == 'hard']),
        ("🟡 Standard — 200 points", [t for t in tasks if t['difficulty'] == 'medium']),
        ("🟢 Quick — 100 points", [t for t in tasks if t['difficulty'] == 'easy']),
    ]

    for label, items in groups:
        if not items:
            continue
        lines.append(label)
        for t in items:
            status = submitted_keys.get(t['key'])
            prefix = '✅' if status == 'approved' else '⏳' if status == 'pending' else '•'
            lines.append(f"{prefix} {t['key']}")
            lines.append(t['name'])
            lines.append("")

    custom_status = submitted_keys.get(CUSTOM_TASK_KEY)
    custom_prefix = '✅' if custom_status == 'approved' else '⏳' if custom_status == 'pending' else '•'
    lines.append("⚪ Custom task")
    lines.append(f"{custom_prefix} CUSTOM — describe what you did in the caption")
    lines.append("")

    lines.append(
        "📸 How to submit:\n"
        "Take a photo → send it here → task key as caption\n"
        "FRIDGES or fridges — any case works\n"
        "For custom: CUSTOM I cleaned the storage room"
    )

    await update.message.reply_text('\n'.join(lines))


async def handle_task_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    caption_raw = (msg.caption or '').strip()
    file_id = msg.photo[-1].file_id
    user = update.effective_user
    chat = update.effective_chat

    if msg.media_group_id:
        key = f"mg_{msg.media_group_id}"
        if key not in context.chat_data:
            context.chat_data[key] = {
                'file_ids': [],
                'caption': '',
                'user_id': user.id,
                'username': user.username or '',
                'full_name': user.full_name or '',
                'chat_id': chat.id,
                'reply_to': msg.message_id,
            }
            context.job_queue.run_once(
                _process_submission_job,
                MEDIA_GROUP_DELAY,
                name=key,
                chat_id=chat.id,
                data={'key': key},
            )
        entry = context.chat_data[key]
        entry['file_ids'].append(file_id)
        if caption_raw:
            entry['caption'] = caption_raw
        return

    if not caption_raw:
        return

    await _do_submission(
        context, chat.id,
        user.id, user.username or '', user.full_name or '',
        [file_id], caption_raw,
        reply_to_message_id=msg.message_id,
    )


async def _process_submission_job(context: ContextTypes.DEFAULT_TYPE):
    key = context.job.data['key']
    entry = context.chat_data.pop(key, None)
    if not entry or not entry['file_ids'] or not entry['caption']:
        return

    await _do_submission(
        context, entry['chat_id'],
        entry['user_id'], entry['username'], entry['full_name'],
        entry['file_ids'], entry['caption'],
        reply_to_message_id=entry.get('reply_to'),
    )


async def _do_submission(
    context, chat_id,
    user_id, username, full_name,
    file_ids, caption_raw,
    reply_to_message_id=None,
):
    db = get_db()

    location = db.execute(
        "SELECT * FROM locations WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    if not location:
        return

    db.execute("""
        INSERT OR IGNORE INTO users (telegram_id, username, full_name, location_id, role)
        VALUES (?, ?, ?, ?, 'barista')
    """, (user_id, username, full_name, location['id']))
    db.commit()

    db_user = db.execute(
        "SELECT * FROM users WHERE telegram_id = ? AND location_id = ?",
        (user_id, location['id'])
    ).fetchone()

    if db_user and db_user['role'] == 'manager':
        await context.bot.send_message(
            chat_id=chat_id,
            text="Managers cannot submit tasks.",
            reply_to_message_id=reply_to_message_id,
        )
        return

    # Parse caption: first word = task key, rest = description
    words = caption_raw.split(None, 1)
    task_key_input = words[0].upper()
    custom_description = words[1].strip() if len(words) > 1 else ''

    if task_key_input == CUSTOM_TASK_KEY:
        task = CUSTOM_TASK
    else:
        task = find_task_by_key(task_key_input)
        if not task:
            await context.bot.send_message(
                chat_id=chat_id,
                text="Task key not recognized.\nUse /tasks to see today's list.",
                reply_to_message_id=reply_to_message_id,
            )
            return
        if task['key'] not in get_today_task_keys():
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"{task['key']} is not on today's task list.\n"
                    "Use /tasks to see what's available today.\n\n"
                    "If this was an exceptional task, submit it as:\n"
                    f"CUSTOM {task['key']} — description"
                ),
                reply_to_message_id=reply_to_message_id,
            )
            return

    existing = db.execute("""
        SELECT * FROM task_submissions
        WHERE user_id = ? AND task_key = ? AND date(submitted_at) = date('now')
    """, (db_user['id'], task['key'])).fetchone()

    if existing:
        if existing['status'] == 'approved':
            msg_text = "✅ You already completed this task today!"
        else:
            msg_text = "⏳ Already submitted — waiting for approval."
        await context.bot.send_message(
            chat_id=chat_id, text=msg_text, reply_to_message_id=reply_to_message_id,
        )
        return

    if task['key'] == CUSTOM_TASK_KEY:
        points = 0
    else:
        earned_today = db.execute("""
            SELECT COALESCE(SUM(tokens_awarded), 0) as total FROM task_submissions
            WHERE user_id = ? AND status IN ('approved', 'pending') AND date(submitted_at) = date('now')
        """, (db_user['id'],)).fetchone()['total']

        points = get_points_for_task(task['key'])

        if earned_today >= DAILY_LIMIT:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"You've reached the daily limit of {DAILY_LIMIT} points.\nLooking forward to the next shift!",
                reply_to_message_id=reply_to_message_id,
            )
            return

        if earned_today + points > DAILY_LIMIT:
            remaining = DAILY_LIMIT - earned_today
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"This task gives {points} points but you only have {remaining} left today.\n\n"
                    "Pick a lighter task that fits!"
                ),
                reply_to_message_id=reply_to_message_id,
            )
            return

    db.execute("""
        INSERT INTO task_submissions
        (user_id, location_id, task_key, task_name, photo_file_id, photo_file_ids,
         tokens_awarded, status, custom_description)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (
        db_user['id'], location['id'], task['key'], task['name'],
        file_ids[0], json.dumps(file_ids), points,
        custom_description or None,
    ))
    submission_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.commit()

    if task['key'] == CUSTOM_TASK_KEY:
        confirm_text = (
            f"📸 Custom task submitted!\n\n"
            f"{custom_description or '(no description)'}\n\n"
            f"⏳ Waiting for manager to assign points..."
        )
    else:
        confirm_text = (
            f"📸 Submitted!\n\n"
            f"{task['key']} — {task['name']}\n"
            f"+{points} points\n\n"
            f"⏳ Waiting for manager approval..."
        )

    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=confirm_text,
        reply_to_message_id=reply_to_message_id,
    )

    try:
        db.execute(
            "UPDATE task_submissions SET group_chat_id = ?, group_message_id = ? WHERE id = ?",
            (chat_id, sent.message_id, submission_id)
        )
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save group message ref: {e}")

    managers = db.execute(
        "SELECT telegram_id FROM users WHERE location_id = ? AND role = 'manager'",
        (location['id'],)
    ).fetchall()

    # Time in location's timezone
    try:
        tz = ZoneInfo(location['timezone'] or 'UTC')
        now_local = datetime.now(tz)
    except Exception:
        now_local = datetime.utcnow()
    time_str = now_local.strftime('%H:%M')

    name_display = full_name or username or 'Unknown'
    username_str = f"@{username}" if username else "no username"
    photo_count = f" ({len(file_ids)} photos)" if len(file_ids) > 1 else ""

    if task['key'] == CUSTOM_TASK_KEY:
        notify_text = (
            f"📋 Custom task{photo_count}\n"
            f"📍 {location['name']}\n"
            f"👤 {name_display} ({username_str})\n\n"
            f"📝 {custom_description or '(no description)'}\n"
            f"🕐 {time_str}"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ 100", callback_data=f"custom_100_{submission_id}"),
                InlineKeyboardButton("✅ 200", callback_data=f"custom_200_{submission_id}"),
                InlineKeyboardButton("✅ 300", callback_data=f"custom_300_{submission_id}"),
            ],
            [InlineKeyboardButton("❌ Reject", callback_data=f"reject_{submission_id}")],
        ])
    else:
        notify_text = (
            f"📋 New submission{photo_count}\n"
            f"📍 {location['name']}\n"
            f"👤 {name_display} ({username_str})\n\n"
            f"{task['key']} — {task['name']}\n"
            f"+{points} points\n"
            f"🕐 {time_str}"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{submission_id}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"reject_{submission_id}"),
        ]])

    if not managers:
        logger.warning(f"No managers found for location {location['id']}")

    for manager in managers:
        mgr_id = manager['telegram_id']
        if not mgr_id or mgr_id == 0:
            logger.warning("Manager has telegram_id=0, skipping")
            continue
        try:
            if len(file_ids) == 1:
                await context.bot.send_photo(chat_id=mgr_id, photo=file_ids[0])
            else:
                media = [InputMediaPhoto(fid) for fid in file_ids]
                await context.bot.send_media_group(chat_id=mgr_id, media=media)
            await context.bot.send_message(
                chat_id=mgr_id, text=notify_text, reply_markup=keyboard,
            )
            logger.info(f"Submission sent to manager {mgr_id}")
        except Exception as e:
            logger.error(f"Failed to send to manager {mgr_id}: {e}")


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
        await update.message.reply_text("Use /tasks to get started.")
        return

    rank = db.execute("""
        SELECT COUNT(*) + 1 as r FROM users
        WHERE location_id = ? AND tokens > ? AND role = 'barista'
    """, (location['id'], db_user['tokens'])).fetchone()['r']

    total_staff = db.execute(
        "SELECT COUNT(*) as c FROM users WHERE location_id = ? AND role = 'barista'",
        (location['id'],)
    ).fetchone()['c']

    earned_today = db.execute("""
        SELECT COALESCE(SUM(tokens_awarded), 0) as total FROM task_submissions
        WHERE user_id = ? AND status = 'approved' AND date(submitted_at) = date('now')
    """, (db_user['id'],)).fetchone()['total']

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
        SELECT task_key, tokens_awarded, submitted_at FROM task_submissions
        WHERE user_id = ? AND status = 'approved'
        ORDER BY submitted_at DESC LIMIT 5
    """, (db_user['id'],)).fetchall()

    first_name = user.first_name or user.username or 'Barista'

    lines = [
        f"{first_name}'s balance",
        f"{location['name']}",
        "",
        f"⭐ {db_user['tokens']} points",
        f"Total ever earned: {db_user['total_earned']}",
        f"Rank: #{rank} of {total_staff}",
        "",
        f"Today: {earned_today}/{DAILY_LIMIT} points · {today_done} tasks",
        f"This week: {week_done} tasks",
    ]

    if recent:
        lines.append("")
        lines.append("Recent:")
        for r in recent:
            dt = r['submitted_at'][8:10] + '/' + r['submitted_at'][5:7]
            lines.append(f"• {r['task_key']} +{r['tokens_awarded']} pts {dt}")

    lines.append("")
    lines.append("/leaderboard — see how you compare with the team")

    await update.message.reply_text('\n'.join(lines))


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
        InlineKeyboardButton("📅 This week",  callback_data=f"lb_{location['id']}_week"),
        InlineKeyboardButton("📆 This month", callback_data=f"lb_{location['id']}_month"),
    ]])

    await update.message.reply_text(text, reply_markup=keyboard)


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
            u.username,
            COALESCE(SUM(s.tokens_awarded), 0) as period_points,
            COUNT(s.id) as period_tasks
        FROM users u
        LEFT JOIN task_submissions s
            ON s.user_id = u.id
            AND s.status = 'approved'
            AND date(s.submitted_at) >= {since}
        WHERE u.location_id = ? AND u.role = 'barista'
        GROUP BY u.id
        ORDER BY period_points DESC, period_tasks DESC
    """, (location['id'],)).fetchall()

    medals = ['🥇', '🥈', '🥉']
    lines = [
        f"Leaderboard — {period_label}",
        f"📍 {location['name']}",
        "",
    ]

    for i, row in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i + 1}."
        is_you = "  ← you" if row['telegram_id'] == viewer_telegram_id else ""
        name = _first_name(row['full_name'], row['username'])
        lines.append(f"{medal} {name}{is_you}")
        lines.append(f"⭐ {row['period_points']} points · ✅ {row['period_tasks']} tasks")
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
        InlineKeyboardButton("📅 This week",  callback_data=f"lb_{location_id}_week"),
        InlineKeyboardButton("📆 This month", callback_data=f"lb_{location_id}_month"),
    ]])

    await query.edit_message_text(text, reply_markup=keyboard)
