from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import Tournament, Match, User, Map
from app.extensions import db
import json, random, math

tournament_bp = Blueprint('tournament', __name__)

# --- NEUE ROUTE: TURNIERBAUM ANZEIGEN ---
@tournament_bp.route('/tournament_tree/<int:tournament_id>')
@login_required
def tournament_tree(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    
    # Matches nach Runden gruppieren
    rounds = {}
    for m in tournament.matches:
        if m.round_number not in rounds:
            rounds[m.round_number] = []
        rounds[m.round_number].append(m)
    
    sorted_rounds = []
    for r in sorted(rounds.keys()):
        sorted_matches = sorted(rounds[r], key=lambda x: x.match_index)
        sorted_rounds.append(sorted_matches)

    # --- LOGIK FÜR HERO CARD ---
    next_match = None
    if not current_user.is_admin: # Admins spielen meist nicht selbst
        # Finde alle Matches, wo der User beteiligt ist UND die noch nicht vorbei sind
        my_matches = [
            m for m in tournament.matches 
            if (m.team_a == current_user.username or m.team_b == current_user.username) 
            and m.state != 'finished'
        ]
        
        # Wenn es Matches gibt, ist das mit der niedrigsten Rundennummer das nächste
        if my_matches:
            my_matches.sort(key=lambda x: x.round_number)
            next_match = my_matches[0]

    return render_template('tournament/view.html', tournament=tournament, rounds=sorted_rounds, next_match=next_match)

# --- PICK / BAN LOGIK (Kopie aus league.py wie gewünscht) ---
def handle_pick_ban_logic(match, selected_map):
    current_banned = match.get_banned()
    current_picked = match.get_picked()
    
    # Prüfen, ob Karte schon weg ist
    if selected_map in current_banned or selected_map in current_picked: 
        return False, "Karte bereits vergeben."

    # --- BAN LOGIK (2 Bans pro Team pro Phase) ---
    if match.state == 'ban_1_a':
        current_banned.append(selected_map)
        if len(current_banned) >= 2: match.state = 'ban_1_b'
        
    elif match.state == 'ban_1_b':
        current_banned.append(selected_map)
        # 2 von A + 2 von B = 4 Karten total
        if len(current_banned) >= 4: match.state = 'ban_2_a'
        
    elif match.state == 'ban_2_a':
        current_banned.append(selected_map)
        # 4 davor + 2 von A = 6 Karten total
        if len(current_banned) >= 6: match.state = 'ban_2_b'
        
    elif match.state == 'ban_2_b':
        current_banned.append(selected_map)
        # 6 davor + 2 von B = 8 Karten total -> Ab zum Pick
        if len(current_banned) >= 8: match.state = 'pick_a'

    # --- PICK LOGIK (A pickt 2, dann B pickt 2) ---
    elif match.state == 'pick_a':
        current_picked.append(selected_map)
        if len(current_picked) >= 2: match.state = 'pick_b'
        
    elif match.state == 'pick_b':
        current_picked.append(selected_map)
        # 2 von A + 2 von B = 4 Karten total -> Scoring
        if len(current_picked) >= 4: match.state = 'scoring_phase'
    
    match.banned_maps = json.dumps(current_banned)
    match.picked_maps = json.dumps(current_picked)
    return True, "Erfolgreich."

def advance_winner(match):
    if not match.next_match_id: return
    nm = Match.query.get(match.next_match_id)
    if not nm: return
    
    wa, wb = match.get_map_wins()
    if wa > wb: win = match.team_a
    elif wb > wa: win = match.team_b
    else: win = match.team_a if match.total_score_a > match.total_score_b else match.team_b

    if match.match_index % 2 == 0: nm.team_a = win
    else: nm.team_b = win
    
    # Wenn beide Gegner im nächsten Match feststehen, startet Ban Phase
    if nm.team_a != "TBD" and nm.team_b != "TBD": 
        nm.state = 'ban_1_a'
        
    db.session.commit()

def handle_scoring_logic(match, form_data, user):
    try:
        sa = [max(0, int(form_data.get(f'score_a_{i}',0))) for i in range(1, 6)]
        sb = [max(0, int(form_data.get(f'score_b_{i}',0))) for i in range(1, 6)]
    except: return
    
    if user.is_admin or user.is_mod:
        match.scores_a = json.dumps(sa); match.scores_b = json.dumps(sb)
        match.state = 'finished'; match.draft_a_scores=None; match.draft_b_scores=None
        advance_winner(match)
        return
        
    isa = (user.username == match.team_a); isb = (user.username == match.team_b)
    if not (isa or isb): return
    
    bundle = {'a':sa, 'b':sb}
    if isa: match.draft_a_scores = json.dumps(bundle)
    elif isb: match.draft_b_scores = json.dumps(bundle)
    
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
        # Power of 2 Check (vereinfacht: fülle mit "BYE" auf wenn nötig, hier basic)
        t = Tournament(name=request.form.get('tournament_name')); db.session.add(t); db.session.commit()
        
        # Runde 1 erstellen
        for i in range(0, len(sel), 2): 
            # Falls ungerade Anzahl: Letzter kriegt Freilos (hier vereinfacht angenommen gerade oder Modulo Logik)
            p1 = sel[i]
            p2 = sel[i+1] if i+1 < len(sel) else "BYE"
            # State ist ban_1_a
            db.session.add(Match(tournament_id=t.id, team_a=p1, team_b=p2, state='ban_1_a', round_number=1, match_index=i//2))
        db.session.commit()
        
        # Folgerunden generieren (Logarithmus zur Basis 2)
        prev = [m for m in t.matches if m.round_number==1]
        rounds_total = int(math.ceil(math.log2(len(sel))))
        
        for r in range(2, rounds_total + 1):
            curr = []
            matches_in_round = len(prev)//2 + len(prev)%2
            for i in range(matches_in_round):
                # TBD vs TBD
                db.session.add(Match(tournament_id=t.id, team_a="TBD", team_b="TBD", state='waiting', round_number=r, match_index=i))
                curr.append(Match.query.all()[-1]) # Hacky um ID zu bekommen
            db.session.commit()
            
            # Verknüpfung setzen
            for idx, pm in enumerate(prev):
                pm.next_match_id = curr[idx//2].id
            db.session.commit()
            prev = curr
            
        return redirect(url_for('main.dashboard'))
    return render_template('tournament/create.html', users=User.query.filter_by(is_admin=False, is_mod=False).all())

@tournament_bp.route('/match/<int:match_id>', methods=['GET', 'POST'])
@login_required
def match_view(match_id):
    match = Match.query.get_or_404(match_id)
    # Redirect zum Tree, wenn Match noch "waiting" oder "TBD" ist
    if match.team_a == "TBD" or match.team_b == "TBD":
        flash("Match steht noch nicht fest.", "info")
        return redirect(url_for('tournament.tournament_tree', tournament_id=match.tournament_id))

    active = match.team_a if match.state.endswith('_a') else (match.team_b if match.state.endswith('_b') else None)
    
    if request.method == 'POST':
        if 'selected_map' in request.form and (current_user.is_admin or current_user.username == active):
            success, msg = handle_pick_ban_logic(match, request.form.get('selected_map'))
            if success: db.session.commit()
            else: flash(msg, "error")
        elif 'submit_scores' in request.form:
            handle_scoring_logic(match, request.form, current_user); db.session.commit()
        elif 'lobby_code' in request.form:
            match.lobby_code = request.form.get('lobby_code'); db.session.commit()
        return redirect(url_for('tournament.match_view', match_id=match.id))
        
    return render_template('tournament/match.html', match=match, all_maps=Map.query.filter_by(is_archived=False).all(), banned=match.get_banned(), picked=match.get_picked(), active_team=active)

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