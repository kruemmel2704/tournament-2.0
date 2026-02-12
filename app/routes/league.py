from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import League, LeagueMatch, User, Map
from app.extensions import db
import json
from datetime import datetime
from app.utils import get_current_time
from config import Config
try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo

league_bp = Blueprint('league', __name__)

def handle_pick_ban_logic(match, selected_map):
    current_banned = match.get_banned()
    current_picked = match.get_picked()
    
    # Prüfen, ob Karte schon vergeben ist
    if selected_map in current_banned or selected_map in current_picked: 
        return False, "Karte bereits vergeben."
    
    # --- BAN PHASE (2 Bans pro Team pro Runde) ---
    if match.state == 'ban_1_a': 
        current_banned.append(selected_map)
        if len(current_banned) >= 2: match.state = 'ban_1_b'

    elif match.state == 'ban_1_b': 
        current_banned.append(selected_map)
        # 2 von A + 2 von B = 4
        if len(current_banned) >= 4: match.state = 'ban_2_a'

    elif match.state == 'ban_2_a': 
        current_banned.append(selected_map)
        # 4 davor + 2 von A = 6
        if len(current_banned) >= 6: match.state = 'ban_2_b'

    elif match.state == 'ban_2_b': 
        current_banned.append(selected_map)
        # 6 davor + 2 von B = 8 -> Wechsel zu Pick
        if len(current_banned) >= 8: match.state = 'pick_a'

    # --- PICK PHASE (2 Picks pro Team) ---
    elif match.state == 'pick_a': 
        current_picked.append(selected_map)
        if len(current_picked) >= 2: match.state = 'pick_b'

    elif match.state == 'pick_b': 
        current_picked.append(selected_map)
        # 2 von A + 2 von B = 4 -> Scoring
        if len(current_picked) >= 4: match.state = 'scoring_phase'
    
    match.banned_maps = json.dumps(current_banned)
    match.picked_maps = json.dumps(current_picked)
    return True, "Erfolgreich."

def handle_scoring_logic(match, form_data, user):
    try:
        # Standardmäßig 5 Slots lesen (Fallback), auch wenn nur 4 gespielt werden
        sa = [max(0, int(form_data.get(f'score_a_{i}',0))) for i in range(1, 6)]
        sb = [max(0, int(form_data.get(f'score_b_{i}',0))) for i in range(1, 6)]
    except: return False, "Ungültige Eingabe."
    
    lineup_list = form_data.getlist('lineup_member')
    
    # ADMIN / MOD: Direkt speichern
    if user.is_admin or user.is_mod:
        match.scores_a = json.dumps(sa); match.scores_b = json.dumps(sb)
        match.state = 'finished'
        return True, "Admin-Save erfolgreich."
        
    isa = (user.username == match.team_a); isb = (user.username == match.team_b)
    if not (isa or isb): return False, "Keine Berechtigung."
    
    # DRAFTS SPEICHERN
    if isa: 
        match.draft_a_scores = json.dumps({'a':sa, 'b':sb}); match.draft_a_lineup = json.dumps(lineup_list)
    elif isb: 
        match.draft_b_scores = json.dumps({'a':sa, 'b':sb}); match.draft_b_lineup = json.dumps(lineup_list)
    
    # VERGLEICHEN
    if match.draft_a_scores and match.draft_b_scores:
        if match.draft_a_scores == match.draft_b_scores:
            match.scores_a = json.dumps(sa); match.scores_b = json.dumps(sb)
            match.state = 'confirming' # In der Liga muss man noch das Lineup bestätigen
            return True, "Scores stimmen überein. Bitte Lineup bestätigen."
        else: 
            match.state = 'conflict'
            return False, "Konflikt: Ergebnisse stimmen nicht überein."
    else: 
        match.state = 'waiting_for_confirmation'
        return True, "Gespeichert. Warte auf Gegner."


@league_bp.route('/create_league', methods=['GET', 'POST'])
@login_required
def create_league():
    if not current_user.is_admin: return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        try:
            start_date_str = request.form.get('start_date')
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else get_current_time().date()
        except: start_date = get_current_time().date()

        participants_list = request.form.getlist('selected_users')
        l = League(name=request.form.get('league_name'), participants=json.dumps(participants_list), start_date=start_date)
        db.session.add(l); db.session.commit()

        teams = list(participants_list)
        if len(teams) % 2 != 0: teams.append(None) # Bye week placeholders
        
        num_weeks = len(teams) - 1
        
        # Round Robin Scheduling
        for week in range(num_weeks):
            for i in range(len(teams)//2):
                t1 = teams[i]
                t2 = teams[len(teams)-1-i]
                if t1 and t2:
                    # Match erstellen für diese Woche
                    m = LeagueMatch(
                        league_id=l.id, 
                        team_a=t1, 
                        team_b=t2, 
                        round_number=week+1, 
                        match_week=week+1
                    )
                    # Default-Datum berechnen: Startdatum + (Wochen-Offset) + Freitag (4 Tage)
                    # Startdatum ist idealerweise ein Montag.
                    # Bsp: Start 01.01 (Mo) -> Woche 1 Freitag = 05.01.
                    # Delta days = (week * 7) + 4
                    # Wir setzen vorerst KEIN scheduled_date, das passiert bei Deadline oder Einigung.
                    # Aber wir können es als Referenz nutzen, falls wir es brauchen.
                    db.session.add(m)
            
            # Rotate teams (ausgenommen 1. Element)
            teams.insert(1, teams.pop())
            
        db.session.commit()
        return redirect(url_for('main.dashboard'))
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


from datetime import timedelta

def get_default_date_for_week(start_date, match_week):
    """Berechnet den Default-Freitag 20:30 für die gegebene Woche."""
    if not start_date: return None
    # Woche 1 startet an start_date (Montag).
    # Freitag der Woche = start_date + (week-1)*7 + 4 Tage
    days_offset = (match_week - 1) * 7 + 4
    default_date = datetime.combine(start_date, datetime.min.time()) + timedelta(days=days_offset, hours=20, minutes=30)
    # Make default_date timezone aware (Berlin)
    tz = zoneinfo.ZoneInfo(Config.TIMEZONE)
    return default_date.replace(tzinfo=tz)

def check_deadline_exceeded(match):
    """Prüft, ob Mittwoch 23:59 der Spielwoche vorbei ist."""
    if not match.league.start_date: return False
    
    # Mittwoch der Woche = start_date + (week-1)*7 + 2 Tage
    days_offset = (match.match_week - 1) * 7 + 2
    deadline = datetime.combine(match.league.start_date, datetime.min.time()) + timedelta(days=days_offset, hours=23, minutes=59)
    # Make deadline timezone aware
    tz = zoneinfo.ZoneInfo(Config.TIMEZONE)
    deadline = deadline.replace(tzinfo=tz)
    
    return get_current_time() > deadline

@league_bp.route('/league_match/<int:match_id>', methods=['GET', 'POST'])
@login_required
def league_match_view(match_id):
    match = LeagueMatch.query.get_or_404(match_id)
    
    # Auto-Schedule Check (Fallback auf Freitag wenn Mittwoch vorbei)
    if not match.scheduled_date and check_deadline_exceeded(match):
        default_date = get_default_date_for_week(match.league.start_date, match.match_week)
        match.scheduled_date = default_date
        db.session.commit()
        flash(f"Deadline abgelaufen. Standardtermin gesetzt: {default_date.strftime('%d.%m.%Y %H:%M')}", "warning")

    # Bestimme aktives Team für Banns/Picks
    active = None
    if match.state.endswith('_a'): active = match.team_a
    elif match.state.endswith('_b'): active = match.team_b
    
    if request.method == 'POST':
        # --- SCHEDULING LOGIC ---
        if 'propose_date' in request.form:
            try:
                dt_str = request.form.get('proposal_datetime')
                proposed_dt = datetime.strptime(dt_str, '%Y-%m-%dT%H:%M')
                # Add timezone info
                tz = zoneinfo.ZoneInfo(Config.TIMEZONE)
                proposed_dt = proposed_dt.replace(tzinfo=tz)
                
                if current_user.username == match.team_a:
                     match.proposed_date_a = proposed_dt
                elif current_user.username == match.team_b:
                     match.proposed_date_b = proposed_dt
                
                # AUTO-MATCH CHECK
                if match.proposed_date_a and match.proposed_date_b and match.proposed_date_a == match.proposed_date_b:
                     match.scheduled_date = match.proposed_date_a
                     flash(f"Termine stimmen überein! Match festgelegt auf: {match.scheduled_date}", "success")
                else:
                     flash("Terminvorschlag gesendet!", "success")
                
                db.session.commit()
            except Exception as e: flash(f"Fehler beim Datum: {e}", "error")

        elif 'accept_proposal_a' in request.form:
            match.scheduled_date = match.proposed_date_a
            db.session.commit()
            flash(f"Termin bestätigt: {match.scheduled_date}", "success")
            
        elif 'accept_proposal_b' in request.form:
            match.scheduled_date = match.proposed_date_b
            db.session.commit()
            flash(f"Termin bestätigt: {match.scheduled_date}", "success")

        # --- READY LOGIC ---
        elif 'toggle_ready' in request.form:
            if not match.scheduled_date:
                flash("Kein Termin festgelegt.", "error")
            else:
                # 10 Minuten Regel
                # Ensure match.scheduled_date is aware. It should be if stored as such, 
                # but SQLite returns generic datetime usually. 
                # If we made it using get_current_time it has tzinfo? 
                # No, SQLite usually strips it. We might need to ensure both are naive or both are aware.
                # Simplest hack: Convert current time to naive if DB is naive, or match time to aware.
                
                # BUT, since we want Berlin time, we should assume DB dates are meant to be Berlin time.
                # So we attach Berlin TZ to them if missing.
                
                tz = zoneinfo.ZoneInfo(Config.TIMEZONE)
                sched = match.scheduled_date
                if sched.tzinfo is None:
                    sched = sched.replace(tzinfo=tz)
                    
                diff = sched - get_current_time()
                # Erlaubt: Zwischen 10 Min vor Start und ... (open end? oder bis Start?)
                # Sagen wir: Ab 15 Min vor Start darf man Ready drücken.
                limit = timedelta(minutes=15)
                
                if diff < limit: # Zeit bis Start ist weniger als 15 min (oder wir sind schon drüber)
                    if current_user.username == match.team_a: match.ready_a = not match.ready_a
                    elif current_user.username == match.team_b: match.ready_b = not match.ready_b
                    db.session.commit()
                else:
                    flash(f"Bereit-Melden erst ab 15 Minuten vor Match-Start möglich! (Start: {match.scheduled_date.strftime('%H:%M')})", "warning")

        # --- EXISTING LOGIC ---
        elif 'selected_map' in request.form and (current_user.is_admin or current_user.username == active):
            # CHECK READY STATUS
            if not (match.ready_a and match.ready_b):
                 flash("Beide Teams müssen BEREIT sein, um zu starten!", "error")
            else:
                success, msg = handle_pick_ban_logic(match, request.form.get('selected_map'))
                if success:
                    db.session.commit()
                else:
                    flash(msg, "error")
                
        elif 'submit_scores' in request.form:
            success, msg = handle_scoring_logic(match, request.form, current_user)
            db.session.commit()
            flash(msg, "success" if success else "error")
            
        elif 'confirm_lineup' in request.form:
            if current_user.username == match.team_a: match.confirmed_a=True
            elif current_user.username == match.team_b: match.confirmed_b=True
            
            if match.confirmed_a and match.confirmed_b:
                match.state = 'finished'
                match.lineup_a = match.draft_a_lineup
                match.lineup_b = match.draft_b_lineup
                flash("Match erfolgreich beendet!", "success")
            else:
                flash("Bestätigt. Warte auf Gegner...", "info")
            db.session.commit()
            
        elif 'lobby_code' in request.form:
            match.lobby_code = request.form.get('lobby_code'); db.session.commit()
            
        return redirect(url_for('league.league_match_view', match_id=match.id))
    
    # --- WICHTIG: Mitglieder laden für die Bann-Anzeige ---
    user_a = User.query.filter_by(username=match.team_a).first()
    members_a = user_a.team_members if user_a else []

    user_b = User.query.filter_by(username=match.team_b).first()
    members_b = user_b.team_members if user_b else []
    # ----------------------------------------------------

    return render_template('league_match.html', 
                           match=match, 
                           all_maps=Map.query.filter_by(is_archived=False).all(), 
                           banned=match.get_banned(), 
                           picked=match.get_picked(), 
                           active_team=active, 
                           now=get_current_time(),
                           members_a=members_a,  # Hier übergeben!
                           members_b=members_b   # Hier übergeben!
                           )

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