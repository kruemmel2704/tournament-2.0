import json
from functools import wraps
from flask import redirect, url_for, session, flash

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_map_wins(scores_a, scores_b):
    wins_a = 0
    wins_b = 0
    # Sicherstellen, dass Listen existieren
    if not scores_a or not scores_b: return 0, 0
    for sa, sb in zip(scores_a, scores_b):
        if sa > sb: wins_a += 1
        elif sb > sa: wins_b += 1
    return wins_a, wins_b

def safe_json_load(data):
    try: return json.loads(data) if data else []
    except: return []

def clan_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'clan_id' not in session:
            flash('Bitte als Clan einloggen.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function