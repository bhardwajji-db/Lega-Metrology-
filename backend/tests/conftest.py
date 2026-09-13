import os
import sys
import tempfile
import shutil
import pytest
import asyncio

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from database.db import init_db


@pytest.fixture(autouse=True, scope="session")
def session_test_isolation():
    """Global session-level safety guarantee for all pytest tests.
    Forces all tests to execute in an isolated temporary environment.
    """
    temp_dir = tempfile.mkdtemp(prefix="metrcheck_pytest_session_")
    test_db_path = os.path.abspath(os.path.join(temp_dir, "test_metrc_check.db"))
    test_upload_dir = os.path.abspath(os.path.join(temp_dir, "test_uploads"))
    os.makedirs(test_upload_dir, exist_ok=True)

    orig_db = settings.DATABASE_PATH
    orig_upload = settings.UPLOAD_DIR
    orig_test_mode = settings.TEST_MODE
    orig_env_db = os.environ.get("DATABASE_PATH")
    orig_env_upload = os.environ.get("UPLOAD_DIR")
    orig_env_test_mode = os.environ.get("TEST_MODE")

    os.environ["TEST_MODE"] = "1"
    os.environ["DATABASE_PATH"] = test_db_path
    os.environ["UPLOAD_DIR"] = test_upload_dir

    settings.TEST_MODE = True
    settings.DATABASE_PATH = test_db_path
    settings.UPLOAD_DIR = test_upload_dir

    # Initialize isolated database schema
    asyncio.run(init_db())

    # Bootstrap isolated test admin fixture for testing environment
    from scripts.bootstrap_admin import bootstrap_admin
    asyncio.run(bootstrap_admin(username="admin", password="admin123", email="admin@test.gov.in", overwrite=True))

    yield {
        "temp_dir": temp_dir,
        "test_db_path": test_db_path,
        "test_upload_dir": test_upload_dir,
    }

    # Restore
    settings.DATABASE_PATH = orig_db
    settings.UPLOAD_DIR = orig_upload
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

    shutil.rmtree(temp_dir, ignore_errors=True)
