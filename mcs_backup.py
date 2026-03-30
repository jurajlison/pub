import os
import shutil
import tarfile
import time
from datetime import datetime, timedelta
from pathlib import Path

# Cesty vo vnútri kontajnera
SOURCE_DIR = Path("/data/world")
BACKUP_BASE = Path("/backups")
PERIODIC_DIR = BACKUP_BASE / "periodic"
DAILY_DIR = BACKUP_BASE / "daily"
MONTHLY_DIR = BACKUP_BASE / "monthly"

# Vytvorenie adresárov ak neexistujú
for d in [PERIODIC_DIR, DAILY_DIR, MONTHLY_DIR]:
    d.mkdir(parents=True, exist_ok=True)

def create_backup():
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M")
    backup_name = f"world_backup_{timestamp}.tar.gz"
    periodic_path = PERIODIC_DIR / backup_name
    
    print(f"[{datetime.now()}] Vytváram zálohu: {backup_name}")
    with tarfile.open(periodic_path, "w:gz") as tar:
        tar.add(SOURCE_DIR, arcname=SOURCE_DIR.name)
    return periodic_path

def rotate_and_copy(current_backup):
    now = datetime.now()
    # 1. Denná záloha
    daily_path = DAILY_DIR / f"daily_{now.strftime('%Y%m%d')}.tar.gz"
    if not daily_path.exists():
        shutil.copy2(current_backup, daily_path)

    # 2. Mesačná záloha
    monthly_path = MONTHLY_DIR / f"monthly_{now.strftime('%Y%m')}.tar.gz"
    if not monthly_path.exists():
        shutil.copy2(current_backup, monthly_path)

def cleanup():
    now = datetime.now()
    # Zmaž periodické > 24h
    for f in PERIODIC_DIR.glob("*.tar.gz"):
        if f.stat().st_mtime < (now - timedelta(hours=24)).timestamp():
            f.unlink()
    # Zmaž denné > 14 dní
    for f in DAILY_DIR.glob("*.tar.gz"):
        if f.stat().st_mtime < (now - timedelta(days=14)).timestamp():
            f.unlink()

if __name__ == "__main__":
    print("Zálohovací kontajner spustený...")
    while True:
        try:
            # Voliteľné: Tu by mohol byť príkaz na rcon-cli save-all
            new_backup = create_backup()
            rotate_and_copy(new_backup)
            cleanup()
        except Exception as e:
            print(f"Chyba pri zálohovaní: {e}")
        
        # Čakaj 30 minút
        time.sleep(1800)
