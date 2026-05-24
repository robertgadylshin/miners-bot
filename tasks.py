from datetime import date

POINTS = {
    'easy': 100,
    'medium': 200,
    'hard': 300,
}

DAILY_LIMIT = 300

WEEKLY_TASKS = {
    'daily': [
        {'key': 'TOILETS',   'name': 'Check toilets throughout the day', 'difficulty': 'easy'},
        {'key': 'MIXER',     'name': 'Clean the mixer', 'difficulty': 'easy'},
        {'key': 'BILLS',     'name': 'Close crew bill and zero-bills', 'difficulty': 'easy'},
        {'key': 'TERRACE',   'name': 'Check cleanliness of the terrace', 'difficulty': 'easy'},
        {'key': 'THERMOSES', 'name': 'Wash thermoses for batch brew', 'difficulty': 'easy'},
        {'key': 'SHOWCASE',  'name': 'Check & refill showcase, check coffee beans date', 'difficulty': 'easy'},
    ],
    'monday': [
        {'key': 'ICEMAKER',  'name': 'Clean Ice Maker filter (vacuum) + Ice Maker inside', 'difficulty': 'hard'},
        {'key': 'FRIDGES',   'name': 'Wipe all fridges inside and out', 'difficulty': 'medium'},
        {'key': 'MACHINE',   'name': 'Wipe top of coffee machine (under mugs & to-go cups)', 'difficulty': 'hard'},
        {'key': 'SPONGES',   'name': 'Check and replace sponges', 'difficulty': 'easy'},
    ],
    'tuesday': [
        {'key': 'LIDS',      'name': 'Clean area under lids / sugar / etc.', 'difficulty': 'easy'},
        {'key': 'GLASSES',   'name': 'Clean all glasses', 'difficulty': 'medium'},
        {'key': 'FOODTOP',   'name': 'Clean top of food showcase', 'difficulty': 'easy'},
        {'key': 'CLEVER',    'name': 'Clean Clever Drippers', 'difficulty': 'easy'},
    ],
    'wednesday': [
        {'key': 'BINS',      'name': 'Wipe/wash trash bins', 'difficulty': 'medium'},
        {'key': 'SINKS',     'name': 'Clean ALL sinks with CIF cleaner', 'difficulty': 'medium'},
        {'key': 'MACHINE',   'name': 'Wipe top of coffee machine (under mugs & to-go cups)', 'difficulty': 'hard'},
        {'key': 'SHELVES',   'name': 'Wipe dust off accessory shelves', 'difficulty': 'easy'},
        {'key': 'SPONGES',   'name': 'Check and replace sponges', 'difficulty': 'easy'},
    ],
    'thursday': [
        {'key': 'EK',        'name': 'Clean and calibrate EK grinder', 'difficulty': 'hard'},
        {'key': 'SPOONS',    'name': 'Clean and polish the spoons', 'difficulty': 'easy'},
        {'key': 'FOODTOP',   'name': 'Clean top of food showcase', 'difficulty': 'easy'},
    ],
    'friday': [
        {'key': 'ICEMAKER',  'name': 'Clean Ice Maker filter (vacuum) + Ice Maker inside', 'difficulty': 'hard'},
        {'key': 'POLISH',    'name': 'Clean & polish showcase inside and out (glass cleaner)', 'difficulty': 'medium'},
        {'key': 'FOODTOP',   'name': 'Clean top of food showcase', 'difficulty': 'easy'},
        {'key': 'GLASSES',   'name': 'Clean all glasses', 'difficulty': 'medium'},
        {'key': 'BARSHELVES','name': 'Clean all bar shelves — wipe with Sanytol', 'difficulty': 'medium'},
    ],
    'saturday': [
        {'key': 'BUNN',      'name': 'Clean BUNN + stand underneath + EK Grinder area', 'difficulty': 'medium'},
        {'key': 'SINKS',     'name': 'Clean ALL sinks with CIF cleaner', 'difficulty': 'medium'},
        {'key': 'PLANTS',    'name': 'Dust off leaves of the plants', 'difficulty': 'easy'},
        {'key': 'SHELVES',   'name': 'Wipe dust off accessory shelves', 'difficulty': 'easy'},
        {'key': 'FOODTOP',   'name': 'Clean top of food showcase', 'difficulty': 'easy'},
        {'key': 'SPONGES',   'name': 'Clean the sponges', 'difficulty': 'easy'},
        {'key': 'GLASSES',   'name': 'Clean all glasses', 'difficulty': 'medium'},
        {'key': 'BARSHELVES','name': 'Clean all bar shelves — wipe with Sanytol', 'difficulty': 'medium'},
    ],
    'sunday': [
        {'key': 'MACHINE',   'name': 'Wipe top of coffee machine (under mugs & to-go cups)', 'difficulty': 'hard'},
        {'key': 'GARNISHES', 'name': 'Refill the garnishes', 'difficulty': 'easy'},
        {'key': 'LIDS',      'name': 'Clean area under lids / sugar / etc.', 'difficulty': 'easy'},
    ],
}


def get_today_tasks():
    weekday = date.today().strftime('%A').lower()
    tasks = list(WEEKLY_TASKS.get('daily', []))
    tasks += WEEKLY_TASKS.get(weekday, [])
    return tasks


def get_points_for_task(task_key: str) -> int:
    for day_tasks in WEEKLY_TASKS.values():
        for task in day_tasks:
            if task['key'] == task_key.upper():
                return POINTS[task['difficulty']]
    return 100


def find_task_by_key(task_key: str):
    key = task_key.strip().upper()
    for day_tasks in WEEKLY_TASKS.values():
        for task in day_tasks:
            if task['key'] == key:
                return task
    return None
