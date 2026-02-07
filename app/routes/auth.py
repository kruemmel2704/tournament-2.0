from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User, Clan
from app.extensions import db

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

        # 2. Passwort Login
        user = User.query.filter_by(username=username).first()
        if user and user.password and check_password_hash(user.password, password):
            login_user(user)
            flash('Willkommen zurück.', 'success')
            if getattr(user, 'is_clan_admin', False):
                return redirect(url_for('main.clan_dashboard'))
            return redirect(url_for('main.dashboard'))
        
        flash('Login fehlgeschlagen.', 'error')
    return render_template('login.html')

@auth_bp.route('/register_clan', methods=['GET', 'POST'])
def register_clan():
    if request.method == 'POST':
        clan_name = request.form.get('clan_name')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')

        # 1. Validierung: Stimmen Passwörter überein?
        if password != confirm:
            flash('Passwörter stimmen nicht überein.', 'error')
            return redirect(url_for('auth.register_clan'))

        # 2. Validierung: Gibt es den Namen schon?
        existing_clan = Clan.query.filter_by(name=clan_name).first()
        existing_user = User.query.filter_by(username=clan_name).first()

        if existing_clan or existing_user:
            flash('Name bereits vergeben.', 'error')
            return redirect(url_for('auth.register_clan'))

        # 3. Passwort hashen (Nur einmal, wird für beide genutzt)
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        # 4. Clan erstellen (MIT PASSWORT!)
        # Hier lag vorher der Fehler: Das Passwort muss auch in den Clan
        new_clan = Clan(name=clan_name, password=hashed_password)
        db.session.add(new_clan)
        db.session.commit()  # Wichtig: Commit, damit new_clan.id generiert wird

        # 5. Clan Admin User erstellen
        admin_user = User(
            username=clan_name,
            password=hashed_password,  # Gleiches gehashtes PW wie beim Clan
            is_clan_admin=True,
            clan_id=new_clan.id
        )
        db.session.add(admin_user)
        db.session.commit()

        flash('Clan erstellt! Bitte einloggen.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register_clan.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))