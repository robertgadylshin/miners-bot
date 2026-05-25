from datetime import date, datetime
from zoneinfo import ZoneInfo

POINTS = {
    'easy': 100,
    'medium': 200,
    'hard': 300,
}

DAILY_LIMIT = 300
CUSTOM_TASK_KEY = 'CUSTOM'
CUSTOM_TASK = {'key': CUSTOM_TASK_KEY, 'name': 'Custom task', 'difficulty': 'custom'}

WEEKLY_TASKS = {
    'daily': [
        {'key': 'TOILETS',   'name': 'Check toilets throughout the day', 'difficulty': 'easy'},
        {'key': 'MIXER',     'name': 'Clean the mixer', 'difficulty': 'easy'},
        {'key': 'BILLS',     'name': 'Close crew bill and zero-bills', 'difficulty': 'easy'},
        {'key': 'TERRACE',   'name': 'Check cleanliness of the terrace', 'difficulty': 'easy'},
        {'key': 'THERMOSES', 'name': 'Wash thermoses for batch brew', 'difficulty': 'easy'},
    ],
    'monday': [
        {'key': 'SHOWCASE',  'name': 'Check & refill showcase (check coffee beans date)', 'difficulty': 'easy'},
        {'key': 'ICEMAKER',  'name': 'Clean Ice Maker filter (vacuum) + Ice Maker inside', 'difficulty': 'hard'},
        {'key': 'FRIDGES',   'name': 'Wipe all fridges inside and out', 'difficulty': 'medium'},
        {'key': 'MACHINE',   'name': 'Clean top of coffee machine (under mugs & to-go cups)', 'difficulty': 'medium'},
        {'key': 'SPONGES',   'name': 'Check and replace sponges', 'difficulty': 'easy'},
    ],
    'tuesday': [
        {'key': 'SHOWCASE',  'name': 'Check & refill showcase (check coffee beans date)', 'difficulty': 'easy'},
        {'key': 'LIDS',      'name': 'Clean area under lids / sugar / etc.', 'difficulty': 'easy'},
        {'key': 'GLASSES',   'name': 'Clean all glasses', 'difficulty': 'medium'},
        {'key': 'FOODTOP',   'name': 'Clean and spray top of food showcase', 'difficulty': 'easy'},
    ],
    'wednesday': [
        {'key': 'SHOWCASE',  'name': 'Check & refill showcase (check coffee beans date)', 'difficulty': 'easy'},
        {'key': 'BINS',      'name': 'Wipe/wash trash bins', 'difficulty': 'medium'},
        {'key': 'SINKS',     'name': 'Clean ALL sinks with CIF cleaner', 'difficulty': 'medium'},
        {'key': 'SHELVES',   'name': 'Wipe dust off accessory shelves', 'difficulty': 'easy'},
        {'key': 'SPONGES',   'name': 'Check and replace sponges', 'difficulty': 'easy'},
        {'key': 'TOWELS',    'name': 'Send dirty towels with Roastery delivery to DOCK', 'difficulty': 'easy'},
    ],
    'thursday': [
        {'key': 'SHOWCASE',  'name': 'Check & refill showcase (check coffee beans date)', 'difficulty': 'easy'},
        {'key': 'EK',        'name': 'Clean EK Grinder', 'difficulty': 'hard'},
        {'key': 'TOWELS',    'name': 'Send dirty towels with Roastery delivery to DOCK', 'difficulty': 'easy'},
        {'key': 'SPOONS',    'name': 'Clean the spoons', 'difficulty': 'easy'},
        {'key': 'FOODTOP',   'name': 'Clean top of food showcase', 'difficulty': 'easy'},
    ],
    'friday': [
        {'key': 'SHOWCASE',   'name': 'Check & refill showcase (check coffee beans date)', 'difficulty': 'easy'},
        {'key': 'POLISH',     'name': 'Clean & polish showcase inside and out (glass cleaner)', 'difficulty': 'medium'},
        {'key': 'FOODTOP',    'name': 'Clean top of food showcase', 'difficulty': 'easy'},
        {'key': 'ICEMAKER',   'name': 'Clean Ice Maker filter (vacuum) + Ice Maker inside', 'difficulty': 'hard'},
        {'key': 'GLASSES',    'name': 'Clean all glasses', 'difficulty': 'medium'},
        {'key': 'BARSHELVES', 'name': 'Clean all bar shelves', 'difficulty': 'medium'},
    ],
    'saturday': [
        {'key': 'SHOWCASE',   'name': 'Check & refill showcase (check coffee beans date)', 'difficulty': 'easy'},
        {'key': 'BUNN',       'name': 'Clean BUNN + stand underneath + EK Grinder area', 'difficulty': 'medium'},
        {'key': 'SINKS',      'name': 'Clean ALL sinks with CIF cleaner', 'difficulty': 'medium'},
        {'key': 'PLANTS',     'name': 'Dust off leaves of the plants', 'difficulty': 'easy'},
        {'key': 'SHELVES',    'name': 'Wipe dust off accessory shelves', 'difficulty': 'easy'},
        {'key': 'FOODTOP',    'name': 'Clean top of food showcase', 'difficulty': 'easy'},
        {'key': 'SPONGES',    'name': 'Clean the sponges', 'difficulty': 'easy'},
        {'key': 'GLASSES',    'name': 'Clean all glasses', 'difficulty': 'medium'},
        {'key': 'BARSHELVES', 'name': 'Clean all bar shelves', 'difficulty': 'medium'},
    ],
    'sunday': [
        {'key': 'SHOWCASE',  'name': 'Check & refill showcase (check coffee beans date)', 'difficulty': 'easy'},
        {'key': 'GARNISHES', 'name': 'Refill the garnishes', 'difficulty': 'easy'},
        {'key': 'LIDS',      'name': 'Clean area under lids / sugar / etc.', 'difficulty': 'easy'},
    ],
}


def _local_weekday(timezone: str = 'UTC') -> str:
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        tz = ZoneInfo('UTC')
    return datetime.now(tz).strftime('%A').lower()


def _local_date_str(timezone: str = 'UTC') -> str:
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        tz = ZoneInfo('UTC')
    return datetime.now(tz).strftime('%A, %d %B %Y')


def get_today_tasks(timezone: str = 'UTC'):
    weekday = _local_weekday(timezone)
    tasks = list(WEEKLY_TASKS.get('daily', []))
    tasks += WEEKLY_TASKS.get(weekday, [])
    return tasks


def get_today_task_keys(timezone: str = 'UTC') -> set:
    return {t['key'] for t in get_today_tasks(timezone)}


def get_points_for_task(task_key: str) -> int:
    for day_tasks in WEEKLY_TASKS.values():
        for task in day_tasks:
            if task['key'] == task_key.upper():
                return POINTS[task['difficulty']]
    return 100


def find_task_by_key(task_key: str):
    key = task_key.strip().upper()
    if key == CUSTOM_TASK_KEY:
        return CUSTOM_TASK
    for day_tasks in WEEKLY_TASKS.values():
        for task in day_tasks:
            if task['key'] == key:
                return task
    return None
