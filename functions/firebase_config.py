import json
import os
import firebase_admin
from firebase_admin import credentials, firestore, storage

_initialized = False
db = None
bucket = None


def initialize_firebase():
    global _initialized, db, bucket
    if _initialized:
        return db, bucket

    # Support both file path and inline JSON string
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
    cred_json = os.getenv("FIREBASE_CREDENTIALS", "")

    if cred_path and os.path.isfile(cred_path):
        # Load from file (like new FileInputStream("path/to/serviceAccountKey.json"))
        cred = credentials.Certificate(cred_path)
    elif cred_json:
        try:
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
        except json.JSONDecodeError:
            cred = credentials.Certificate(cred_json)
    else:
        # Fallback: Application Default Credentials (Cloud Functions)
        cred = credentials.ApplicationDefault()

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {
            "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", "quron-yodlaymiz.firebasestorage.app"),
        })

    db = firestore.client()
    try:
        bucket = storage.bucket()
    except Exception:
        bucket = None

    _initialized = True
    return db, bucket


# Initialize at module load
try:
    db, bucket = initialize_firebase()
    print("[Firebase] Connected to Firestore: quron-yodlaymiz")
except Exception as e:
    print(f"[Firebase] Init skipped: {e}")
    db = None
    bucket = None
