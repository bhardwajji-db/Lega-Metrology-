"""
Test Isolation & Safety Utilities for MetrCheck AI.
Guarantees 100% isolation between automated tests and the production/development database.
"""

import os
import sys
import shutil
import tempfile
import asyncio
import datetime
from contextlib import contextmanager

from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from database.db import init_db


def safe_db_backup(db_path: str = PROD_DATABASE_PATH) -> str:
    """
    Creates a timestamped backup of the database file if it exists.
    Returns the backup filepath.
    """
    if not os.path.exists(db_path):
        return ""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    return backup_path


@contextmanager
def isolated_test_env():
    """
    Context manager that creates an isolated temporary test directory containing:
    1. A fresh SQLite database (test_metrc_check.db)
    2. A fresh uploads directory (test_uploads)
    
    Guarantees that tests NEVER interact with backend/metrc_check.db or backend/uploads/.
    Automatically creates the schema and cleans up on exit.
    """
    temp_dir = tempfile.mkdtemp(prefix="metrcheck_test_")
    test_db_path = os.path.abspath(os.path.join(temp_dir, "test_metrc_check.db"))
    test_upload_dir = os.path.abspath(os.path.join(temp_dir, "test_uploads"))
    os.makedirs(test_upload_dir, exist_ok=True)

    # Save original settings
    orig_db_path = settings.DATABASE_PATH
    orig_upload_dir = settings.UPLOAD_DIR
    orig_test_mode = settings.TEST_MODE
    orig_env_db = os.environ.get("DATABASE_PATH")
    orig_env_upload = os.environ.get("UPLOAD_DIR")
    orig_env_test_mode = os.environ.get("TEST_MODE")

    try:
        # Override environment and settings
        os.environ["DATABASE_PATH"] = test_db_path
        os.environ["UPLOAD_DIR"] = test_upload_dir
        os.environ["TEST_MODE"] = "1"
        settings.DATABASE_PATH = test_db_path
        settings.UPLOAD_DIR = test_upload_dir
        settings.TEST_MODE = True

        # Verify strict isolation
        assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "CRITICAL: Test DB matches Production DB!"
        assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "CRITICAL: Test Uploads matches Production Uploads!"

        # Initialize schema in isolated test DB
        asyncio.run(init_db())

        yield {
            "temp_dir": temp_dir,
            "test_db_path": test_db_path,
            "test_upload_dir": test_upload_dir,
            "prod_db_path": PROD_DATABASE_PATH,
            "prod_upload_dir": PROD_UPLOAD_DIR
        }
    finally:
        # Restore original settings
        settings.DATABASE_PATH = orig_db_path
        settings.UPLOAD_DIR = orig_upload_dir
        settings.TEST_MODE = orig_test_mode

        if orig_env_db is not None:
            os.environ["DATABASE_PATH"] = orig_env_db
        else:
            os.environ.pop("DATABASE_PATH", None)

        if orig_env_upload is not None:
            os.environ["UPLOAD_DIR"] = orig_env_upload
        else:
            os.environ.pop("UPLOAD_DIR", None)

        if orig_env_test_mode is not None:
            os.environ["TEST_MODE"] = orig_env_test_mode
        else:
            os.environ.pop("TEST_MODE", None)

        # Remove temporary directory and files
        shutil.rmtree(temp_dir, ignore_errors=True)
