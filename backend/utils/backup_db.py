"""
Safe Database Backup Utility for MetrCheck AI.
Provides manual and automated backup mechanisms before database migrations.
"""

import os
import sys
import shutil
import datetime

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config import settings, PROD_DATABASE_PATH


def create_db_backup(db_path: str = None) -> str:
    """
    Creates a timestamped copy of the database.
    Example: backend/metrc_check.db.backup_20260907_201500
    """
    target_db = db_path or settings.DATABASE_PATH
    if not os.path.exists(target_db):
        print(f"[BACKUP] Database file not found: {target_db}")
        return ""

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{target_db}.backup_{timestamp}"
    shutil.copy2(target_db, backup_file)
    print(f"[BACKUP] Successfully created database backup: {backup_file}")
    return backup_file


if __name__ == "__main__":
    create_db_backup()
