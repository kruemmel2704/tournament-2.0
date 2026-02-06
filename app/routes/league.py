from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import League, LeagueMatch, User, Map
from app.extensions import db
import json

league_bp = Blueprint('league', __name__)

def handle_pick_ban_logic(match, selected_map):
    current_banned = match.get_banned(); current_picked = match.get_picked()
    if selected_map in current_banned or selected_map in current_picked: return False
    if match.state == 'ban_1_a': current_banned.append(selected_map); match.state = 'ban_1_b'
    elif match.state == 'ban_1_b': current_banned.append(selected_map); match.state = 'ban_2_a'
    elif match.state == 'ban_2_a': current_banned.append(selected_map); match.state = 'ban_2_b'
    elif match.state == 'ban_2_b': current_banned.append(selected_map); match.state = 'pick_a'
    elif match.state == 'pick_a': current_picked.append(selected_map); match.state = 'pick_b' if len(current_picked) < 5 else 'scoring_phase'
    elif match.state == 'pick_b': current_picked.append(selected_map); match.state = 'pick_a' if len(current_picked) < 5 else 'scoring_phase'
    match.banned_maps = json.dumps(current_banned); match.picked_maps = json.dumps(current_picked)
    return True

def handle_scoring_logic(match, form_data, user):
    try:
        sa = [max(0, int(form_data.get(f'score_a_{i}',0))) for i in range(1, 6)]
        sb = [max(0, int(form_data.get(f'score_b_{i}',0))) for i in range(1, 6)]
    except: return False
    lineup_list = form_data.getlist('lineup_member')
    
    if user.is_admin or user.is_mod:
        match.scores_a = json.dumps(sa); match.scores_b = json.dumps(sb); match.state = 'finished'
        return True
        
    isa = (user.username == match.team_a); isb = (user.username == match.team_b)
    if not (isa or isb): return False
    
    if isa: 
        match.draft_a_scores = json.dumps({'a':sa, 'b':sb}); match.draft_a_lineup = json.dumps(lineup_list)
    elif isb: 
        match.draft_b_scores = json.dumps({'a':sa, 'b':sb}); match.draft_b_lineup = json.dumps(lineup_list)
    
    if match.draft_a_scores and match.draft_b_scores:
        if match.draft_a_scores == match.draft_b_scores:
            match.scores_a = json.dumps(sa); match.scores_b = json.dumps(sb); match.state = 'confirming'
        else: match.state = 'conflict'
    else: match.state = 'waiting_for_confirmation'
    return True

@league_bp.route('/create_league', methods=['GET', 'POST'])
@login_required
def create_league():
    if not current_user.is_admin: return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        l = League(name=request.form.get('league_name'), participants=json.dumps(request.form.getlist('selected_users'))); db.session.add(l); db.session.commit()
        teams = request.form.getlist('selected_users')
        if len(teams)%2!=0: teams.append(None)
        for r in range(len(teams)-1):
            for i in range(len(teams)//2):
                if teams[i] and teams[len(teams)-1-i]: db.session.add(LeagueMatch(league_id=l.id, team_a=teams[i], team_b=teams[len(teams)-1-i], round_number=r+1))
            teams.insert(1, teams.pop())
        db.session.commit(); return redirect(url_for('main.dashboard'))
    return render_template('create_league.html', users=User.query.filter_by(is_admin=False, is_mod=False).all())

@league_bp.route('/league/<int:league_id>')
def league_details(league_id):
    league = League.query.get_or_404(league_id)
    standings = {user: {'played': 0, 'won_matches': 0, 'lost_matches': 0, 'draw_matches': 0, 'own_score': 0, 'opp_score': 0} for user in league.get_participants()}
    for m in league.matches:
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
    return render_template('league_details.html', league=league, standings=sorted(standings.items(), key=lambda x:x[1]['own_score'], reverse=True))

@league_bp.route('/league_match/<int:match_id>', methods=['GET', 'POST'])
@login_required
def league_match_view(match_id):
    match = LeagueMatch.query.get_or_404(match_id)
    active = match.team_a if match.state.endswith('_a') else (match.team_b if match.state.endswith('_b') else None)
    if request.method == 'POST':
        if 'selected_map' in request.form and (current_user.is_admin or current_user.username == active):
            handle_pick_ban_logic(match, request.form.get('selected_map')); db.session.commit()
        elif 'submit_scores' in request.form:
            handle_scoring_logic(match, request.form, current_user); db.session.commit()
        elif 'confirm_lineup' in request.form:
            if current_user.username == match.team_a: match.confirmed_a=True
            elif current_user.username == match.team_b: match.confirmed_b=True
            if match.confirmed_a and match.confirmed_b:
                match.state = 'finished'; match.lineup_a = match.draft_a_lineup; match.lineup_b = match.draft_b_lineup
            db.session.commit()
        elif 'lobby_code' in request.form:
            match.lobby_code = request.form.get('lobby_code'); db.session.commit()
        return redirect(url_for('league.league_match_view', match_id=match.id))
    return render_template('league_match.html', match=match, all_maps=Map.query.filter_by(is_archived=False).all(), banned=match.get_banned(), picked=match.get_picked(), active_team=active)

@league_bp.route('/archive_league/<int:league_id>', methods=['POST'])
@login_required
def archive_league(league_id):
    if current_user.is_admin: l = League.query.get_or_404(league_id); l.is_archived = not l.is_archived; db.session.commit()
    return redirect(url_for('main.dashboard'))

@league_bp.route('/delete_league/<int:league_id>', methods=['POST'])
@login_required
def delete_league(league_id):
    if current_user.is_admin: db.session.delete(League.query.get_or_404(league_id)); db.session.commit()
    return redirect(url_for('main.dashboard'))