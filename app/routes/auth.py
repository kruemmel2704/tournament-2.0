from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User, Clan
from app.extensions import db
from sqlalchemy import func
import re # Für die Regex-Validierung nötig

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # 1. Token Login
        token_user = User.query.filter_by(token=password).first()
        if token_user:
            login_user(token_user)
            flash('Login mit Token erfolgreich.', 'success')
            return redirect(url_for('main.dashboard'))

        # 2. Passwort Login (Für normale User UND Clan-Admins)
        # Da der Clan-Name jetzt der Username des Admins ist, funktioniert das hier universell.
        user = User.query.filter_by(username=username).first()
        
        if user and user.password and check_password_hash(user.password, password):
            login_user(user)
            flash('Willkommen zurück.', 'success')
            if getattr(user, 'is_clan_admin', False):
                return redirect(url_for('main.clan_dashboard'))
            return redirect(url_for('main.dashboard'))
        
        flash('Login fehlgeschlagen. Bitte Daten prüfen.', 'error')
    return render_template('login.html')

@auth_bp.route('/register_clan', methods=['GET', 'POST'])
def register_clan():
    if request.method == 'POST':
        # strip() entfernt versehentliche Leerzeichen
        clan_name = request.form.get('clan_name', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        # --- SICHERHEITS-CHECKS START ---
        # 1. Länge
        if len(clan_name) < 3 or len(clan_name) > 20:
            flash('Name muss zwischen 3 und 20 Zeichen lang sein.', 'error')
            return redirect(url_for('auth.register_clan'))

        # 2. Erlaubte Zeichen (nur Buchstaben, Zahlen, Unterstrich)
        if not re.match(r'^[a-zA-Z0-9_]+$', clan_name):
            flash('Name darf nur Buchstaben, Zahlen und Unterstriche enthalten.', 'error')
            return redirect(url_for('auth.register_clan'))

        # 3. Reservierte Namen
        reserved_names = ['admin', 'root', 'support', 'moderator']
        if clan_name.lower() in reserved_names:
            flash('Dieser Name ist reserviert.', 'error')
            return redirect(url_for('auth.register_clan'))
        # --- SICHERHEITS-CHECKS ENDE ---

        # 4. Passwörter abgleichen
        if password != confirm:
            flash('Passwörter stimmen nicht überein.', 'error')
            return redirect(url_for('auth.register_clan'))

        # 5. Namens-Check (Case Insensitive)
        # Wir prüfen, ob der Name schon als Clan ODER als User existiert
        existing_clan = Clan.query.filter(func.lower(Clan.name) == clan_name.lower()).first()
        existing_user = User.query.filter(func.lower(User.username) == clan_name.lower()).first()

        if existing_clan or existing_user:
            flash('Name bereits vergeben.', 'error')
            return redirect(url_for('auth.register_clan'))

        # 6. Clan erstellen (OHNE PASSWORT - Verhindert Redundanz)
        new_clan = Clan(name=clan_name)
        db.session.add(new_clan)
        db.session.commit() # ID generieren

        # 7. Admin-User erstellen (MIT PASSWORT)
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        admin_user = User(
            username=clan_name,          # Der Admin-Account heißt wie der Clan
            password=hashed_password,    # Hier wird das PW gespeichert
            is_clan_admin=True,
            clan_id=new_clan.id
        )
        db.session.add(admin_user)
        db.session.commit()

        flash('Clan erstellt! Du kannst dich nun mit dem Clan-Namen einloggen.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register_clan.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))