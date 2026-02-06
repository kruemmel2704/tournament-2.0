from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, current_app
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from app.models import User, TeamMember, Tournament, Cup, League, Clan, Match, Map
from app.extensions import db
import os
import json
import secrets

main_bp = Blueprint('main', __name__)

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

# --- CLAN DASHBOARD ---
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
    # ... Logik vereinfacht, da oben identisch implementiert ...
    # Hier kurz halten oder Copy-Paste von vorher, Prinzip ist gleich
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