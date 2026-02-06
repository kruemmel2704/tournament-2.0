from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import Tournament, Match, User, Map
from app.extensions import db
import json, random, math

tournament_bp = Blueprint('tournament', __name__)

def handle_pick_ban_logic(match, selected_map):
    current_banned = match.get_banned()
    current_picked = match.get_picked()
    if selected_map in current_banned or selected_map in current_picked: return False
    if match.state == 'ban_1_a': current_banned.append(selected_map); match.state = 'ban_1_b'
    elif match.state == 'ban_1_b': current_banned.append(selected_map); match.state = 'ban_2_a'
    elif match.state == 'ban_2_a': current_banned.append(selected_map); match.state = 'ban_2_b'
    elif match.state == 'ban_2_b': current_banned.append(selected_map); match.state = 'pick_a'
    elif match.state == 'pick_a': current_picked.append(selected_map); match.state = 'pick_b' if len(current_picked) < 5 else 'scoring_phase'
    elif match.state == 'pick_b': current_picked.append(selected_map); match.state = 'pick_a' if len(current_picked) < 5 else 'scoring_phase'
    match.banned_maps = json.dumps(current_banned); match.picked_maps = json.dumps(current_picked)
    return True

def advance_winner(match):
    if not match.next_match_id: return
    nm = Match.query.get(match.next_match_id)
    wa, wb = match.get_map_wins()
    win = match.team_a if wa > wb else (match.team_b if wb > wa else (match.team_a if match.total_score_a > match.total_score_b else match.team_b))
    if match.match_index % 2 == 0: nm.team_a = win
    else: nm.team_b = win
    if nm.team_a != "TBD" and nm.team_b != "TBD": nm.state = 'ban_1_a'
    db.session.commit()

def handle_scoring_logic(match, form_data, user):
    sa = [max(0, int(form_data.get(f'score_a_{i}',0))) for i in range(1, 6)]
    sb = [max(0, int(form_data.get(f'score_b_{i}',0))) for i in range(1, 6)]
    
    if user.is_admin or user.is_mod:
        match.scores_a = json.dumps(sa); match.scores_b = json.dumps(sb)
        match.state = 'finished'; match.draft_a_scores=None; match.draft_b_scores=None
        advance_winner(match)
        return
        
    isa = (user.username == match.team_a); isb = (user.username == match.team_b)
    if not (isa or isb): return
    if isa: match.draft_a_scores = json.dumps({'a':sa, 'b':sb})
    elif isb: match.draft_b_scores = json.dumps({'a':sa, 'b':sb})
    
    if match.draft_a_scores and match.draft_b_scores:
        if match.draft_a_scores == match.draft_b_scores:
            match.scores_a = json.dumps(sa); match.scores_b = json.dumps(sb); match.state = 'finished'; advance_winner(match)
        else: match.state = 'conflict'
    else: match.state = 'waiting_for_confirmation'

@tournament_bp.route('/create_tournament', methods=['GET', 'POST'])
@login_required
def create_tournament():
    if not current_user.is_admin: return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        sel = request.form.getlist('selected_users'); random.shuffle(sel)
        t = Tournament(name=request.form.get('tournament_name')); db.session.add(t); db.session.commit()
        for i in range(0, len(sel), 2): db.session.add(Match(tournament_id=t.id, team_a=sel[i], team_b=sel[i+1], state='ban_1_a', round_number=1, match_index=i//2))
        db.session.commit()
        prev = [m for m in t.matches if m.round_number==1]
        for r in range(2, int(math.ceil(math.log2(len(sel))))+1):
            curr = []
            for i in range(len(prev)//2 + len(prev)%2):
                db.session.add(Match(tournament_id=t.id, team_a="TBD", team_b="TBD", state='waiting', round_number=r, match_index=i)); curr.append(Match.query.all()[-1])
            db.session.commit(); 
            for idx, pm in enumerate(prev): pm.next_match_id = curr[idx//2].id
            db.session.commit(); prev = curr
        return redirect(url_for('main.dashboard'))
    return render_template('create_tournament.html', users=User.query.filter_by(is_admin=False, is_mod=False).all())

@tournament_bp.route('/match/<int:match_id>', methods=['GET', 'POST'])
@login_required
def match_view(match_id):
    match = Match.query.get_or_404(match_id)
    active = match.team_a if match.state.endswith('_a') else (match.team_b if match.state.endswith('_b') else None)
    if request.method == 'POST':
        if 'selected_map' in request.form and (current_user.is_admin or current_user.username == active):
            handle_pick_ban_logic(match, request.form.get('selected_map')); db.session.commit()
        elif 'submit_scores' in request.form:
            handle_scoring_logic(match, request.form, current_user); db.session.commit()
        elif 'lobby_code' in request.form:
            match.lobby_code = request.form.get('lobby_code'); db.session.commit()
        return redirect(url_for('tournament.match_view', match_id=match.id))
    return render_template('match.html', match=match, all_maps=Map.query.filter_by(is_archived=False).all(), banned=match.get_banned(), picked=match.get_picked(), active_team=active)

@tournament_bp.route('/archive_tournament/<int:t_id>', methods=['POST'])
@login_required
def archive_tournament(t_id):
    if current_user.is_admin: t = Tournament.query.get_or_404(t_id); t.is_archived = not t.is_archived; db.session.commit()
    return redirect(url_for('main.dashboard'))

@tournament_bp.route('/delete_tournament/<int:t_id>', methods=['POST'])
@login_required
def delete_tournament(t_id):
    if current_user.is_admin: db.session.delete(Tournament.query.get_or_404(t_id)); db.session.commit()
    return redirect(url_for('main.dashboard'))