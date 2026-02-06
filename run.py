from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()

def create_initial_admin():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            hashed_pw = generate_password_hash("admin123", method='pbkdf2:sha256')
            db.session.add(User(username="admin", password=hashed_pw, is_admin=True))
            db.session.commit()
            print("Initialer Admin erstellt (PW: admin123).")

if __name__ == '__main__':
    create_initial_admin()
    app.run(debug=True, host='0.0.0.0')