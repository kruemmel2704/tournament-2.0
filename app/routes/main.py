from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, current_app
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from app.models import User, TeamMember, Tournament, Cup, League, Clan, Match, Map
from app.extensions import db
from sqlalchemy import func
from datetime import datetime, timedelta
import os
import json
import secrets

main_bp = Blueprint('main', __name__)

@main_bp.before_app_request
def check_first_run():
    # Ausnahmen: Statische Dateien (CSS/JS) und die Setup-Seite selbst nicht blockieren
    if request.endpoint and ('static' in request.endpoint or 'main.setup' in request.endpoint or 'main.do_setup' in request.endpoint):
        return

    # Prüfen, ob IRGENDEIN Admin existiert
    admin_exists = User.query.filter_by(is_admin=True).first()
    
    # Wenn KEIN Admin da ist -> Ab zum Setup!
    if not admin_exists:
        return redirect(url_for('main.setup'))

# --- SETUP ROUTEN ---
@main_bp.route('/setup', methods=['GET'])
def setup():
    # Sicherheitscheck: Wenn schon ein Admin da ist, darf man hier nicht mehr hin
    if User.query.filter_by(is_admin=True).first():
        return redirect(url_for('main.dashboard'))
    return render_template('setup.html')

@main_bp.route('/setup', methods=['POST'])
def do_setup():
    # Doppelt hält besser: Check ob schon Admin da
    if User.query.filter_by(is_admin=True).first():
        return redirect(url_for('main.dashboard'))
        
    username = request.form.get('username')
    password = request.form.get('password')
    
    if username and password:
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        # Erster User ist Admin UND Mod
        new_admin = User(username=username, password=hashed_pw, is_admin=True, is_mod=True)
        db.session.add(new_admin)
        db.session.commit()
        flash('Installation erfolgreich! Bitte einloggen.', 'success')
        return redirect(url_for('auth.login')) # Oder main.dashboard wenn auto-login gewünscht
    
    flash('Bitte beide Felder ausfüllen.', 'error')
    return redirect(url_for('main.setup'))

# --- DASHBOARD ---
@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    active_tournaments = Tournament.query.filter_by(is_archived=False).all()
    archived_tournaments = Tournament.query.filter_by(is_archived=True).all()
    active_cups = Cup.query.filter_by(is_archived=False).all()
    archived_cups = Cup.query.filter_by(is_archived=True).all()
    active_leagues = League.query.filter_by(is_archived=False).all()
    archived_leagues = League.query.filter_by(is_archived=True).all()

    return render_template('dashboard.html',
                           active_tournaments=active_tournaments, archived_tournaments=archived_tournaments,
                           active_cups=active_cups, archived_cups=archived_cups,
                           active_leagues=active_leagues, archived_leagues=archived_leagues)

# --- CLAN / USERS MANAGER (NEU) ---
@main_bp.route('/users')
@login_required
def users():
    if not current_user.is_admin:
        flash('Kein Zugriff.', 'error')
        return redirect(url_for('main.dashboard'))
    
    clans = Clan.query.all()
    moderators = User.query.filter_by(is_mod=True).all()
    
    # Freie Teams: Kein Clan, kein Admin/Mod/ClanAdmin
    users_no_clan = User.query.filter(
        User.clan_id == None,
        User.is_admin == False, 
        User.is_mod == False,
        User.is_clan_admin == False
    ).all()

    return render_template('users.html', clans=clans, moderators=moderators, users_no_clan=users_no_clan)

@main_bp.route('/create_clan', methods=['POST'])
@login_required
def create_clan():
    if not current_user.is_admin:
        flash('Kein Zugriff.', 'error')
        return redirect(url_for('main.dashboard'))

    clan_name = request.form.get('clan_name', '').strip()
    password = request.form.get('password') # Das neue Passwort-Feld

    if not clan_name or not password:
        flash('Name und Passwort erforderlich.', 'error')
        return redirect(url_for('main.users'))

    # Case-Insensitive Prüfung auf Duplikate
    if Clan.query.filter(func.lower(Clan.name) == clan_name.lower()).first() or \
       User.query.filter(func.lower(User.username) == clan_name.lower()).first():
        flash('Name bereits vergeben.', 'error')
        return redirect(url_for('main.users'))

    try:
        # 1. Clan erstellen (OHNE Passwort)
        new_clan = Clan(name=clan_name)
        db.session.add(new_clan)
        db.session.commit()

        # 2. Admin User erstellen (MIT Passwort)
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        admin_user = User(
            username=clan_name,
            password=hashed_pw,
            is_clan_admin=True,
            clan_id=new_clan.id,
            token=secrets.token_hex(4)
        )
        db.session.add(admin_user)
        db.session.commit()
        
        flash(f'Clan "{clan_name}" erstellt.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Datenbankfehler: {str(e)}', 'error')

    return redirect(url_for('main.users'))


# --- CLAN DASHBOARD (USER VIEW) ---
@main_bp.route('/clan_dashboard')
@login_required
def clan_dashboard():
    if not current_user.is_clan_admin:
        flash('Nur für Clan-Leiter.', 'error')
        return redirect(url_for('main.dashboard'))
    
    my_clan = Clan.query.get(current_user.clan_id)
    # Freie Agents (Kein Clan, kein Admin/Mod/Clan-Admin)
    free_agents = User.query.filter_by(clan_id=None, is_admin=False, is_mod=False, is_clan_admin=False).all()
    
    return render_template('clan_dashboard.html', clan=my_clan, free_agents=free_agents)

@main_bp.route('/clan/create_team', methods=['POST'])
@login_required
def clan_create_team():
    if not current_user.is_clan_admin: return redirect(url_for('main.dashboard'))

    team_name = request.form.get('team_name')
    if User.query.filter_by(username=team_name).first():
        flash('Name vergeben.', 'error')
        return redirect(url_for('main.clan_dashboard'))

    token = secrets.token_hex(4)
    new_team = User(username=team_name, token=token, clan_id=current_user.clan_id)
    db.session.add(new_team)
    db.session.commit()
    flash(f'Team "{team_name}" erstellt! Token: {token}', 'success')
    return redirect(url_for('main.clan_dashboard'))

@main_bp.route('/clan/remove_member/<int:user_id>', methods=['POST'])
@login_required
def clan_remove_member(user_id):
    if not current_user.is_clan_admin: return redirect(url_for('main.dashboard'))
    user = User.query.get_or_404(user_id)
    if user.clan_id == current_user.clan_id:
        user.clan_id = None
        db.session.commit()
        flash('Team entfernt.', 'success')
    return redirect(url_for('main.clan_dashboard'))

@main_bp.route('/clan/add_member/<int:user_id>', methods=['POST'])
@login_required
def clan_add_member(user_id):
    if not current_user.is_clan_admin: return redirect(url_for('main.dashboard'))
    user = User.query.get_or_404(user_id)
    if user.clan_id is None:
        user.clan_id = current_user.clan_id
        db.session.commit()
        flash('Team aufgenommen.', 'success')
    return redirect(url_for('main.clan_dashboard'))

@main_bp.route('/clan/change_password', methods=['POST'])
@login_required
def clan_change_password():
    if not current_user.is_clan_admin: return redirect(url_for('main.dashboard'))
    cur = request.form.get('current_password')
    new = request.form.get('new_password')
    conf = request.form.get('confirm_password')
    
    if not check_password_hash(current_user.password, cur) or new != conf:
        flash('Fehler beim Passwort ändern.', 'error')
    else:
        current_user.password = generate_password_hash(new, method='pbkdf2:sha256')
        db.session.commit()
        flash('Passwort geändert.', 'success')
    return redirect(url_for('main.clan_dashboard'))

# --- ROSTER (TEAM MEMBERS) ---
@main_bp.route('/add_member', methods=['POST'])
@login_required
def add_member():
    gamertag = request.form.get('gamertag')
    activision_id = request.form.get('activision_id')
    platform = request.form.get('platform')
    
    if gamertag and activision_id and platform:
        db.session.add(TeamMember(gamertag=gamertag, activision_id=activision_id, platform=platform, owner_id=current_user.id))
        db.session.commit()
        flash('Mitglied hinzugefügt.', 'success')
    return redirect(url_for('main.dashboard'))

@main_bp.route('/delete_member/<int:member_id>', methods=['POST'])
@login_required
def delete_member(member_id):
    m = TeamMember.query.get_or_404(member_id)
    if m.owner_id == current_user.id:
        db.session.delete(m)
        db.session.commit()
        flash('Gelöscht.', 'success')
    return redirect(url_for('main.dashboard'))

# --- MODERATOR ---
@main_bp.route('/mod_change_password', methods=['POST'])
@login_required
def mod_change_password():
    if not current_user.is_mod: return redirect(url_for('main.dashboard'))
    cur = request.form.get('current_password')
    new = request.form.get('new_password')
    conf = request.form.get('confirm_password')
    if check_password_hash(current_user.password, cur) and new == conf:
        current_user.password = generate_password_hash(new, method='pbkdf2:sha256')
        db.session.commit()
        flash('Passwort geändert.', 'success')
    else:
        flash('Fehler.', 'error')
    return redirect(url_for('main.dashboard'))

# --- RULES & PWA ---
@main_bp.route('/sw.js')
def service_worker():
    res = send_from_directory(os.path.join(current_app.root_path, 'static'), 'sw.js')
    res.headers['Content-Type'] = 'application/javascript'
    res.headers['Cache-Control'] = 'no-cache'
    return res

@main_bp.route('/rules')
def rules():
    content = None
    fp = os.path.join(current_app.root_path, 'static', 'rules_content.json')
    if os.path.exists(fp):
        try:
            with open(fp, 'r', encoding='utf-8') as f: content = json.load(f).get('content')
        except: pass
    return render_template('rules.html', custom_content=content)

@main_bp.route('/save_rules', methods=['POST'])
@login_required
def save_rules():
    if not current_user.is_admin: return jsonify({'success': False}), 403
    fp = os.path.join(current_app.root_path, 'static', 'rules_content.json')
    try:
        with open(fp, 'w', encoding='utf-8') as f: json.dump({'content': request.get_json().get('content')}, f)
        return jsonify({'success': True})
    except Exception as e: return jsonify({'success': False, 'msg': str(e)}), 500

@main_bp.route('/reset_rules', methods=['POST'])
@login_required
def reset_rules():
    if not current_user.is_admin: return jsonify({'success': False}), 403
    fp = os.path.join(current_app.root_path, 'static', 'rules_content.json')
    if os.path.exists(fp): os.remove(fp)
    return jsonify({'success': True})

@main_bp.route('/players')
@login_required
def player_list():
    # Zugriff nur für Admin oder Mod
    if not (current_user.is_admin or current_user.is_mod):
        flash('Kein Zugriff.', 'error')
        return redirect(url_for('main.dashboard'))

    # Alle Spieler laden, sortiert nach Gamertag
    # Durch .join(User) können wir auch nach Clan filtern/sortieren
    players = TeamMember.query.join(User).all()
    
    return render_template('players_overview.html', players=players)

@main_bp.route('/ban_player/<int:member_id>', methods=['POST'])
@login_required
def ban_player(member_id):
    if not (current_user.is_admin or current_user.is_mod):
        return redirect(url_for('main.dashboard'))
    
    member = TeamMember.query.get_or_404(member_id)
    action = request.form.get('action') # 'unban', '24h', '7d', 'perm'
    
    if action == 'unban':
        member.banned_until = None
        member.ban_reason = None
        flash(f'{member.gamertag} wurde entbannt.', 'success')
        
    elif action in ['24h', '7d', 'perm']:
        now = datetime.now()
        if action == '24h':
            member.banned_until = now + timedelta(days=1)
            duration = "24 Stunden"
        elif action == '7d':
            member.banned_until = now + timedelta(days=7)
            duration = "7 Tage"
        elif action == 'perm':
            member.banned_until = now + timedelta(days=365*100) # 100 Jahre = Permanent
            duration = "Permanent"
            
        member.ban_reason = request.form.get('reason', 'Verstoß gegen Regeln')
        flash(f'{member.gamertag} wurde gebannt ({duration}).', 'error')

    db.session.commit()
    return redirect(url_for('main.player_list'))