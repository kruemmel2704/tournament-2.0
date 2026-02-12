from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import Match, CupMatch, LeagueMatch, ChatMessage, CupChatMessage, LeagueChatMessage
from app.extensions import db
from app.firebase_utils import send_push_notification

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/save_fcm_token', methods=['POST'])
@login_required
def save_fcm_token():
    token = request.json.get('token')
    if token:
        current_user.fcm_token = token
        db.session.commit()
        return jsonify({'status': 'ok', 'msg': 'Token saved'})
    return jsonify({'status': 'error', 'msg': 'No token provided'}), 400

@api_bp.route('/test_push', methods=['POST'])
@login_required
def test_push():
    if not current_user.is_admin:
        return jsonify({'status': 'error', 'msg': 'Admin only'}), 403
    
    target_username = request.json.get('username')
    user = User.query.filter_by(username=target_username).first() if target_username else current_user
    
    if user and user.fcm_token:
        success = send_push_notification(user.fcm_token, "Test Notification", "This is a test from Tournament 2.0")
        return jsonify({'status': 'ok', 'sent': success})
    return jsonify({'status': 'error', 'msg': 'User has no token'}), 404

def handle_chat(model, match_id, id_field):
    if request.method == 'POST' and request.json.get('message'):
        msg = model(username=current_user.username, message=request.json['message'], is_admin=current_user.is_admin, is_mod=current_user.is_mod)
        setattr(msg, id_field, match_id)
        db.session.add(msg); db.session.commit()
        return jsonify({'status':'ok'})
    msgs = model.query.filter_by(**{id_field: match_id}).order_by(model.timestamp).all()
    return jsonify([{'user':m.username, 'text':m.message, 'time':m.timestamp.strftime('%H:%M'), 'is_admin':m.is_admin, 'is_mod':m.is_mod, 'is_me':m.username==current_user.username} for m in msgs])

@api_bp.route('/match/<int:match_id>/chat', methods=['GET', 'POST'])
@login_required
def match_chat(match_id): return handle_chat(ChatMessage, match_id, 'match_id')

@api_bp.route('/cup_match/<int:match_id>/chat', methods=['GET', 'POST'])
@login_required
def cup_chat(match_id): return handle_chat(CupChatMessage, match_id, 'cup_match_id')

@api_bp.route('/league_match/<int:match_id>/chat', methods=['GET', 'POST'])
@login_required
def league_chat(match_id): return handle_chat(LeagueChatMessage, match_id, 'league_match_id')

@api_bp.route('/match/<int:match_id>/lobby_code', methods=['GET', 'POST'])
@login_required
def match_lobby(match_id):
    m = Match.query.get_or_404(match_id)
    if request.method == 'GET': return jsonify({'lobby_code': m.lobby_code or ''})
    if current_user.is_admin or current_user.is_mod or current_user.username in [m.team_a, m.team_b]:
        m.lobby_code = request.json.get('lobby_code', '').strip(); db.session.commit(); return jsonify({'status': 'ok'})
    return jsonify({'status': 'error'}), 403

@api_bp.route('/league_match/<int:match_id>/lobby_code', methods=['GET'])
@login_required
def league_lobby(match_id):
    return jsonify({'lobby_code': LeagueMatch.query.get_or_404(match_id).lobby_code or ''})

@api_bp.route('/match/<int:match_id>/state')
@login_required
def match_state(match_id):
    m = Match.query.get_or_404(match_id)
    active = m.team_a if m.state.endswith('_a') else (m.team_b if m.state.endswith('_b') else None)
    return jsonify({'state':m.state, 'active_team':active, 'banned':m.get_banned(), 'picked':m.get_picked(), 'lobby_code':m.lobby_code})

@api_bp.route('/cup_match/<int:match_id>/state')
@login_required
def cup_state(match_id):
    m = CupMatch.query.get_or_404(match_id)
    return jsonify({'state':m.state, 'current_picker':m.current_picker, 'picked':m.get_picked(), 'lobby_code':m.lobby_code, 'ready_a':m.ready_a, 'ready_b':m.ready_b})

@api_bp.route('/league_match/<int:match_id>/state')
@login_required
def league_state(match_id):
    m = LeagueMatch.query.get_or_404(match_id)
    active = m.team_a if m.state.endswith('_a') else (m.team_b if m.state.endswith('_b') else None)
    return jsonify({'state':m.state, 'active_team':active, 'banned':m.get_banned(), 'picked':m.get_picked(), 'lobby_code':m.lobby_code, 'confirmed_a':m.confirmed_a, 'confirmed_b':m.confirmed_b})