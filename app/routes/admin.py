import os
import random
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from app.models import User, Clan, Map
from app.extensions import db
from app.utils import allowed_file

admin_bp = Blueprint('admin', __name__)

@main_bp.route('/users')
@login_required
def users():
    if not current_user.is_admin:
        flash('Kein Zugriff.', 'error')
        return redirect(url_for('main.dashboard'))
    
    clans = Clan.query.all()
    moderators = User.query.filter_by(is_mod=True).all()
    
    # NEU: Auch die Admins laden!
    admins = User.query.filter_by(is_admin=True).all()

    # Freie Teams: Kein Clan, kein Admin/Mod/ClanAdmin
    users_no_clan = User.query.filter(
        User.clan_id == None,
        User.is_admin == False, 
        User.is_mod == False,
        User.is_clan_admin == False
    ).all()

    return render_template('users.html', 
                           clans=clans, 
                           moderators=moderators, 
                           users_no_clan=users_no_clan,
                           admins=admins)  # <--- WICHTIG: Variable hier übergeben

@admin_bp.route('/maps')
@login_required
def maps_manager():
    if not current_user.is_admin: return redirect(url_for('main.dashboard'))
    return render_template('maps.html', active_maps=[m for m in Map.query.all() if not m.is_archived], archived_maps=[m for m in Map.query.all() if m.is_archived])

@admin_bp.route('/create_admin', methods=['POST'])
@login_required
def create_admin():
    if current_user.is_admin: db.session.add(User(username=request.form.get('username'), password=generate_password_hash(request.form.get('password'), method='pbkdf2:sha256'), is_admin=True)); db.session.commit()
    return redirect(url_for('admin.users_manager'))

@admin_bp.route('/create_mod', methods=['POST'])
@login_required
def create_mod():
    if current_user.is_admin: db.session.add(User(username=request.form.get('username'), password=generate_password_hash(request.form.get('password'), method='pbkdf2:sha256'), is_mod=True)); db.session.commit()
    return redirect(url_for('admin.users_manager'))

@admin_bp.route('/create_clan', methods=['POST'])
@login_required
def create_clan():
    if current_user.is_admin: db.session.add(Clan(name=request.form.get('clan_name'), password=generate_password_hash("1234", method='pbkdf2:sha256'))); db.session.commit()
    return redirect(url_for('admin.users_manager'))

@admin_bp.route('/create_user', methods=['POST'])
@login_required
def create_user():
    if current_user.is_admin:
        c_id = request.form.get('clan_id')
        
        # WICHTIGE ÄNDERUNG: Leeren String in None umwandeln!
        if not c_id: 
            c_id = None
        
        raw_name = request.form.get('username')
        
        # Name zusammensetzen (Clan.User oder nur User)
        if c_id:
            final_name = f"{Clan.query.get(c_id).name}.{raw_name}"
        else:
            final_name = raw_name

        if not User.query.filter_by(username=final_name).first():
            db.session.add(User(username=final_name, token=str(random.randint(10000,99999)), clan_id=c_id))
            db.session.commit()
            flash(f'Team {final_name} erstellt!', 'success')
        else:
            flash('Name bereits vergeben.', 'error')

    return redirect(url_for('admin.users_manager'))

@admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.is_admin: db.session.delete(User.query.get_or_404(user_id)); db.session.commit()
    return redirect(url_for('admin.users_manager'))

@admin_bp.route('/delete_clan/<int:clan_id>', methods=['POST'])
@login_required
def delete_clan(clan_id):
    if current_user.is_admin: db.session.delete(Clan.query.get_or_404(clan_id)); db.session.commit()
    return redirect(url_for('admin.users_manager'))

@admin_bp.route('/admin_change_password', methods=['POST'])
@login_required
def admin_change_password():
    if current_user.is_admin and request.form.get('new_password') == request.form.get('confirm_password'):
        current_user.password = generate_password_hash(request.form.get('new_password'), method='pbkdf2:sha256'); db.session.commit(); flash('PW geändert.', 'success')
    return redirect(url_for('admin.users_manager'))

@admin_bp.route('/admin_reset_clan_password/<int:clan_id>', methods=['POST'])
@login_required
def admin_reset_clan_password(clan_id):
    if current_user.is_admin: Clan.query.get_or_404(clan_id).password = generate_password_hash(request.form.get('new_password'), method='pbkdf2:sha256'); db.session.commit()
    return redirect(url_for('admin.users_manager'))

@admin_bp.route('/add_map', methods=['POST'])
@login_required
def add_map():
    if current_user.is_admin:
        for f in request.files.getlist('map_images'):
            if f and allowed_file(f.filename):
                s = secure_filename(f.filename)
                f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], s))
                db.session.add(Map(name=os.path.splitext(f.filename)[0].replace('_',' ').title(), image_file=s))
        db.session.commit()
    return redirect(url_for('admin.maps_manager'))

@admin_bp.route('/archive_map/<int:map_id>', methods=['POST'])
@login_required
def archive_map(map_id):
    if current_user.is_admin: m=Map.query.get_or_404(map_id); m.is_archived=not m.is_archived; db.session.commit()
    return redirect(url_for('admin.maps_manager'))

@admin_bp.route('/delete_map/<int:map_id>', methods=['POST'])
@login_required
def delete_map(map_id):
    if current_user.is_admin: db.session.delete(Map.query.get_or_404(map_id)); db.session.commit()
    return redirect(url_for('admin.maps_manager'))