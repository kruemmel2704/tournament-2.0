import os
from flask import Flask
from .extensions import db, login_manager
from .models import User
from .firebase_utils import init_firebase

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    # Ordner erstellen
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Init Extensions
    db.init_app(app)
    login_manager.init_app(app)
    init_firebase(app)
    
    from .utils import strip_clan_tag
    app.jinja_env.filters['strip_clan_tag'] = strip_clan_tag

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprints registrieren
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.admin import admin_bp
    from app.routes.tournament import tournament_bp
    from app.routes.cup import cup_bp
    from app.routes.league import league_bp
    from app.routes.api import api_bp
    from app.routes.tickets import tickets

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(tournament_bp)
    app.register_blueprint(cup_bp)
    app.register_blueprint(league_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(tickets)

    return app