from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from app.models import Tournament, Cup, League, Map, User, Clan, Member
from app.extensions import db
from app.utils import clan_required
import random, secrets

main_bp = Blueprint('main', __name__)

@main_bp.route('/dashboard')
@login_required
def dashboard():
    all_tournaments = Tournament.query.all()
    return render_template('dashboard.html', 
        active_tournaments=[t for t in all_tournaments if not t.is_archived],
        archived_tournaments=[t for t in all_tournaments if t.is_archived],
        active_cups=Cup.query.filter_by(is_archived=False).all(),
        archived_cups=Cup.query.filter_by(is_archived=True).all(),
        active_leagues=League.query.filter_by(is_archived=False).all(),
        archived_leagues=League.query.filter_by(is_archived=True).all(),
        maps=Map.query.filter_by(is_archived=False).all(),
        users=User.query.filter_by(is_admin=False).all(), clans=Clan.query.all(),
        clan_map={u.username: u.clan.name for u in User.query.filter(User.clan_id != None).all()}
    )

@main_bp.route('/rules')
def rules(): return render_template('rules.html')

@main_bp.route('/add_member', methods=['POST'])
@login_required
def add_member():
    db.session.add(Member(user_id=current_user.id, gamertag=request.form.get('gamertag'), activision_id=request.form.get('activision_id'), platform=request.form.get('platform')))
    db.session.commit(); return redirect(url_for('main.dashboard'))

@main_bp.route('/delete_member/<int:member_id>', methods=['POST'])
@login_required
def delete_member(member_id):
    m = Member.query.get_or_404(member_id)
    if m.user_id == current_user.id or current_user.is_admin: db.session.delete(m); db.session.commit()
    return redirect(url_for('main.dashboard'))

@main_bp.route('/clan_dashboard')
@clan_required
def clan_dashboard():
    return render_template('clan_dashboard.html', clan=Clan.query.get(session['clan_id']), free_agents=User.query.filter(User.clan_id == None, User.is_admin == False, User.is_mod == False).all())

@main_bp.route('/clan_add_member/<int:user_id>', methods=['POST'])
@clan_required
def clan_add_member(user_id):
    User.query.get_or_404(user_id).clan_id = session['clan_id']; db.session.commit(); return redirect(url_for('main.clan_dashboard'))

@main_bp.route('/clan_remove_member/<int:user_id>', methods=['POST'])
@clan_required
def clan_remove_member(user_id):
    User.query.get_or_404(user_id).clan_id = None; db.session.commit(); return redirect(url_for('main.clan_dashboard'))

@main_bp.route('/clan_create_team', methods=['POST'])
@clan_required
def clan_create_team():
    c = Clan.query.get(session['clan_id']); name = f"{c.name}.{request.form.get('team_name')}"
    if not User.query.filter_by(username=name).first(): db.session.add(User(username=name, token=str(random.randint(10000,99999)), clan_id=c.id)); db.session.commit(); flash(f'Team {name} erstellt!', 'success')
    return redirect(url_for('main.clan_dashboard'))

@main_bp.route('/clan_change_password', methods=['POST'])
@clan_required
def clan_change_password():
    c = Clan.query.get(session['clan_id'])
    if check_password_hash(c.password, request.form.get('current_password')) and request.form.get('new_password') == request.form.get('confirm_password'):
        c.password = generate_password_hash(request.form.get('new_password'), method='pbkdf2:sha256'); db.session.commit(); flash('PW geändert.', 'success')
    return redirect(url_for('main.clan_dashboard'))