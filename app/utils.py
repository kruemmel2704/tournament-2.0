import json
from functools import wraps
from flask import redirect, url_for, session, flash

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_map_wins(scores_a, scores_b):
    """
    Berechnet die Siege basierend auf zwei Listen von Scores.
    Wandelt Eingaben sicher in Integers um, um String-Vergleichsfehler zu vermeiden.
    """
    wins_a = 0
    wins_b = 0
    
    # Sicherstellen, dass Listen existieren
    if not scores_a or not scores_b: 
        return 0, 0
        
    for sa, sb in zip(scores_a, scores_b):
        try:
            # Wichtig: In int umwandeln, da DB-Daten oft Strings sind
            val_a = int(sa)
            val_b = int(sb)
            
            if val_a > val_b: 
                wins_a += 1
            elif val_b > val_a: 
                wins_b += 1
        except (ValueError, TypeError):
            # Falls ein Wert ungültig ist (z.B. leer), diese Runde ignorieren
            continue
            
    return wins_a, wins_b

def safe_json_load(data):
    """
    Lädt JSON-Daten sicher. Gibt eine leere Liste zurück, falls Daten fehlen oder fehlerhaft sind.
    """
    if not data:
        return []
    try: 
        return json.loads(data)
    except (TypeError, json.JSONDecodeError): 
        return []

def clan_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'clan_id' not in session:
            flash('Bitte als Clan einloggen.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function