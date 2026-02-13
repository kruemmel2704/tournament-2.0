from .extensions import db
from flask_login import UserMixin
from .utils import calculate_map_wins, safe_json_load, get_current_time, strip_clan_tag
from datetime import datetime
import json

class Clan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    logo_file = db.Column(db.String(120), nullable=True) # Custom Logo
    # Beziehung zu Usern
    members = db.relationship('User', backref='clan', lazy=True)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    logo_file = db.Column(db.String(120), nullable=True) # Custom Team Logo
    password = db.Column(db.String(150), nullable=True)
    token = db.Column(db.String(5), nullable=True)
    fcm_token = db.Column(db.String(255), nullable=True) # Firebase Cloud Messaging Token
    
    # Rechte
    is_admin = db.Column(db.Boolean, default=False)
    is_mod = db.Column(db.Boolean, default=False)
    
    # Clan Zugehörigkeit
    clan_id = db.Column(db.Integer, db.ForeignKey('clan.id'), nullable=True)
    is_clan_admin = db.Column(db.Boolean, default=False)
    
    # Roster / Team Member Management (Legacy Member entfernt)
    team_members = db.relationship('TeamMember', backref='owner', lazy=True)

    @property
    def display_name(self):
        return strip_clan_tag(self.username)

class TeamMember(db.Model):
    """Repräsentiert einen Spieler/Account in einem Roster (z.B. für verschiedene Games)"""
    id = db.Column(db.Integer, primary_key=True)
    gamertag = db.Column(db.String(150), nullable=False)
    activision_id = db.Column(db.String(150), nullable=False)
    platform = db.Column(db.String(50), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    banned_until = db.Column(db.DateTime, nullable=True) # Wenn Datum in Zukunft = Gebannt
    ban_reason = db.Column(db.String(200), nullable=True)

    @property
    def is_banned(self):
        # Prüft, ob ein Bann aktiv ist
        if self.banned_until and self.banned_until > get_current_time():
            return True
        return False

# Class Member wurde entfernt (da Legacy/veraltet)

class Map(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    image_file = db.Column(db.String(120), nullable=False, default='default.jpg')
    is_archived = db.Column(db.Boolean, default=False)

# --- MATCH MODELS ---

class Tournament(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    is_archived = db.Column(db.Boolean, default=False)
    matches = db.relationship('Match', backref='tournament', lazy=True, cascade="all, delete-orphan")

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'))
    
    # Teams
    team_a = db.Column(db.String(100), nullable=False, default="TBD")
    team_b = db.Column(db.String(100), nullable=False, default="TBD")
    
    # Status & Meta
    state = db.Column(db.String(50), default='waiting') 
    lobby_code = db.Column(db.String(50), nullable=True)
    round_number = db.Column(db.Integer, default=1)
    match_index = db.Column(db.Integer, default=0)
    next_match_id = db.Column(db.Integer, nullable=True)
    
    # Daten
    banned_maps = db.Column(db.Text, default='[]') 
    picked_maps = db.Column(db.Text, default='[]')
    scores_a = db.Column(db.Text, default='[]')
    scores_b = db.Column(db.Text, default='[]')
    
    # NEU: Beweis-Screenshots für Ergebnisse
    evidence_a = db.Column(db.String(150), nullable=True) # Dateipfad Bild Team A
    evidence_b = db.Column(db.String(150), nullable=True) # Dateipfad Bild Team B
    
    chat_messages = db.relationship('ChatMessage', backref='match', lazy=True, cascade="all, delete-orphan")

    def get_banned(self): return safe_json_load(self.banned_maps)
    def get_picked(self): return safe_json_load(self.picked_maps)
    def get_scores_a(self): return safe_json_load(self.scores_a)
    def get_scores_b(self): return safe_json_load(self.scores_b)
    def get_map_wins(self): return calculate_map_wins(self.get_scores_a(), self.get_scores_b())
    
    @property
    def team_a_clan(self):
        u = User.query.filter_by(username=self.team_a).first()
        return u.clan.name if u and u.clan else None
    @property
    def team_b_clan(self):
        u = User.query.filter_by(username=self.team_b).first()
        return u.clan.name if u and u.clan else None

    @property
    def team_a_logo(self):
        u = User.query.filter_by(username=self.team_a).first()
        if u:
            if u.logo_file: return u.logo_file
            if u.clan and u.clan.logo_file: return u.clan.logo_file
        return None

    @property
    def team_b_logo(self):
        u = User.query.filter_by(username=self.team_b).first()
        if u:
            if u.logo_file: return u.logo_file
            if u.clan and u.clan.logo_file: return u.clan.logo_file
        return None

class Cup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    is_archived = db.Column(db.Boolean, default=False)
    participants = db.Column(db.Text, default='[]')
    matches = db.relationship('CupMatch', backref='cup', lazy=True, cascade="all, delete-orphan")
    rosters = db.Column(db.Text, default='{}') 
    
    matches = db.relationship('CupMatch', backref='cup', lazy=True, cascade="all, delete-orphan")
    
    def get_participants(self): return safe_json_load(self.participants)
    def get_rosters(self): return safe_json_load(self.rosters)

class CupMatch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cup_id = db.Column(db.Integer, db.ForeignKey('cup.id'), nullable=False)
    team_a = db.Column(db.String(100), nullable=False)
    team_b = db.Column(db.String(100), nullable=False)
    round_number = db.Column(db.Integer, default=1)
    state = db.Column(db.String(50), default='waiting_for_ready')
    lobby_code = db.Column(db.String(50), nullable=True)
    current_picker = db.Column(db.String(100), nullable=True)
    
    scores_a = db.Column(db.Text, default='[]')
    scores_b = db.Column(db.Text, default='[]')
    picked_maps = db.Column(db.Text, default='[]')
    
    # NEU: Lineups & Bestätigung
    lineup_a = db.Column(db.Text, default='[]') # JSON Liste der Gamertags/IDs
    lineup_b = db.Column(db.Text, default='[]')
    confirmed_a = db.Column(db.Boolean, default=False) # Admin hat Team A bestätigt
    confirmed_b = db.Column(db.Boolean, default=False) # Admin hat Team B bestätigt

    def get_lineup_a(self): return safe_json_load(self.lineup_a)
    def get_lineup_b(self): return safe_json_load(self.lineup_b)

    # NEU: Beweis-Screenshots
    evidence_a = db.Column(db.String(150), nullable=True)
    evidence_b = db.Column(db.String(150), nullable=True)
    
    chat_messages = db.relationship('CupChatMessage', backref='cup_match', lazy=True, cascade="all, delete-orphan")

    def get_picked(self): return safe_json_load(self.picked_maps)
    def get_scores_a(self): return safe_json_load(self.scores_a)
    def get_scores_b(self): return safe_json_load(self.scores_b)
    def get_map_wins(self): return calculate_map_wins(self.get_scores_a(), self.get_scores_b())

    @property
    def team_a_clan(self):
        u = User.query.filter_by(username=self.team_a).first()
        return u.clan.name if u and u.clan else None
    @property
    def team_b_clan(self):
        u = User.query.filter_by(username=self.team_b).first()
        return u.clan.name if u and u.clan else None

    @property
    def team_a_logo(self):
        u = User.query.filter_by(username=self.team_a).first()
        if u:
            if u.logo_file: return u.logo_file
            if u.clan and u.clan.logo_file: return u.clan.logo_file
        return None

    @property
    def team_b_logo(self):
        u = User.query.filter_by(username=self.team_b).first()
        if u:
            if u.logo_file: return u.logo_file
            if u.clan and u.clan.logo_file: return u.clan.logo_file
        return None

class League(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    is_archived = db.Column(db.Boolean, default=False)
    participants = db.Column(db.Text, default='[]')
    start_date = db.Column(db.Date, nullable=True) # Start der Liga (Montag der ersten Woche)
    matches = db.relationship('LeagueMatch', backref='league', lazy=True, cascade="all, delete-orphan")
    def get_participants(self): return safe_json_load(self.participants)

class LeagueMatch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    league_id = db.Column(db.Integer, db.ForeignKey('league.id'), nullable=False)
    
    team_a = db.Column(db.String(100), nullable=False)
    team_b = db.Column(db.String(100), nullable=False)
    round_number = db.Column(db.Integer, default=1)
    match_week = db.Column(db.Integer, default=1) # Spielwoche (1, 2, 3...)
    scheduled_date = db.Column(db.DateTime, nullable=True) # Finaler Termin
    proposed_date_a = db.Column(db.DateTime, nullable=True) # Vorschlag Team A
    proposed_date_b = db.Column(db.DateTime, nullable=True) # Vorschlag Team B
    
    state = db.Column(db.String(50), default='ban_1_a') 
    lobby_code = db.Column(db.String(50), nullable=True)
    
    banned_maps = db.Column(db.Text, default='[]') 
    picked_maps = db.Column(db.Text, default='[]')
    scores_a = db.Column(db.Text, default='[]')
    scores_b = db.Column(db.Text, default='[]')
    
    lineup_a = db.Column(db.Text, default='[]') 
    lineup_b = db.Column(db.Text, default='[]')
    confirmed_a = db.Column(db.Boolean, default=False)
    confirmed_b = db.Column(db.Boolean, default=False)
    
    # Drafts (Temporary storage for confirmation)
    draft_a_scores = db.Column(db.Text, nullable=True)
    draft_b_scores = db.Column(db.Text, nullable=True)
    draft_a_lineup = db.Column(db.Text, nullable=True)
    draft_b_lineup = db.Column(db.Text, nullable=True)

    # NEU: Ready Check Flags
    ready_a = db.Column(db.Boolean, default=False)
    ready_b = db.Column(db.Boolean, default=False)
    
    # NEU: Beweis-Screenshots
    evidence_a = db.Column(db.String(150), nullable=True)
    evidence_b = db.Column(db.String(150), nullable=True)

    chat_messages = db.relationship('LeagueChatMessage', backref='league_match', lazy=True, cascade="all, delete-orphan")

    def get_banned(self): return safe_json_load(self.banned_maps)
    def get_picked(self): return safe_json_load(self.picked_maps)
    def get_scores_a(self): return safe_json_load(self.scores_a)
    def get_scores_b(self): return safe_json_load(self.scores_b)
    def get_map_wins(self): return calculate_map_wins(self.get_scores_a(), self.get_scores_b())
    def get_draft_lineup_a(self): return safe_json_load(self.draft_a_lineup)
    def get_draft_lineup_b(self): return safe_json_load(self.draft_b_lineup)
    def get_draft_scores_a(self): return safe_json_load(self.draft_a_scores)
    def get_draft_scores_b(self): return safe_json_load(self.draft_b_scores)

    @property
    def team_a_clan(self):
        u = User.query.filter_by(username=self.team_a).first()
        return u.clan.name if u and u.clan else None
    @property
    def team_b_clan(self):
        u = User.query.filter_by(username=self.team_b).first()
        return u.clan.name if u and u.clan else None

    @property
    def team_a_logo(self):
        u = User.query.filter_by(username=self.team_a).first()
        if u:
            if u.logo_file: return u.logo_file
            if u.clan and u.clan.logo_file: return u.clan.logo_file
        return None

    @property
    def team_b_logo(self):
        u = User.query.filter_by(username=self.team_b).first()
        if u:
            if u.logo_file: return u.logo_file
            if u.clan and u.clan.logo_file: return u.clan.logo_file
        return None

# --- CHAT MODELS (Unverändert) ---
class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=get_current_time)
    is_admin = db.Column(db.Boolean, default=False)
    is_mod = db.Column(db.Boolean, default=False)

class CupChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cup_match_id = db.Column(db.Integer, db.ForeignKey('cup_match.id'), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=get_current_time)
    is_admin = db.Column(db.Boolean, default=False)
    is_mod = db.Column(db.Boolean, default=False)

class LeagueChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    league_match_id = db.Column(db.Integer, db.ForeignKey('league_match.id'), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=get_current_time)
    is_admin = db.Column(db.Boolean, default=False)
    is_mod = db.Column(db.Boolean, default=False)