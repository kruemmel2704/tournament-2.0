import os

class Config:
    SECRET_KEY = 'dein-geheimer-schluessel-bitte-aendern'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///tournament.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'app/static/map_images'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024