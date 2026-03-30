"""
MINECRAFT BACKUP SCRIPT - VERSION 2.0 (OAuth 2.0)
------------------------------------------------
USAGE INSTRUCTIONS:
1. Generate 'token.json' on your laptop using 'client_secrets.json'.
2. Upload 'token.json' to your VPS in the same directory as docker-compose.yml.
3. Ensure 'GDRIVE_FOLDER_ID' is set in your docker-compose environment.
4. Mounts required:
   - /data/world (ro), /data/mods (ro), /backups (rw), /app/token.json (rw)
"""

import os
import shutil
import tarfile
import time
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- CONFIGURATION ---
WORLD_DIR = Path("/data/world")
MODS_DIR = Path("/data/mods")
BACKUP_BASE = Path("/backups")
PERIODIC_DIR = BACKUP_BASE / "periodic"
DAILY_DIR = BACKUP_BASE / "daily"
MONTHLY_DIR = BACKUP_BASE / "monthly"
TOKEN_FILE = Path("/app/token.json")
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")

SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Ensure local directories exist
for d in [PERIODIC_DIR, DAILY_DIR, MONTHLY_DIR]:
    d.mkdir(parents=True, exist_ok=True)

def get_gdrive_service():
    """Authenticates using token.json and handles token refresh."""
    creds = None
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print(f"[{datetime.now()}] Refreshing Google Drive token...")
            creds.refresh(Request())
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
        else:
            print(f"[{datetime.now()}] ERROR: No valid token.json found!")
            return None

    return build('drive', 'v3', credentials=creds)

def upload_to_gdrive(file_path):
    """Uploads a single file to the specified Google Drive folder."""
    service = get_gdrive_service()
    if not service or not GDRIVE_FOLDER_ID:
        return

    file_metadata = {'name': file_path.name, 'parents': [GDRIVE_FOLDER_ID]}
    media = MediaFileUpload(str(file_path), mimetype='application/gzip')
    
    try:
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"[{datetime.now()}] Cloud upload successful: {file_path.name}")
    except Exception as e:
        print(f"[{datetime.now()}] Cloud upload failed: {e}")

def cleanup_gdrive():
    """Keeps only the last 14 backups on Google Drive."""
    service = get_gdrive_service()
    if not service or not GDRIVE_FOLDER_ID:
        return

    try:
        query = f"'{GDRIVE_FOLDER_ID}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id, name, createdTime)").execute()
        files = results.get('files', [])
        files.sort(key=lambda x: x['createdTime'])
        
        if len(files) > 14:
            for i in range(len(files) - 14):
                service.files().delete(fileId=files[i]['id']).execute()
                print(f"[{datetime.now()}] Deleted from Cloud: {files[i]['name']}")
    except Exception as e:
        print(f"[{datetime.now()}] Cloud cleanup error: {e}")

def create_backup():
    """Creates a local tar.gz archive of world and mods."""
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M")
    backup_name = f"mc_full_backup_{timestamp}.tar.gz"
    periodic_path = PERIODIC_DIR / backup_name
    
    print(f"[{datetime.now()}] Starting local backup: {backup_name}")
    with tarfile.open(periodic_path, "w:gz") as tar:
        if WORLD_DIR.exists():
            tar.add(WORLD_DIR, arcname="world")
        if MODS_DIR.exists():
            tar.add(MODS_DIR, arcname="mods")
    return periodic_path

def rotate_and_copy(current_backup):
    """Handles daily and monthly logic + triggers cloud upload."""
    now = datetime.now()
    
    # Daily logic
    daily_path = DAILY_DIR / f"daily_{now.strftime('%Y%m%d')}.tar.gz"
    if not daily_path.exists():
        shutil.copy2(current_backup, daily_path)
        upload_to_gdrive(daily_path)
        cleanup_gdrive()

    # Monthly logic
    monthly_path = MONTHLY_DIR / f"monthly_{now.strftime('%Y%m')}.tar.gz"
    if not monthly_path.exists():
        shutil.copy2(current_backup, monthly_path)

def cleanup_local():
    """Local retention: 24h for periodic, 14d for daily."""
    now = datetime.now()
    for f in PERIODIC_DIR.glob("*.tar.gz"):
        if f.stat().st_mtime < (now - timedelta(hours=24)).timestamp():
            f.unlink()
    for f in DAILY_DIR.glob("*.tar.gz"):
        if f.stat().st_mtime < (now - timedelta(days=14)).timestamp():
            f.unlink()

if __name__ == "__main__":
    print("Backup Sidecar is active. Frequency: 30 minutes.")
    while True:
        try:
            new_backup = create_backup()
            rotate_and_copy(new_backup)
            cleanup_local()
        except Exception as e:
            print(f"Critical Error: {e}")
        time.sleep(1800)
