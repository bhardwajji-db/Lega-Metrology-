import pytest
import os
import sys

from auth.security import ROLE_ADMIN, ROLE_MERCHANT, verify_password, hash_password
from database.db import get_user_by_username, get_db, create_user
from scripts.bootstrap_admin import bootstrap_admin

@pytest.mark.asyncio
async def test_bootstrap_admin_creation_and_idempotency():
    # 1. Bootstrap new admin
    success = await bootstrap_admin(
        username="bootstrap_admin_test",
        password="AdminTestPassword123!",
        email="bootstrap_admin@metrcheck.gov.in",
        full_name="Bootstrap Admin",
        jurisdiction="DoCA Directorate",
        overwrite=False
    )
    assert success is True

    user = await get_user_by_username("bootstrap_admin_test")
    assert user is not None
    assert user["role"] == ROLE_ADMIN
    assert user["email"] == "bootstrap_admin@metrcheck.gov.in"
    assert user["status"] == "ACTIVE"
    assert verify_password("AdminTestPassword123!", user["salt"], user["password_hash"]) is True

    # 2. Idempotent rerun without overwrite should succeed without altering password
    success_idemp = await bootstrap_admin(
        username="bootstrap_admin_test",
        password="DifferentPassword456!",
        overwrite=False
    )
    assert success_idemp is True
    user_after = await get_user_by_username("bootstrap_admin_test")
    assert verify_password("AdminTestPassword123!", user_after["salt"], user_after["password_hash"]) is True

    # 3. Rerun with overwrite should update credentials
    success_overwrite = await bootstrap_admin(
        username="bootstrap_admin_test",
        password="NewAdminPassword789!",
        email="new_email@metrcheck.gov.in",
        overwrite=True
    )
    assert success_overwrite is True
    user_updated = await get_user_by_username("bootstrap_admin_test")
    assert user_updated["email"] == "new_email@metrcheck.gov.in"
    assert verify_password("NewAdminPassword789!", user_updated["salt"], user_updated["password_hash"]) is True


@pytest.mark.asyncio
async def test_bootstrap_admin_safety_protections():
    # 1. Cannot overwrite omsainikaul
    fail_om = await bootstrap_admin(
        username="omsainikaul",
        password="AttemptPassword123!",
        overwrite=True
    )
    assert fail_om is False

    # 2. Cannot use weak password (< 8 chars)
    fail_weak = await bootstrap_admin(
        username="weak_admin_test",
        password="short",
        overwrite=True
    )
    assert fail_weak is False

    # 3. Cannot overwrite non-admin existing account
    pw_hash, salt = hash_password("MerchantPass123!")
    await create_user("some_merchant", pw_hash, salt, ROLE_MERCHANT, email="merchant@test.com")
    fail_nonadmin = await bootstrap_admin(
        username="some_merchant",
        password="NewAdminPass123!",
        overwrite=True
    )
    assert fail_nonadmin is False
