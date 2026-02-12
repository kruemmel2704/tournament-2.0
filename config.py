import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = 'dein-geheimer-schluessel-bitte-aendern'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///tournament.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    basedir = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = 'app/static/map_images'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    FIREBASE_CREDENTIALS = os.path.join(os.getcwd(), 'instance', 'serviceAccountKey.json')
    LOGO_UPLOAD_FOLDER = 'app/static/logos'
    TIMEZONE = 'Europe/Berlin'
    
    # Frontend Config (Load from Environment or defaults)
    FIREBASE_API_KEY = os.environ.get('FIREBASE_API_KEY', 'YOUR_API_KEY')
    FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'YOUR_PROJECT_ID')
    FIREBASE_MESSAGING_SENDER_ID = os.environ.get('FIREBASE_MESSAGING_SENDER_ID', 'YOUR_SENDER_ID')
    FIREBASE_APP_ID = os.environ.get('FIREBASE_APP_ID', 'YOUR_APP_ID')
    FIREBASE_VAPID_KEY = os.environ.get('FIREBASE_VAPID_KEY', 'YOUR_VAPID_KEY')