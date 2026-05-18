from datetime import date

# Token values by difficulty
TOKENS = {
    'easy': 1,
    'medium': 2,
    'hard': 3,
}

# All tasks organized by day
# Format: { 'day': [ {'key': unique_id, 'name': display_name, 'difficulty': easy/medium/hard} ] }
WEEKLY_TASKS = {
    'daily': [
        {'key': 'daily_mychka',    'name': 'Check mychka — run CLE programme & take photo (Sanytol)', 'difficulty': 'easy'},
        {'key': 'daily_toilets',   'name': 'Check toilets throughout the day', 'difficulty': 'easy'},
        {'key': 'daily_bunn',      'name': 'Clean BUNN + stand underneath + EK Grinder area', 'difficulty': 'medium'},
        {'key': 'daily_mixer',     'name': 'Clean the mixer', 'difficulty': 'easy'},
        {'key': 'daily_bills',     'name': 'Close crew bill and zero-bills', 'difficulty': 'easy'},
        {'key': 'daily_terrace',   'name': 'Check cleanliness of the terrace', 'difficulty': 'easy'},
        {'key': 'daily_thermoses', 'name': 'Wash thermoses for batch brew', 'difficulty': 'easy'},
    ],
    'monday': [
        {'key': 'mon_showcase',    'name': 'Check & refill showcase (check coffee beans date)', 'difficulty': 'easy'},
        {'key': 'mon_icemaker',    'name': 'Clean Ice Maker filter (vacuum) + Ice Maker inside', 'difficulty': 'hard'},
        {'key': 'mon_fridges',     'name': 'Wipe all fridges inside and out', 'difficulty': 'medium'},
        {'key': 'mon_lamarzocco',  'name': 'Wipe top of La Marzocco (under mugs & to-go cups)', 'difficulty': 'easy'},
        {'key': 'mon_sponges',     'name': 'Check and replace sponges', 'difficulty': 'easy'},
    ],
    'tuesday': [
        {'key': 'tue_showcase',    'name': 'Check & refill showcase (check coffee beans date)', 'difficulty': 'easy'},
        {'key': 'tue_deepclean',   'name': 'Coffee Machine Deep Clean', 'difficulty': 'hard'},
        {'key': 'tue_lids_area',   'name': 'Clean area under lids / sugar / etc.', 'difficulty': 'easy'},
        {'key': 'tue_glasses',     'name': 'Clean glasses with straws and all spoons', 'difficulty': 'medium'},
        {'key': 'tue_foodshowcase','name': 'Clean and spray top of food showcase', 'difficulty': 'easy'},
    ],
    'wednesday': [
        {'key': 'wed_showcase',    'name': 'Check & refill showcase (check coffee beans date)', 'difficulty': 'easy'},
        {'key': 'wed_bins',        'name': 'Wipe/wash trash bins', 'difficulty': 'medium'},
        {'key': 'wed_sinks',       'name': 'Clean ALL sinks with CIF cleaner', 'difficulty': 'medium'},
        {'key': 'wed_lamarzocco',  'name': 'Wipe top of La Marzocco (under mugs & to-go cups)', 'difficulty': 'easy'},
        {'key': 'wed_shelves',     'name': 'Wipe dust off accessory shelves', 'difficulty': 'easy'},
        {'key': 'wed_sponges',     'name': 'Check and replace sponges', 'difficulty': 'easy'},
        {'key': 'wed_towels',      'name': 'Send dirty towels with Roastery delivery to DOCK', 'difficulty': 'easy'},
    ],
    'thursday': [
        {'key': 'thu_showcase',    'name': 'Check & refill showcase (check coffee beans date)', 'difficulty': 'easy'},
        {'key': 'thu_brewbar',     'name': 'Clean brew bar area thoroughly (BUNN + EK Grinder)', 'difficulty': 'hard'},
        {'key': 'thu_towels',      'name': 'Send dirty towels with Roastery delivery to DOCK', 'difficulty': 'easy'},
        {'key': 'thu_spoons',      'name': 'Clean the spoons', 'difficulty': 'easy'},
        {'key': 'thu_foodshowcase','name': 'Clean top of food showcase', 'difficulty': 'easy'},
    ],
    'friday': [
        {'key': 'fri_showcase',    'name': 'Check & refill showcase (check coffee beans date)', 'difficulty': 'easy'},
        {'key': 'fri_showcase_pol','name': 'Clean & polish showcase inside and out (glass cleaner)', 'difficulty': 'medium'},
        {'key': 'fri_foodshowcase','name': 'Clean top of food showcase', 'difficulty': 'easy'},
        {'key': 'fri_icemaker',    'name': 'Clean Ice Maker filter (vacuum) + Ice Maker inside', 'difficulty': 'hard'},
        {'key': 'fri_glasses',     'name': 'Clean glasses with straws and all spoons', 'difficulty': 'medium'},
        {'key': 'fri_allshelves',  'name': 'Clean all shelves — wipe with Sanytol', 'difficulty': 'medium'},
    ],
    'saturday': [
        {'key': 'sat_showcase',    'name': 'Check & refill showcase (check coffee beans date)', 'difficulty': 'easy'},
        {'key': 'sat_bunn',        'name': 'Clean BUNN + stand underneath + EK Grinder area', 'difficulty': 'medium'},
        {'key': 'sat_sinks',       'name': 'Clean ALL sinks with CIF cleaner', 'difficulty': 'medium'},
        {'key': 'sat_mixer',       'name': 'Clean the mixer', 'difficulty': 'easy'},
        {'key': 'sat_plants',      'name': 'Dust off leaves of the plants', 'difficulty': 'easy'},
        {'key': 'sat_shelves',     'name': 'Wipe dust off accessory shelves', 'difficulty': 'easy'},
        {'key': 'sat_foodshowcase','name': 'Clean top of food showcase', 'difficulty': 'easy'},
        {'key': 'sat_sponges',     'name': 'Clean the sponges', 'difficulty': 'easy'},
        {'key': 'sat_glasses',     'name': 'Clean glasses with straws and all spoons', 'difficulty': 'medium'},
        {'key': 'sat_allshelves',  'name': 'Clean all shelves — wipe with Sanytol', 'difficulty': 'medium'},
    ],
    'sunday': [
        {'key': 'sun_showcase',    'name': 'Check & refill showcase (check coffee beans date)', 'difficulty': 'easy'},
        {'key': 'sun_deepclean',   'name': 'Coffee Machine Deep Clean', 'difficulty': 'hard'},
        {'key': 'sun_garnishes',   'name': 'Refill the garnishes', 'difficulty': 'easy'},
        {'key': 'sun_topshowcase', 'name': 'Clean top of showcase', 'difficulty': 'easy'},
        {'key': 'sun_lids_area',   'name': 'Clean area under lids / sugar / etc.', 'difficulty': 'easy'},
        {'key': 'sun_mixer_rinse', 'name': 'Leave mixer in rinser overnight', 'difficulty': 'easy'},
        {'key': 'sun_matcha_tray', 'name': 'Clean tray under matcha and straws (near mixer)', 'difficulty': 'easy'},
        {'key': 'sun_batchstation','name': 'Clean batch station properly (under drips, capsules)', 'difficulty': 'medium'},
        {'key': 'sun_mychka',      'name': 'Check mychka — run CLE programme & photo (Antikylk)', 'difficulty': 'easy'},
    ],
}


def get_today_tasks():
    """Returns daily tasks + tasks for today's weekday."""
    weekday = date.today().strftime('%A').lower()
    tasks = list(WEEKLY_TASKS.get('daily', []))
    tasks += WEEKLY_TASKS.get(weekday, [])
    return tasks


def get_tokens_for_task(task_key: str) -> int:
    """Returns token value for a task by its key."""
    for day_tasks in WEEKLY_TASKS.values():
        for task in day_tasks:
            if task['key'] == task_key:
                return TOKENS[task['difficulty']]
    return 1


def find_task_by_key(task_key: str):
    for day_tasks in WEEKLY_TASKS.values():
        for task in day_tasks:
            if task['key'] == task_key:
                return task
    return None


def format_task_list(tasks: list) -> str:
    """Format task list for Telegram message."""
    easy   = [t for t in tasks if t['difficulty'] == 'easy']
    medium = [t for t in tasks if t['difficulty'] == 'medium']
    hard   = [t for t in tasks if t['difficulty'] == 'hard']

    lines = []
    if hard:
        lines.append("🔴 *Heavy tasks — 3 tokens each*")
        for t in hard:
            lines.append(f"  • `{t['key']}` — {t['name']}")
    if medium:
        lines.append("\n🟡 *Standard tasks — 2 tokens each*")
        for t in medium:
            lines.append(f"  • `{t['key']}` — {t['name']}")
    if easy:
        lines.append("\n🟢 *Quick tasks — 1 token each*")
        for t in easy:
            lines.append(f"  • `{t['key']}` — {t['name']}")

    return '\n'.join(lines)
