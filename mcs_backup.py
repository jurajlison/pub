"""
MINECRAFT BACKUP SCRIPT - USAGE INSTRUCTIONS:
1. This script is designed to run as a sidecar Docker container.
2. Ensure you mount the following volumes in your docker-compose.yml:
   - Minecraft World:  ./world -> /data/world:ro
   - Minecraft Mods:   ./mods  -> /data/mods:ro
   - Backup Storage:   ./backups -> /backups
3. The script creates a full backup (World + Mods) every 30 minutes.
4. Retention Policy:
   - Periodic: Kept for 24 hours.
   - Daily: Kept for 14 days.
   - Monthly: Kept indefinitely.
"""

import os
import shutil
import tarfile
import time
from datetime import datetime, timedelta
from pathlib import Path

# Paths inside the container
WORLD_DIR = Path("/data/world")
MODS_DIR = Path("/data/mods")
BACKUP_BASE = Path("/backups")
PERIODIC_DIR = BACKUP_BASE / "periodic"
DAILY_DIR = BACKUP_BASE / "daily"
MONTHLY_DIR = BACKUP_BASE / "monthly"

# Create directories if they don't exist
for d in [PERIODIC_DIR, DAILY_DIR, MONTHLY_DIR]:
    d.mkdir(parents=True, exist_ok=True)

def create_backup():
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M")
    backup_name = f"mc_full_backup_{timestamp}.tar.gz"
    periodic_path = PERIODIC_DIR / backup_name
    
    print(f"[{datetime.now()}] Creating backup: {backup_name}")
    with tarfile.open(periodic_path, "w:gz") as tar:
        # Add world folder if it exists
        if WORLD_DIR.exists():
            tar.add(WORLD_DIR, arcname="world")
        # Add mods folder if it exists
        if MODS_DIR.exists():
            tar.add(MODS_DIR, arcname="mods")
            
    return periodic_path

def rotate_and_copy(current_backup):
    now = datetime.now()
    # 1. Daily backup (copy if first one today)
    daily_path = DAILY_DIR / f"daily_{now.strftime('%Y%m%d')}.tar.gz"
    if not daily_path.exists():
        shutil.copy2(current_backup, daily_path)

    # 2. Monthly backup (copy if first one this month)
    monthly_path = MONTHLY_DIR / f"monthly_{now.strftime('%Y%m')}.tar.gz"
    if not monthly_path.exists():
        shutil.copy2(current_backup, monthly_path)

def cleanup():
    now = datetime.now()
    # Delete periodic backups older than 24h
    for f in PERIODIC_DIR.glob("*.tar.gz"):
        if f.stat().st_mtime < (now - timedelta(hours=24)).timestamp():
            f.unlink()
            
    # Delete daily backups older than 14 days
    for f in DAILY_DIR.glob("*.tar.gz"):
        if f.stat().st_mtime < (now - timedelta(days=14)).timestamp():
            f.unlink()

if __name__ == "__main__":
    print("Backup container started...")
    while True:
        try:
            # Note: You can add rcon-cli save-all here if needed
            new_backup = create_backup()
            rotate_and_copy(new_backup)
            cleanup()
        except Exception as e:
            print(f"Backup error: {e}")
        
        # Wait 30 minutes (1800 seconds)
        time.sleep(1800)
