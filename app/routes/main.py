from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, current_app
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from app.models import User, TeamMember, Tournament, Cup, League
from app.extensions import db
import os
import json

main_bp = Blueprint('main', __name__)

# --- DASHBOARD & HAUPTSEITEN ---

@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Daten für das Dashboard laden
    active_tournaments = Tournament.query.filter_by(is_archived=False).all()
    archived_tournaments = Tournament.query.filter_by(is_archived=True).all()
    
    active_cups = Cup.query.filter_by(is_archived=False).all()
    archived_cups = Cup.query.filter_by(is_archived=True).all()
    
    active_leagues = League.query.filter_by(is_archived=False).all()
    archived_leagues = League.query.filter_by(is_archived=True).all()

    return render_template('dashboard.html',
                           active_tournaments=active_tournaments,
                           archived_tournaments=archived_tournaments,
                           active_cups=active_cups,
                           archived_cups=archived_cups,
                           active_leagues=active_leagues,
                           archived_leagues=archived_leagues)

@main_bp.route('/clan_dashboard')
@login_required
def clan_dashboard():
    # Placeholder für die Clan-Ansicht
    return render_template('clan_dashboard.html') 

# --- MEMBER VERWALTUNG ---

@main_bp.route('/add_member', methods=['POST'])
@login_required
def add_member():
    gamertag = request.form.get('gamertag')
    activision_id = request.form.get('activision_id')
    platform = request.form.get('platform')
    
    if gamertag and activision_id and platform:
        new_member = TeamMember(gamertag=gamertag, activision_id=activision_id, platform=platform, owner_id=current_user.id)
        db.session.add(new_member)
        db.session.commit()
        flash('Mitglied hinzugefügt!', 'success')
    else:
        flash('Bitte alle Felder ausfüllen.', 'error')
        
    return redirect(url_for('main.dashboard'))

@main_bp.route('/delete_member/<int:member_id>', methods=['POST'])
@login_required
def delete_member(member_id):
    member = TeamMember.query.get_or_404(member_id)
    if member.owner_id == current_user.id:
        db.session.delete(member)
        db.session.commit()
        flash('Mitglied entfernt.', 'success')
    else:
        flash('Keine Berechtigung.', 'error')
    return redirect(url_for('main.dashboard'))

# --- MODERATOR FUNKTIONEN ---

@main_bp.route('/mod_change_password', methods=['POST'])
@login_required
def mod_change_password():
    if not current_user.is_mod:
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('main.dashboard'))

    current_pw = request.form.get('current_password')
    new_pw = request.form.get('new_password')
    confirm_pw = request.form.get('confirm_password')

    if not check_password_hash(current_user.password, current_pw):
        flash('Das aktuelle Passwort ist falsch.', 'error')
        return redirect(url_for('main.dashboard'))

    if new_pw != confirm_pw:
        flash('Die neuen Passwörter stimmen nicht überein.', 'error')
        return redirect(url_for('main.dashboard'))

    current_user.password = generate_password_hash(new_pw, method='pbkdf2:sha256')
    db.session.commit()
    
    flash('Passwort erfolgreich geändert!', 'success')
    return redirect(url_for('main.dashboard'))

# --- PWA SERVICE WORKER ---
@main_bp.route('/sw.js')
def service_worker():
    # Dient dazu, die sw.js Datei aus dem static Ordner im Root-Pfad bereitzustellen
    response = send_from_directory(os.path.join(current_app.root_path, 'static'), 'sw.js')
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Cache-Control'] = 'no-cache'
    return response

# --- REGELWERK (EDITIERBAR) ---

@main_bp.route('/rules')
def rules():
    custom_content = None
    # Der Pfad zur JSON-Datei im static Ordner
    file_path = os.path.join(current_app.root_path, 'static', 'rules_content.json')
    
    # Prüfen ob eine bearbeitete Version existiert
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                custom_content = data.get('content')
        except:
            pass # Bei Fehler einfach None lassen -> lädt Original
            
    return render_template('rules.html', custom_content=custom_content)

@main_bp.route('/save_rules', methods=['POST'])
@login_required
def save_rules():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Keine Berechtigung'}), 403
        
    data = request.get_json()
    content = data.get('content')
    file_path = os.path.join(current_app.root_path, 'static', 'rules_content.json')
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({'content': content}, f)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@main_bp.route('/reset_rules', methods=['POST'])
@login_required
def reset_rules():
    if not current_user.is_admin:
        return jsonify({'success': False}), 403
    
    file_path = os.path.join(current_app.root_path, 'static', 'rules_content.json')
    # Datei löschen, damit wieder das Hardcoded-Template angezeigt wird
    if os.path.exists(file_path):
        os.remove(file_path)
        
    return jsonify({'success': True})