import firebase_admin
from firebase_admin import credentials, messaging
from flask import current_app
import os

_firebase_app = None

def init_firebase(app):
    """
    Initializes the Firebase Admin SDK.
    Requires FIREBASE_CREDENTIALS in app config pointing to the serviceAccountKey.json.
    """
    global _firebase_app
    cred_path = app.config.get('FIREBASE_CREDENTIALS')
    
    if not cred_path or not os.path.exists(cred_path):
        print(f"⚠️ Firebase Credentials not found at: {cred_path}")
        return

    try:
        cred = credentials.Certificate(cred_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        print("✅ Firebase Admin SDK initialized.")
    except Exception as e:
        print(f"❌ Failed to initialize Firebase: {e}")

def send_push_notification(token, title, body, data=None):
    """
    Sends a push notification to a specific device token.
    """
    if not _firebase_app:
        print("⚠️ Firebase not initialized. Skipping notification.")
        return False

    if not token:
        return False

    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data,
            token=token,
        )
        response = messaging.send(message)
        print(f"🚀 Notification sent: {response}")
        return True
    except Exception as e:
        print(f"❌ Error sending notification: {e}")
        return False
