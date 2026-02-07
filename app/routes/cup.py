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
        # 1. Cup Basis anlegen
        participants = request.form.getlist('selected_users')
        new_cup = Cup(name=request.form.get('cup_name'), participants=json.dumps(participants))
        db.session.add(new_cup)
        db.session.commit()
        
        # 2. Weiterleitung zum Zwischenschritt (Kader wählen)
        return redirect(url_for('cup.setup_cup_rosters', cup_id=new_cup.id))
        
    # User laden, die keine Admins/Mods sind (also Teams)
    return render_template('create_cup.html', users=User.query.filter_by(is_admin=False, is_mod=False).all())


@cup_bp.route('/setup_cup_rosters/<int:cup_id>', methods=['GET', 'POST'])
@login_required
def setup_cup_rosters(cup_id):
    if not current_user.is_admin: return redirect(url_for('main.dashboard'))
    cup = Cup.query.get_or_404(cup_id)
    
    # Liste der teilnehmenden Teams (User Objekte) laden
    team_names = cup.get_participants()
    teams_obj = User.query.filter(User.username.in_(team_names)).all()

    if request.method == 'POST':
        # 1. Kader aus Formular auslesen
        cup_rosters = {}
        for team in teams_obj:
            # Holt alle angehakten Spieler für dieses Team
            selected_players = request.form.getlist(f'roster_{team.id}')
            cup_rosters[team.username] = selected_players
        
        cup.rosters = json.dumps(cup_rosters)
        
        # 2. Matches generieren (Round Robin)
        # Wir tragen die gewählten Spieler direkt fest in die Matches ein!
        teams_list = team_names.copy()
        if len(teams_list) % 2 != 0: teams_list.append(None) # Dummy für ungerade Anzahl
        
        # Round Robin Algorithmus
        for r in range(len(teams_list)-1):
            for i in range(len(teams_list)//2):
                t1 = teams_list[i]
                t2 = teams_list[len(teams_list)-1-i]
                
                if t1 and t2:
                    # Lineups direkt aus dem festen Kader holen
                    lineup_a = cup_rosters.get(t1, [])
                    lineup_b = cup_rosters.get(t2, [])
                    
                    match = CupMatch(
                        cup_id=cup.id,
                        team_a=t1,
                        team_b=t2,
                        round_number=r+1,
                        # HIER TRAGEN WIR SIE FEST EIN:
                        lineup_a=json.dumps(lineup_a),
                        lineup_b=json.dumps(lineup_b),
                        confirmed_a=False, # Muss trotzdem noch bestätigt werden (Check-in)
                        confirmed_b=False
                    )
                    db.session.add(match)
            
            teams_list.insert(1, teams_list.pop()) # Rotation

        db.session.commit()
        flash(f"Cup '{cup.name}' erfolgreich gestartet!", "success")
        return redirect(url_for('main.dashboard'))

    return render_template('setup_cup_rosters.html', cup=cup, teams=teams_obj)

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
    
    # 1. Sicherheits-Check: Nur Admins, Mods oder die beteiligten Teams dürfen rein
    if not (current_user.is_admin or current_user.is_mod or current_user.username in [match.team_a, match.team_b]):
        flash("Kein Zugriff.", "error")
        return redirect(url_for('main.dashboard'))

    # 2. Roster (Spieler) der beiden Teams laden für die Auswahl-Boxen
    user_a = User.query.filter_by(username=match.team_a).first()
    members_a = user_a.team_members if user_a else []
    
    user_b = User.query.filter_by(username=match.team_b).first()
    members_b = user_b.team_members if user_b else []

    if request.method == 'POST':
        
        # --- A) TEAM WÄHLT LINEUP (SPIELER) ---
        if 'set_lineup' in request.form:
            # Wir prüfen, wer gerade klickt
            is_team_a = current_user.username == match.team_a
            is_team_b = current_user.username == match.team_b
            
            selected_players = request.form.getlist('selected_players')
            
            # Speichern je nach Team (Admin darf für beide)
            if is_team_a or (current_user.is_admin and request.form.get('team_target') == 'a'):
                match.lineup_a = json.dumps(selected_players)
                match.confirmed_a = False # Wenn sich das Lineup ändert, muss neu bestätigt werden
                flash("Lineup Team A gespeichert.", "success")
                
            elif is_team_b or (current_user.is_admin and request.form.get('team_target') == 'b'):
                match.lineup_b = json.dumps(selected_players)
                match.confirmed_b = False
                flash("Lineup Team B gespeichert.", "success")
                
            db.session.commit()

        # --- B) ADMIN BESTÄTIGT ANWESENHEIT (CHECK-IN) ---
        elif 'confirm_lineups' in request.form and (current_user.is_admin or current_user.is_mod):
            # Checkboxen auswerten
            match.confirmed_a = True if request.form.get('confirm_a') else False
            match.confirmed_b = True if request.form.get('confirm_b') else False
            
            db.session.commit()
            flash("Anwesenheit aktualisiert.", "success")

        # --- C) ADMIN SETZT MAPS ---
        elif 'set_maps' in request.form and (current_user.is_admin or current_user.is_mod):
            selected = [request.form.get(f'map_{i}') for i in range(1, 4)]
            match.picked_maps = json.dumps(selected)
            # Status nur ändern, wenn wir noch ganz am Anfang waren
            if match.state == 'waiting_for_ready':
                match.state = 'waiting_for_code'
            db.session.commit()
            flash("Maps gespeichert.", "success")

        # --- D) LOBBY CODE SETZEN ---
        elif 'set_lobby_code' in request.form and (current_user.is_admin or current_user.is_mod):
            match.lobby_code = request.form.get('lobby_code')
            match.state = 'in_progress'
            db.session.commit()
            flash("Lobby Code gesetzt. Match läuft!", "success")

        # --- E) ERGEBNIS EINTRAGEN ---
        elif 'submit_scores' in request.form and (current_user.is_admin or current_user.is_mod):
            try:
                sa = [int(request.form.get(f'score_a_{i}', 0)) for i in range(1, 4)]
                sb = [int(request.form.get(f'score_b_{i}', 0)) for i in range(1, 4)]
                match.scores_a = json.dumps(sa)
                match.scores_b = json.dumps(sb)
                match.state = 'finished'
                db.session.commit()
                flash("Ergebnis gespeichert.", "success")
            except ValueError:
                flash("Ungültige Eingabe bei den Punkten.", "error")

        # Redirect auf sich selbst (verhindert Form-Resubmit Warnung beim Neuladen)
        return redirect(url_for('cup.cup_match_view', match_id=match.id))

    # Template rendern
    return render_template('cup_match.html', 
                           match=match, 
                           all_maps=Map.query.filter_by(is_archived=False).all(), 
                           picked=match.get_picked(),
                           members_a=members_a, 
                           members_b=members_b)

@cup_bp.route('/delete_cup/<int:cup_id>', methods=['POST'])
@login_required
def delete_cup(cup_id):
    if current_user.is_admin: db.session.delete(Cup.query.get_or_404(cup_id)); db.session.commit()
    return redirect(url_for('main.dashboard'))