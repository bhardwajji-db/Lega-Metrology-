"""
Unit and Integration Tests for SEC-AUD-04 — Production Secret / Default Secret Hardening.

Vulnerability Reference: SEC-AUD-04
Components Under Test:
  - backend/config.py: Settings, validate_production_secrets, KNOWN_INSECURE_SECRETS
  - backend/auth/security.py: _secret_key, create_token, decode_token
  - backend/main.py: lifespan startup secret validation

Security Requirements:
1. Production mode strictly rejects startup if SECRET_KEY is missing, empty, or whitespace.
2. Production mode strictly rejects startup if SECRET_KEY matches known insecure/development defaults.
3. Production mode strictly rejects secrets with insufficient length/entropy (< 32 characters).
4. Development and Test modes allow seamless local execution and test isolation.
5. Token creation and verification correctly use HMAC-SHA256 with the configured secret.
6. Tokens signed with Secret A are completely rejected under Secret B (rotation/isolation).
7. Configuration validation errors never leak raw secret values in exception strings.
"""

import os
import pytest
from unittest.mock import patch
from pydantic import ValidationError

from config import Settings, KNOWN_INSECURE_SECRETS, settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from auth.security import (
    create_token,
    decode_token,
    _secret_key,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
)


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


# ═════════════════════════════════════════════════════════════════════════════
# 1. PRODUCTION SECRET VALIDATION & STRENGTH CHECKS
# ═════════════════════════════════════════════════════════════════════════════

def test_01_production_without_secret_key_rejected():
    """Production mode with empty or missing SECRET_KEY must fail validation."""
    _ensure_test_isolation()
    with pytest.raises(ValueError) as exc_info:
        Settings(ENVIRONMENT="production", SECRET_KEY="", TEST_MODE=False)
    assert "SECRET_KEY must be configured in production" in str(exc_info.value)


def test_02_production_with_known_development_secret_rejected():
    """Production mode with default dev secret must fail validation."""
    _ensure_test_isolation()
    for insecure_secret in KNOWN_INSECURE_SECRETS:
        with pytest.raises(ValueError) as exc_info:
            Settings(ENVIRONMENT="production", SECRET_KEY=insecure_secret, TEST_MODE=False)
        assert "Default or known placeholder SECRET_KEY cannot be used in production" in str(exc_info.value)


def test_03_production_with_short_secret_rejected():
    """Production mode with secret under 32 characters must fail validation."""
    _ensure_test_isolation()
    short_secret = "short_secret_under_32_chars!"
    with pytest.raises(ValueError) as exc_info:
        Settings(ENVIRONMENT="production", SECRET_KEY=short_secret, TEST_MODE=False)
    assert "at least 32 characters long" in str(exc_info.value)


def test_04_production_with_strong_secret_accepted():
    """Production mode with strong 32+ character secret is accepted."""
    _ensure_test_isolation()
    strong_secret = "c7e8a912b45f60d3e1f2a3b4c5d6e7f809123456789abcdef0123456789abcde"
    s = Settings(ENVIRONMENT="production", SECRET_KEY=strong_secret, TEST_MODE=False)
    assert s.SECRET_KEY == strong_secret
    assert s.ENVIRONMENT == "production"


# ═════════════════════════════════════════════════════════════════════════════
# 2. DEVELOPMENT & TEST ENVIRONMENT PRESERVATION
# ═════════════════════════════════════════════════════════════════════════════

def test_05_development_environment_preserves_default_behavior():
    """Development environment allows default development secret for local workflow."""
    _ensure_test_isolation()
    s = Settings(ENVIRONMENT="development", SECRET_KEY="metrcheck-dev-secret-change-in-prod", TEST_MODE=False)
    assert s.ENVIRONMENT == "development"
    assert s.SECRET_KEY == "metrcheck-dev-secret-change-in-prod"


def test_06_test_environment_allows_test_initialization():
    """TEST_MODE=True bypasses production secret enforcement for automated test isolation."""
    _ensure_test_isolation()
    s = Settings(ENVIRONMENT="production", SECRET_KEY="test-key", TEST_MODE=True)
    assert s.TEST_MODE is True
    assert s.SECRET_KEY == "test-key"


# ═════════════════════════════════════════════════════════════════════════════
# 3. CRYPTOGRAPHIC TOKEN SIGNING & ROTATION VERIFICATION
# ═════════════════════════════════════════════════════════════════════════════

def test_07_token_signing_and_decoding_roundtrip():
    """Bearer tokens generated with valid secret decode and verify successfully."""
    _ensure_test_isolation()
    token = create_token("admin_user", ROLE_ADMIN, token_version=1)
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "admin_user"
    assert payload["role"] == ROLE_ADMIN
    assert payload["token_version"] == 1


def test_08_token_signature_fails_under_different_secret():
    """Tokens signed with Secret A cannot be decoded or verified under Secret B."""
    _ensure_test_isolation()
    secret_a = "secret_a_12345678901234567890123456789012"
    secret_b = "secret_b_98765432109876543210987654321098"

    # Create token under secret A
    with patch.object(settings, "SECRET_KEY", secret_a):
        token_a = create_token("officer_alpha", ROLE_ENFORCEMENT)

    # Verify token validates under secret A
    with patch.object(settings, "SECRET_KEY", secret_a):
        payload_a = decode_token(token_a)
        assert payload_a is not None
        assert payload_a["sub"] == "officer_alpha"

    # Verify token completely fails under secret B
    with patch.object(settings, "SECRET_KEY", secret_b):
        payload_b = decode_token(token_a)
        assert payload_b is None, "Token signed with Secret A must fail verification under Secret B"


def test_09_tampered_token_body_rejected():
    """Tampering with token payload payload invalidates HMAC signature."""
    _ensure_test_isolation()
    token = create_token("regular_officer", ROLE_ENFORCEMENT)
    parts = token.split(".")
    assert len(parts) == 2

    # Forge/tamper payload
    tampered_token = f"eyJzdWIiOiAic3VwZXJhZG1pbiIsICJyb2xlIjogIkFETUlOIn0.{parts[1]}"
    assert decode_token(tampered_token) is None


# ═════════════════════════════════════════════════════════════════════════════
# 4. SECRET LEAKAGE PREVENTION IN ERRORS
# ═════════════════════════════════════════════════════════════════════════════

def test_10_validation_error_does_not_leak_raw_secret():
    """Ensure error messages do not echo or log the candidate secret string."""
    _ensure_test_isolation()
    raw_secret_candidate = "my_super_secret_password_12345"
    with pytest.raises(ValueError) as exc_info:
        Settings(ENVIRONMENT="production", SECRET_KEY=raw_secret_candidate, TEST_MODE=False)
    err_str = str(exc_info.value)
    assert raw_secret_candidate not in err_str, "Validation error must never echo the raw secret value"
    assert "at least 32 characters long" in err_str
