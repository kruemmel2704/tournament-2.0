from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import Cup, CupMatch, User, Map
from app.extensions import db
import json

cup_bp = Blueprint('cup', __name__)

@cup_bp.route('/create_cup', methods=['GET', 'POST'])
@login_required
def create_cup():
    if not current_user.is_admin: return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        c = Cup(name=request.form.get('cup_name'), participants=json.dumps(request.form.getlist('selected_users'))); db.session.add(c); db.session.commit()
        teams = request.form.getlist('selected_users'); 
        if len(teams)%2!=0: teams.append(None)
        for r in range(len(teams)-1):
            for i in range(len(teams)//2):
                if teams[i] and teams[len(teams)-1-i]: db.session.add(CupMatch(cup_id=c.id, team_a=teams[i], team_b=teams[len(teams)-1-i], current_picker=teams[i], round_number=r+1))
            teams.insert(1, teams.pop())
        db.session.commit(); return redirect(url_for('main.dashboard'))
    return render_template('create_cup.html', users=User.query.filter_by(is_admin=False, is_mod=False).all())

@cup_bp.route('/cup/<int:cup_id>')
@login_required
def cup_details(cup_id):
    cup = Cup.query.get_or_404(cup_id)
    standings = {user: {'played': 0, 'won_matches': 0, 'lost_matches': 0, 'draw_matches': 0, 'own_score': 0, 'opp_score': 0} for user in cup.get_participants()}
    for m in cup.matches:
        if m.state == 'finished':
            wa, wb = m.get_map_wins(); sum_a = sum(m.get_scores_a()); sum_b = sum(m.get_scores_b())
            if m.team_a in standings:
                s=standings[m.team_a]; s['played']+=1; s['own_score']+=sum_a; s['opp_score']+=sum_b
                if wa>wb: s['won_matches']+=1
                elif wb>wa: s['lost_matches']+=1
                else: s['draw_matches']+=1
            if m.team_b in standings:
                s=standings[m.team_b]; s['played']+=1; s['own_score']+=sum_b; s['opp_score']+=sum_a
                if wb>wa: s['won_matches']+=1
                elif wa>wb: s['lost_matches']+=1
                else: s['draw_matches']+=1
    return render_template('cup_details.html', cup=cup, standings=sorted(standings.items(), key=lambda x:x[1]['own_score'], reverse=True))

@cup_bp.route('/cup_match/<int:match_id>', methods=['GET', 'POST'])
@login_required
def cup_match_view(match_id):
    match = CupMatch.query.get_or_404(match_id)
    if not (current_user.is_admin or current_user.is_mod or current_user.username in [match.team_a, match.team_b]):
        flash("Kein Zugriff.", "error"); return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        if 'set_maps' in request.form and (current_user.is_admin or current_user.is_mod):
            selected = [request.form.get(f'map_{i}') for i in range(1, 4)]
            match.picked_maps = json.dumps(selected); match.state = 'waiting_for_code'; db.session.commit()
        elif 'set_lobby_code' in request.form and (current_user.is_admin or current_user.is_mod):
            match.lobby_code = request.form.get('lobby_code'); match.state = 'in_progress'; db.session.commit()
        elif 'submit_scores' in request.form and (current_user.is_admin or current_user.is_mod):
            try:
                sa = [int(request.form.get(f'score_a_{i}', 0)) for i in range(1, 4)]
                sb = [int(request.form.get(f'score_b_{i}', 0)) for i in range(1, 4)]
                match.scores_a = json.dumps(sa); match.scores_b = json.dumps(sb); match.state = 'finished'
                db.session.commit(); flash("Gespeichert.", "success")
            except: flash("Fehler.", "error")
        return redirect(url_for('cup.cup_match_view', match_id=match.id))
    return render_template('cup_match.html', match=match, all_maps=Map.query.filter_by(is_archived=False).all(), picked=match.get_picked())

@cup_bp.route('/archive_cup/<int:cup_id>', methods=['POST'])
@login_required
def archive_cup(cup_id):
    if current_user.is_admin: c = Cup.query.get_or_404(cup_id); c.is_archived = not c.is_archived; db.session.commit()
    return redirect(url_for('main.dashboard'))

@cup_bp.route('/delete_cup/<int:cup_id>', methods=['POST'])
@login_required
def delete_cup(cup_id):
    if current_user.is_admin: db.session.delete(Cup.query.get_or_404(cup_id)); db.session.commit()
    return redirect(url_for('main.dashboard'))