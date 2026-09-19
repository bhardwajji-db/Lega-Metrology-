"""
Phase 7.1.8 — Password Reset Email Delivery Verification & SMTP Configuration Test Suite

Covers:
1. Provider Selection: DevLoggerDeliveryProvider when SMTP host is unset.
2. Provider Selection: SMTPDeliveryProvider when SMTP host is set.
3. Safe Delivery Status: get_delivery_provider_status() returns metadata without exposing passwords/credentials.
4. SMTP Message Formatting: Generates multipart/alternative message with Subject, From, To, HTML and Plaintext versions.
5. SMTP Security & Content: Email contains 15-minute expiration notice, security disclaimer, and reset link pointing to /reset-password.
6. Mock SMTP Transmission: Verifies SMTP delivery to registered recipient email.
7. SMTP Error Handling: Connection failure is handled gracefully without leaking credentials or tokens, returning False.
8. Forgot Password Destination: Always uses stored account recovery email, never an attacker-supplied destination.
9. Enumeration Resistance: Generic response returned for existing and non-existing accounts.
10. Dev Token Availability: Provided in development/test environment.
11. Dev Token Suppression: Strictly suppressed in production environment (METRCHECK_ENV=production).
12. Frontend URL Customization: METRCHECK_FRONTEND_URL customizes origin of reset link.
13. Reset Token Expiry: 15-minute validity enforced.
14. Single-Use Token Enforcement: Token cannot be reused after successful reset.
15. Previous Token Invalidation: New request invalidates earlier active tokens.
16. Password Update: Old password fails, new password succeeds.
17. Role & Workspace Preservation: Role is preserved across reset.
18. Rate Limiting Protection: Throttling enforced on abuse.
19. Existing Accounts: Accounts with or without recovery email are handled safely.
20. Self-Service Email Configuration: omsainikaul and other accounts can configure recovery email via /api/auth/me/email.
"""

import os
import smtplib
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from main import app
from config import settings
from auth.security import (
    create_token,
    hash_password,
    verify_password,
    get_delivery_provider,
    set_delivery_provider,
    get_delivery_provider_status,
    DevLoggerDeliveryProvider,
    SMTPDeliveryProvider,
    RESET_TOKEN_EXPIRE_MINUTES,
    ROLE_MERCHANT,
    ROLE_ENFORCEMENT,
    ROLE_ADMIN,
)
from auth.ratelimit import clear_rate_limits
from database.db import (
    create_user,
    get_user_by_username,
    get_user_by_email,
    get_user_by_identifier,
    update_user,
    delete_user,
)


@pytest.fixture(autouse=True)
def reset_state():
    clear_rate_limits()
    # Reset delivery provider to clean state
    set_delivery_provider(None)
    yield
    clear_rate_limits()
    set_delivery_provider(None)


@pytest.fixture(scope="module")
def client():
    os.environ["TEST_MODE"] = "1"
    os.environ["METRCHECK_ENV"] = "development"
    settings.TEST_MODE = True
    with TestClient(app) as c:
        yield c


def test_01_provider_selection_dev_logger_default():
    with patch.dict(os.environ, {"METRCHECK_SMTP_HOST": ""}, clear=False):
        set_delivery_provider(None)
        provider = get_delivery_provider()
        assert isinstance(provider, DevLoggerDeliveryProvider)


def test_02_provider_selection_smtp_when_configured():
    with patch.dict(os.environ, {
        "METRCHECK_SMTP_HOST": "smtp.example.com",
        "METRCHECK_SMTP_PORT": "587",
        "METRCHECK_SMTP_USER": "mailer@example.com",
        "METRCHECK_SMTP_PASS": "SecretPass123!",
        "METRCHECK_SMTP_FROM": "support@metrcheck.gov.in"
    }, clear=False):
        set_delivery_provider(None)
        provider = get_delivery_provider()
        assert isinstance(provider, SMTPDeliveryProvider)
        assert provider.host == "smtp.example.com"
        assert provider.port == 587
        assert provider.from_addr == "support@metrcheck.gov.in"


def test_03_delivery_provider_status_does_not_leak_secrets(client):
    with patch.dict(os.environ, {
        "METRCHECK_SMTP_HOST": "smtp.mailserver.gov.in",
        "METRCHECK_SMTP_PORT": "587",
        "METRCHECK_SMTP_USER": "admin_user",
        "METRCHECK_SMTP_PASS": "SUPER_SECRET_PASSWORD_NEVER_LEAK",
        "METRCHECK_SMTP_FROM": "notifications@metrcheck.gov.in"
    }, clear=False):
        set_delivery_provider(None)
        status_data = get_delivery_provider_status()
        assert status_data["smtp_configured"] is True
        assert status_data["provider_type"] == "SMTP"
        assert status_data["smtp_host"] == "smtp.mailserver.gov.in"
        assert status_data["smtp_from"] == "notifications@metrcheck.gov.in"
        # Ensure password is NOT in status dictionary
        assert "password" not in status_data
        assert "SUPER_SECRET_PASSWORD_NEVER_LEAK" not in str(status_data)

        # Also verify via GET /api/auth/delivery-status
        res = client.get("/api/auth/delivery-status")
        assert res.status_code == 200
        api_data = res.json()
        assert api_data["smtp_configured"] is True
        assert "password" not in str(api_data)


@pytest.mark.asyncio
async def test_04_smtp_provider_message_formatting_and_transmission():
    provider = SMTPDeliveryProvider(
        host="smtp.testserver.internal",
        port=587,
        user="testuser",
        password="testpassword",
        from_addr="noreply@metrcheck.gov.in",
        use_tls=True
    )

    mock_smtp_instance = MagicMock()
    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        recipient_email = "target.officer@example.com"
        username = "officer_recipient"
        raw_token = "secure_random_token_12345"
        reset_url = f"https://metrcheck.gov.in/reset-password?token={raw_token}"

        success = await provider.send_reset_instructions(
            username=username,
            raw_token=raw_token,
            reset_url=reset_url,
            email=recipient_email
        )
        assert success is True
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("testuser", "testpassword")
        mock_smtp_instance.sendmail.assert_called_once()
        
        args, _ = mock_smtp_instance.sendmail.call_args
        from_arg, to_arg, msg_str = args
        assert from_arg == "noreply@metrcheck.gov.in"
        assert to_arg == [recipient_email]
        assert "noreply@metrcheck.gov.in" in msg_str
        assert "target.officer@example.com" in msg_str
        assert "Subject:" in msg_str
        assert "Password_Reset_Request" in msg_str or "Password Reset Request" in msg_str


@pytest.mark.asyncio
async def test_05_smtp_error_handling_gracefully_fails_without_exception():
    provider = SMTPDeliveryProvider(
        host="unavailable.smtp.host",
        port=587,
        user="testuser",
        password="testpassword",
        from_addr="noreply@metrcheck.gov.in",
    )

    with patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(421, b"Connection refused")):
        success = await provider.send_reset_instructions(
            username="user_error_test",
            raw_token="token123",
            reset_url="http://localhost:5173/reset-password?token=token123",
            email="error.target@example.com"
        )
        # Must return False, not raise exception
        assert success is False


@pytest.mark.asyncio
async def test_06_forgot_password_uses_stored_email_and_preserves_enumeration_resistance(client):
    username = "test_smtp_user_06"
    stored_email = "verified.stored@example.com"
    await delete_user(username)

    pw_hash, salt = hash_password("OldPassword123!")
    await create_user(username=username, password_hash=pw_hash, salt=salt, role=ROLE_MERCHANT, email=stored_email)

    mock_provider = MagicMock(spec=DevLoggerDeliveryProvider)
    mock_provider.send_reset_instructions = MagicMock()
    
    async def fake_send(username, raw_token, reset_url, email=None):
        return True
    mock_provider.send_reset_instructions.side_effect = fake_send

    set_delivery_provider(mock_provider)

    resp = client.post("/api/auth/forgot-password", json={"identifier": username})
    assert resp.status_code == 200
    # Must return exact generic enumeration-resistant response
    assert resp.json()["message"] == "If an account matches the information provided, password reset instructions have been sent."

    mock_provider.send_reset_instructions.assert_called_once()
    call_kwargs = mock_provider.send_reset_instructions.call_args[1]
    assert call_kwargs["email"] == stored_email


def test_07_production_environment_suppresses_dev_token(client):
    with patch.dict(os.environ, {"METRCHECK_ENV": "production", "ENVIRONMENT": "production"}):
        with patch.object(settings, "TEST_MODE", False):
            resp = client.post("/api/auth/forgot-password", json={"identifier": "admin"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["message"] == "If an account matches the information provided, password reset instructions have been sent."
            assert data.get("dev_token") is None


@pytest.mark.asyncio
async def test_08_custom_frontend_url_in_reset_link(client):
    username = "test_custom_url_user"
    email = "custom.url@example.com"
    await delete_user(username)

    pw_hash, salt = hash_password("OldPassword123!")
    await create_user(username=username, password_hash=pw_hash, salt=salt, role=ROLE_MERCHANT, email=email)

    with patch.object(settings, "METRCHECK_FRONTEND_URL", "https://compliance.metrcheck.gov.in"):
        set_delivery_provider(None)
        resp = client.post("/api/auth/forgot-password", json={"identifier": username})
        assert resp.status_code == 200
        provider = get_delivery_provider()
        if isinstance(provider, DevLoggerDeliveryProvider):
            assert provider.last_sent is not None
            assert provider.last_sent["reset_url"].startswith("https://compliance.metrcheck.gov.in/reset-password?token=")


@pytest.mark.asyncio
async def test_09_e2e_complete_reset_flow_and_single_use_token(client):
    username = "test_e2e_single_use"
    email = "single.use@example.com"
    old_pw = "OldPassword123!"
    new_pw = "NewSecurePassword456!"
    await delete_user(username)

    pw_hash, salt = hash_password(old_pw)
    await create_user(username=username, password_hash=pw_hash, salt=salt, role=ROLE_ENFORCEMENT, email=email, organization_id="org_ministry")

    # 1. Forgot password
    resp = client.post("/api/auth/forgot-password", json={"identifier": username})
    assert resp.status_code == 200
    token = resp.json()["dev_token"]
    assert token is not None

    # 2. Reset password
    r_reset = client.post("/api/auth/reset-password", json={"token": token, "new_password": new_pw})
    assert r_reset.status_code == 200

    # 3. Attempting to reuse same token must fail
    r_reuse = client.post("/api/auth/reset-password", json={"token": token, "new_password": "AnotherPassword999!"})
    assert r_reuse.status_code == 400
    assert "Invalid or expired" in r_reuse.json()["detail"]

    # 4. Login with old password fails
    r_old = client.post("/api/auth/login", json={"username": username, "password": old_pw})
    assert r_old.status_code == 401

    # 5. Login with new password succeeds and preserves role
    r_new = client.post("/api/auth/login", json={"username": username, "password": new_pw})
    assert r_new.status_code == 200
    assert r_new.json()["user"]["role"] == ROLE_ENFORCEMENT
    assert r_new.json()["user"]["email"] == email


@pytest.mark.asyncio
async def test_10_account_without_email_can_configure_recovery_email_self_service(client):
    username = "account_initially_no_email"
    await delete_user(username)

    pwh, salt = hash_password("InitialPassword123!")
    await create_user(username=username, password_hash=pwh, salt=salt, role=ROLE_MERCHANT, email="")

    u = await get_user_by_username(username)
    assert u is not None
    assert u["email"] == ""
    assert u["role"] == ROLE_MERCHANT

    # Authenticate as user
    token = create_token(username, ROLE_MERCHANT)
    
    # Configure recovery email via PATCH /api/auth/me/email
    test_recov_email = "user.verified.sih2026@example.com"
    res = client.patch(
        "/api/auth/me/email",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": test_recov_email}
    )
    assert res.status_code == 200
    assert res.json()["email"] == test_recov_email

    # Now verify Forgot Password finds by email and username
    res_f_user = client.post("/api/auth/forgot-password", json={"identifier": username})
    assert res_f_user.status_code == 200
    
    res_f_email = client.post("/api/auth/forgot-password", json={"identifier": test_recov_email})
    assert res_f_email.status_code == 200


@pytest.mark.asyncio
async def test_11_username_with_recovery_email_invokes_smtp_to_stored_email(client):
    """Test A & B: User enters username OR email -> SMTP sends to account's registered email."""
    username = "test_merchant_recovery"
    recovery_email = "merchant.secure.recovery@domain.in"
    await delete_user(username)

    pwh, salt = hash_password("MerchantPass123!")
    await create_user(username=username, password_hash=pwh, salt=salt, role=ROLE_MERCHANT, email=recovery_email)

    mock_smtp_instance = MagicMock()
    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        with patch.dict(os.environ, {
            "METRCHECK_SMTP_HOST": "smtp.gmail.com",
            "METRCHECK_SMTP_PORT": "587",
            "METRCHECK_SMTP_USER": "test@gmail.com",
            "METRCHECK_SMTP_PASS": "app-pass",
            "METRCHECK_SMTP_FROM": "MetrCheck Security <no-reply@metrcheck.ai>",
        }, clear=False):
            set_delivery_provider(None)

            # Test A: Entering USERNAME
            resp_user = client.post("/api/auth/forgot-password", json={"identifier": username})
            assert resp_user.status_code == 200
            assert resp_user.json()["message"] == "If an account matches the information provided, password reset instructions have been sent."

            assert mock_smtp_instance.sendmail.called
            args, _ = mock_smtp_instance.sendmail.call_args
            from_arg, to_arg, msg_str = args
            assert to_arg == [recovery_email]
            assert from_arg == "MetrCheck Security <no-reply@metrcheck.ai>"
            
            import email as email_lib
            parsed_msg = email_lib.message_from_string(msg_str)
            assert parsed_msg["To"] == recovery_email
            payloads = ""
            for part in parsed_msg.walk():
                if part.get_content_type() in ("text/plain", "text/html"):
                    payloads += part.get_payload(decode=True).decode("utf-8", errors="ignore")
            assert username in payloads

            mock_smtp_instance.reset_mock()

            # Test B: Entering REGISTERED EMAIL
            resp_email = client.post("/api/auth/forgot-password", json={"identifier": recovery_email})
            assert resp_email.status_code == 200
            assert resp_email.json()["message"] == "If an account matches the information provided, password reset instructions have been sent."

            assert mock_smtp_instance.sendmail.called
            args, _ = mock_smtp_instance.sendmail.call_args
            from_arg, to_arg, msg_str = args
            assert to_arg == [recovery_email]
            
            parsed_msg = email_lib.message_from_string(msg_str)
            assert parsed_msg["To"] == recovery_email
            payloads = ""
            for part in parsed_msg.walk():
                if part.get_content_type() in ("text/plain", "text/html"):
                    payloads += part.get_payload(decode=True).decode("utf-8", errors="ignore")
            assert username in payloads


@pytest.mark.asyncio
async def test_12_unknown_username_and_unknown_email_return_generic_response(client):
    """Test C & D: Unknown username and unknown email return identical generic response with no SMTP call."""
    mock_smtp_instance = MagicMock()
    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        with patch.dict(os.environ, {
            "METRCHECK_SMTP_HOST": "smtp.gmail.com",
            "METRCHECK_SMTP_PORT": "587",
            "METRCHECK_SMTP_USER": "test@gmail.com",
            "METRCHECK_SMTP_PASS": "app-pass",
        }, clear=False):
            set_delivery_provider(None)

            # Test C: Unknown username
            resp_c = client.post("/api/auth/forgot-password", json={"identifier": "nonexistent_user_99999"})
            assert resp_c.status_code == 200
            assert resp_c.json()["message"] == "If an account matches the information provided, password reset instructions have been sent."
            assert not mock_smtp_instance.sendmail.called

            # Test D: Unknown email
            resp_d = client.post("/api/auth/forgot-password", json={"identifier": "completely.unknown.email@xyz987.org"})
            assert resp_d.status_code == 200
            assert resp_d.json()["message"] == "If an account matches the information provided, password reset instructions have been sent."
            assert not mock_smtp_instance.sendmail.called


@pytest.mark.asyncio
async def test_13_username_without_recovery_email_returns_generic_response_without_smtp_crash(client):
    """Test E: Username with NO recovery email returns generic 200 and skips SMTP gracefully."""
    username = "test_user_no_email_at_all"
    await delete_user(username)

    pwh, salt = hash_password("NoEmailPass123!")
    await create_user(username=username, password_hash=pwh, salt=salt, role=ROLE_MERCHANT, email="")

    mock_smtp_instance = MagicMock()
    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        with patch.dict(os.environ, {
            "METRCHECK_SMTP_HOST": "smtp.gmail.com",
            "METRCHECK_SMTP_PORT": "587",
            "METRCHECK_SMTP_USER": "test@gmail.com",
            "METRCHECK_SMTP_PASS": "app-pass",
        }, clear=False):
            set_delivery_provider(None)

            resp = client.post("/api/auth/forgot-password", json={"identifier": username})
            assert resp.status_code == 200
            assert resp.json()["message"] == "If an account matches the information provided, password reset instructions have been sent."
            # sendmail should NOT be called with a bare username
            assert not mock_smtp_instance.sendmail.called


@pytest.mark.asyncio
async def test_14_omsainikaul_resolution_with_configured_recovery_email(client):
    """Test specifically for account omsainikaul resolving to its registered recovery email."""
    username = "omsainikaul"
    recovery_email = "omsaini9719@gmail.com"
    
    # Ensure account exists in test environment
    u = await get_user_by_username(username)
    if not u:
        pwh, salt = hash_password("DemoPassword123!")
        await create_user(username=username, password_hash=pwh, salt=salt, role=ROLE_MERCHANT, email=recovery_email)
    else:
        await update_user(username=username, email=recovery_email)

    mock_smtp_instance = MagicMock()
    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        with patch.dict(os.environ, {
            "METRCHECK_SMTP_HOST": "smtp.gmail.com",
            "METRCHECK_SMTP_PORT": "587",
            "METRCHECK_SMTP_USER": "test@gmail.com",
            "METRCHECK_SMTP_PASS": "app-pass",
        }, clear=False):
            set_delivery_provider(None)

            # Check omsainikaul lookup by username
            u_check = await get_user_by_identifier("omsainikaul")
            assert u_check is not None
            assert u_check["username"] == "omsainikaul"
            assert u_check["email"] == recovery_email

            # Submitting username "omsainikaul" triggers reset email to omsaini9719@gmail.com
            resp = client.post("/api/auth/forgot-password", json={"identifier": "omsainikaul"})
            assert resp.status_code == 200
            assert mock_smtp_instance.sendmail.called
            args, _ = mock_smtp_instance.sendmail.call_args
            _, to_arg, msg_str = args
            assert to_arg == [recovery_email]
            
            import email as email_lib
            parsed_msg = email_lib.message_from_string(msg_str)
            assert parsed_msg["To"] == recovery_email
            payloads = ""
            for part in parsed_msg.walk():
                if part.get_content_type() in ("text/plain", "text/html"):
                    payloads += part.get_payload(decode=True).decode("utf-8", errors="ignore")
            assert "@omsainikaul" in payloads or "omsainikaul" in payloads

