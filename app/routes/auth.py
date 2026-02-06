from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from app.models import User, Clan
from app.extensions import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/', endpoint='index')
def index():
    if current_user.is_authenticated: return redirect(url_for('main.dashboard'))
    if 'clan_id' in session: return redirect(url_for('main.clan_dashboard'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user:
            if (user.is_admin or user.is_mod) and check_password_hash(user.password, password):
                login_user(user); return redirect(url_for('main.dashboard'))
            elif user.token == password:
                login_user(user); return redirect(url_for('main.dashboard'))
        clan = Clan.query.filter_by(name=username).first()
        if clan and check_password_hash(clan.password, password):
            session['clan_id'] = clan.id; flash(f'Willkommen {clan.name}!', 'success'); return redirect(url_for('main.clan_dashboard'))
        flash('Login fehlgeschlagen.', 'error')
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    logout_user(); session.pop('clan_id', None); return redirect(url_for('auth.login'))

@auth_bp.route('/register_clan', methods=['GET', 'POST'])
def register_clan():
    if current_user.is_authenticated or 'clan_id' in session: return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        name = request.form.get('clan_name'); pw = request.form.get('password')
        if not name or not pw: flash('Felder fehlen.', 'error')
        elif Clan.query.filter_by(name=name).first(): flash('Name vergeben.', 'error')
        else:
            db.session.add(Clan(name=name, password=generate_password_hash(pw, method='pbkdf2:sha256')))
            db.session.commit(); flash('Registriert!', 'success'); return redirect(url_for('auth.login'))
    return render_template('register_clan.html')