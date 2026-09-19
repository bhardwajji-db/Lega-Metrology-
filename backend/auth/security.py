"""MetrCheck AI — Authentication & Authorization (stdlib-only, ZERO new pip deps).

Design decisions (hackathon-safe):
- Passwords : PBKDF2-HMAC-SHA256 + per-user random salt  (hashlib stdlib)
- Tokens    : HMAC-SHA256 signed JSON payload w/ expiry   (hand-rolled, no PyJWT install)
- Roles     : ADMIN > ENFORCEMENT_OFFICER > MERCHANT_PUBLIC
- FastAPI   : HTTPBearer dependency + require_roles() guard
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import List, Optional

from fastapi import Depends, HTTPException, status, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from database.db import get_user_by_username

# ── Roles ────────────────────────────────────────────────────────────────
ROLE_ADMIN = "ADMIN"
ROLE_ENFORCEMENT = "ENFORCEMENT_OFFICER"
ROLE_AUDIT = "AUDIT_OFFICER"
ROLE_MERCHANT = "MERCHANT_PUBLIC"

ALL_ROLES = [ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT, ROLE_MERCHANT]

ROLE_LABELS = {
    ROLE_ADMIN: "Administrator",
    ROLE_ENFORCEMENT: "Enforcement Official",
    ROLE_AUDIT: "Quality & Audit Inspector",
    ROLE_MERCHANT: "Brand / Merchant",
}


# ── Secrets ──────────────────────────────────────────────────────────────
def _secret_key() -> bytes:
    key = getattr(settings, "SECRET_KEY", "") or "metrcheck-dev-secret-change-in-prod"
    return key.encode("utf-8")


# ── Password hashing (PBKDF2-HMAC-SHA256) ────────────────────────────────
_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str, salt_hex: Optional[str] = None):
    """Return (password_hash_hex, salt_hex)."""
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return dk.hex(), salt.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    dk, _ = hash_password(password, salt_hex)
    return hmac.compare_digest(dk, expected_hash_hex.lower())


# ── Password Reset & Invitation Tokens & Delivery ────────────────────────
RESET_TOKEN_EXPIRE_MINUTES = 15
INVITATION_TOKEN_EXPIRE_HOURS = 24


def hash_reset_token(token: str) -> str:
    """Return SHA-256 hex digest of the raw token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_password_reset_token(expire_minutes: int = RESET_TOKEN_EXPIRE_MINUTES):
    """Generate (raw_token, token_hash, expires_at_iso)."""
    import datetime
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_reset_token(raw_token)
    expires_at = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=expire_minutes)
    ).isoformat()
    return raw_token, token_hash, expires_at


def generate_invitation_token(expire_hours: int = INVITATION_TOKEN_EXPIRE_HOURS):
    """Generate (raw_token, token_hash, expires_at_iso) for new account invitation."""
    import datetime
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_reset_token(raw_token)
    expires_at = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=expire_hours)
    ).isoformat()
    return raw_token, token_hash, expires_at


class PasswordResetDeliveryProvider:
    """Abstract/base delivery provider for password reset and account invitation instructions."""
    async def send_reset_instructions(self, username: str, raw_token: str, reset_url: str, email: Optional[str] = None) -> bool:
        raise NotImplementedError

    async def send_invitation_email(self, full_name: str, username: str, role: str, raw_token: str, activation_url: str, email: Optional[str] = None) -> bool:
        raise NotImplementedError


class DevLoggerDeliveryProvider(PasswordResetDeliveryProvider):
    """Logs password reset and invitation tokens to logger for local development and testing."""
    def __init__(self):
        self.last_sent: Optional[dict] = None
        self.last_invitation_sent: Optional[dict] = None

    async def send_reset_instructions(self, username: str, raw_token: str, reset_url: str, email: Optional[str] = None) -> bool:
        import logging
        logger = logging.getLogger("metrcheck.auth")
        is_prod = (
            os.environ.get("METRCHECK_ENV") == "production" 
            or os.environ.get("ENVIRONMENT") == "production"
            or getattr(settings, "ENVIRONMENT", "") == "production"
        )
        if is_prod:
            logger.warning(
                f"[PASSWORD RESET] Password reset requested for '{username}', but no production SMTP provider is configured."
            )
            return False

        self.last_sent = {
            "username": username,
            "raw_token": raw_token,
            "reset_url": reset_url,
            "email": email or "",
        }
        logger.info(
            f"[PASSWORD RESET] Dev delivery for '{username}' (email: '{email or 'none'}'): Reset URL = {reset_url} (Token = {raw_token})"
        )
        return True

    async def send_invitation_email(self, full_name: str, username: str, role: str, raw_token: str, activation_url: str, email: Optional[str] = None) -> bool:
        import logging
        logger = logging.getLogger("metrcheck.auth")
        is_prod = (
            os.environ.get("METRCHECK_ENV") == "production" 
            or os.environ.get("ENVIRONMENT") == "production"
            or getattr(settings, "ENVIRONMENT", "") == "production"
        )
        if is_prod:
            logger.warning(
                f"[ACCOUNT INVITATION] Account invitation requested for '{username}', but no production SMTP provider is configured."
            )
            return False

        self.last_invitation_sent = {
            "full_name": full_name,
            "username": username,
            "role": role,
            "raw_token": raw_token,
            "activation_url": activation_url,
            "email": email or "",
        }
        logger.info(
            f"[ACCOUNT INVITATION] Dev delivery for '{username}' ({role}, email: '{email or 'none'}'): Activation URL = {activation_url} (Token = {raw_token})"
        )
        return True


class SMTPDeliveryProvider(PasswordResetDeliveryProvider):
    """Sends password reset and account invitation links via SMTP if configured."""
    def __init__(self, host: str, port: int = 587, user: str = "", password: str = "", from_addr: str = "noreply@metrcheck.gov.in", use_tls: bool = True):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_addr = from_addr
        self.use_tls = use_tls

    async def send_reset_instructions(self, username: str, raw_token: str, reset_url: str, email: Optional[str] = None) -> bool:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        import logging
        logger = logging.getLogger("metrcheck.auth")
        target_email = (email or "").strip()
        if not target_email or "@" not in target_email:
            logger.info(f"SMTP delivery skipped for account '{username}': no valid recovery email configured.")
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "MetrCheck AI — Password Reset Request"
            msg["From"] = self.from_addr
            msg["To"] = target_email

            text_content = (
                f"Hello,\n\n"
                f"A password reset was requested for your MetrCheck AI account '{username}'.\n\n"
                f"Use the link below within {RESET_TOKEN_EXPIRE_MINUTES} minutes to set a new password:\n"
                f"{reset_url}\n\n"
                f"This single-use link will expire in {RESET_TOKEN_EXPIRE_MINUTES} minutes.\n"
                f"If you did not request this password reset, please ignore this email.\n\n"
                f"— MetrCheck AI Compliance Suite\n"
                f"Directorate of Legal Metrology"
            )

            html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>MetrCheck AI — Password Reset Request</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 24px;">
  <div style="max-width: 560px; margin: 0 auto; background-color: #1e293b; border: 1px solid #334155; border-radius: 16px; overflow: hidden; padding: 32px;">
    <div style="border-bottom: 1px solid #334155; padding-bottom: 16px; margin-bottom: 24px;">
      <h1 style="color: #6366f1; font-size: 20px; font-weight: 800; margin: 0;">MetrCheck AI</h1>
      <p style="color: #94a3b8; font-size: 12px; margin: 4px 0 0 0;">AI-Assisted Statutory Legal Metrology Compliance</p>
    </div>
    
    <h2 style="color: #ffffff; font-size: 18px; font-weight: 700; margin-top: 0;">Password Reset Request</h2>
    <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6;">
      A password reset request was received for account <strong style="color: #ffffff;">@{username}</strong>.
    </p>
    <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6;">
      Click the button below within <strong>{RESET_TOKEN_EXPIRE_MINUTES} minutes</strong> to set a new password:
    </p>

    <div style="text-align: center; margin: 28px 0;">
      <a href="{reset_url}" style="background-color: #4f46e5; color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 10px; font-size: 14px; font-weight: 700; display: inline-block;">
        Reset My Password
      </a>
    </div>

    <p style="color: #94a3b8; font-size: 12px; line-height: 1.5; margin-top: 24px;">
      If the button above does not work, copy and paste this link into your browser:<br>
      <a href="{reset_url}" style="color: #818cf8; word-break: break-all;">{reset_url}</a>
    </p>

    <div style="border-top: 1px solid #334155; padding-top: 16px; margin-top: 28px; color: #64748b; font-size: 11px; line-height: 1.5;">
      <p style="margin: 0 0 6px 0;"><strong>Security Notice:</strong> This single-use link expires in {RESET_TOKEN_EXPIRE_MINUTES} minutes. If you did not request this, you can safely ignore this email.</p>
      <p style="margin: 0;">SIH 2026 · Problem Statement 26034</p>
    </div>
  </div>
</body>
</html>"""

            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            server = smtplib.SMTP(self.host, self.port, timeout=8)
            if self.use_tls:
                server.starttls()
            if self.user and self.password:
                server.login(self.user, self.password)
            server.sendmail(self.from_addr, [target_email], msg.as_string())
            server.quit()
            logger.info(f"Password reset email sent successfully to '{target_email}' for account '{username}'.")
            return True
        except Exception as e:
            logger.warning(f"SMTP delivery failed for '{username}' ({target_email}): {e}")
            return False

    async def send_invitation_email(self, full_name: str, username: str, role: str, raw_token: str, activation_url: str, email: Optional[str] = None) -> bool:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        import logging
        logger = logging.getLogger("metrcheck.auth")
        target_email = (email or "").strip()
        if not target_email or "@" not in target_email:
            logger.info(f"SMTP invitation skipped for account '{username}': no valid email configured.")
            return False

        is_audit = role == ROLE_AUDIT
        role_title = "Quality & Audit Inspector" if is_audit else "Enforcement Official"
        workspace_info = (
            "Audit Workspace access for technical compliance verification and calibration audits."
            if is_audit else
            "Enforcement Workspace access (including Audit and Merchant workspaces) for statutory inspection and evidence investigation."
        )
        subject = f"MetrCheck AI — {'Audit' if is_audit else 'Enforcement'} Workspace Access Invitation"

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_addr
            msg["To"] = target_email

            text_content = (
                f"Hello {full_name or username},\n\n"
                f"An administrator has provisioned an authorized MetrCheck AI account for you.\n\n"
                f"Account Details:\n"
                f"- Username: {username}\n"
                f"- Assigned Role: {role_title} ({role})\n"
                f"- Workspace Access: {workspace_info}\n\n"
                f"To activate your account and set your password, please open the link below within {INVITATION_TOKEN_EXPIRE_HOURS} hours:\n"
                f"{activation_url}\n\n"
                f"Security Notice:\n"
                f"- This single-use link expires in {INVITATION_TOKEN_EXPIRE_HOURS} hours.\n"
                f"- MetrCheck AI provisions application workspace roles; organizational authorization exists outside this system.\n\n"
                f"— MetrCheck AI Administration\n"
                f"Directorate of Legal Metrology"
            )

            badge_color = "#6366f1" if is_audit else "#f59e0b"
            html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 24px;">
  <div style="max-width: 580px; margin: 0 auto; background-color: #1e293b; border: 1px solid #334155; border-radius: 16px; overflow: hidden; padding: 32px;">
    <div style="border-bottom: 1px solid #334155; padding-bottom: 16px; margin-bottom: 24px;">
      <h1 style="color: #6366f1; font-size: 20px; font-weight: 800; margin: 0;">MetrCheck AI</h1>
      <p style="color: #94a3b8; font-size: 12px; margin: 4px 0 0 0;">AI-Assisted Statutory Legal Metrology Compliance</p>
    </div>
    
    <div style="display: inline-block; padding: 4px 12px; border-radius: 9999px; background-color: rgba(99,102,241,0.15); border: 1px solid {badge_color}; color: {badge_color}; font-size: 11px; font-weight: 800; text-transform: uppercase; margin-bottom: 12px;">
      {role_title} Invitation
    </div>

    <h2 style="color: #ffffff; font-size: 18px; font-weight: 700; margin-top: 0;">Account Provisioning Invitation</h2>
    <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6;">
      Hello <strong>{full_name or username}</strong>, an administrator has provisioned an authorized account for you on <strong>MetrCheck AI</strong>.
    </p>

    <div style="background-color: #0f172a; border: 1px solid #334155; border-radius: 12px; padding: 16px; margin: 20px 0; font-size: 13px;">
      <p style="margin: 0 0 8px 0; color: #94a3b8;"><strong style="color: #e2e8f0;">Username:</strong> @{username}</p>
      <p style="margin: 0 0 8px 0; color: #94a3b8;"><strong style="color: #e2e8f0;">Assigned Role:</strong> {role_title} (<code style="color: #818cf8;">{role}</code>)</p>
      <p style="margin: 0; color: #94a3b8;"><strong style="color: #e2e8f0;">Workspace Access:</strong> {workspace_info}</p>
    </div>

    <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6;">
      Click the button below within <strong>{INVITATION_TOKEN_EXPIRE_HOURS} hours</strong> to choose your password and activate your account:
    </p>

    <div style="text-align: center; margin: 28px 0;">
      <a href="{activation_url}" style="background-color: #4f46e5; color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 10px; font-size: 14px; font-weight: 700; display: inline-block;">
        Activate My Account
      </a>
    </div>

    <p style="color: #94a3b8; font-size: 12px; line-height: 1.5; margin-top: 24px;">
      If the button above does not work, copy and paste this link into your browser:<br>
      <a href="{activation_url}" style="color: #818cf8; word-break: break-all;">{activation_url}</a>
    </p>

    <div style="border-top: 1px solid #334155; padding-top: 16px; margin-top: 28px; color: #64748b; font-size: 11px; line-height: 1.5;">
      <p style="margin: 0 0 6px 0;"><strong>Security Notice:</strong> This single-use invitation link expires in {INVITATION_TOKEN_EXPIRE_HOURS} hours. Application roles control access within MetrCheck AI; formal legal authority remains an external process.</p>
      <p style="margin: 0;">SIH 2026 · Problem Statement 26034</p>
    </div>
  </div>
</body>
</html>"""

            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            server = smtplib.SMTP(self.host, self.port, timeout=8)
            if self.use_tls:
                server.starttls()
            if self.user and self.password:
                server.login(self.user, self.password)
            server.sendmail(self.from_addr, [target_email], msg.as_string())
            server.quit()
            logger.info(f"Account invitation email sent successfully to '{target_email}' for account '{username}'.")
            return True
        except Exception as e:
            logger.warning(f"SMTP invitation delivery failed for '{username}' ({target_email}): {e}")
            return False


_global_delivery_provider: Optional[PasswordResetDeliveryProvider] = None


def get_delivery_provider() -> PasswordResetDeliveryProvider:
    global _global_delivery_provider
    if _global_delivery_provider is None:
        if "METRCHECK_SMTP_HOST" in os.environ:
            smtp_host = (os.environ.get("METRCHECK_SMTP_HOST") or "").strip()
        else:
            smtp_host = (getattr(settings, "METRCHECK_SMTP_HOST", "") or "").strip()

        if smtp_host:
            port_val = os.environ.get("METRCHECK_SMTP_PORT") or getattr(settings, "METRCHECK_SMTP_PORT", 587)
            user_val = os.environ.get("METRCHECK_SMTP_USER") or getattr(settings, "METRCHECK_SMTP_USER", "")
            pass_val = os.environ.get("METRCHECK_SMTP_PASS") or getattr(settings, "METRCHECK_SMTP_PASS", "")
            from_val = os.environ.get("METRCHECK_SMTP_FROM") or getattr(settings, "METRCHECK_SMTP_FROM", "noreply@metrcheck.gov.in")
            tls_env = os.environ.get("METRCHECK_SMTP_TLS")
            if tls_env is not None:
                tls_val = str(tls_env).lower() in ("true", "1", "yes")
            else:
                tls_val = bool(getattr(settings, "METRCHECK_SMTP_TLS", True))
            _global_delivery_provider = SMTPDeliveryProvider(
                host=smtp_host,
                port=int(port_val),
                user=user_val,
                password=pass_val,
                from_addr=from_val,
                use_tls=tls_val,
            )
        else:
            _global_delivery_provider = DevLoggerDeliveryProvider()
    return _global_delivery_provider


def set_delivery_provider(provider: Optional[PasswordResetDeliveryProvider]):
    global _global_delivery_provider
    _global_delivery_provider = provider


def get_delivery_provider_status() -> dict:
    """Safe internal check for delivery configuration without leaking credentials."""
    provider = get_delivery_provider()
    is_smtp = isinstance(provider, SMTPDeliveryProvider)
    is_prod = (
        os.environ.get("METRCHECK_ENV") == "production" 
        or os.environ.get("ENVIRONMENT") == "production" 
        or getattr(settings, "ENVIRONMENT", "") == "production"
    )
    return {
        "provider_type": "SMTP" if is_smtp else "DEVELOPMENT_LOGGER",
        "smtp_configured": is_smtp,
        "smtp_host": provider.host if is_smtp else None,
        "smtp_port": provider.port if is_smtp else None,
        "smtp_from": provider.from_addr if is_smtp else None,
        "is_production": is_prod,
    }


# ── Token signing (HMAC-SHA256) ──────────────────────────────────────────
def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def create_token(username: str, role: str, token_version: int = 1) -> str:
    now = int(time.time())
    payload = {
        "sub": username,
        "role": role,
        "token_version": token_version,
        "iat": now,
        "exp": now + int(getattr(settings, "TOKEN_EXPIRE_MINUTES", 60) or 60) * 60,
    }
    body = _b64e(json.dumps(payload).encode("utf-8"))
    sig = hmac.new(_secret_key(), body.encode("utf-8"), hashlib.sha256).digest()
    return f"{body}.{_b64e(sig)}"


def decode_token(token: str) -> Optional[dict]:
    """Return payload dict if signature + expiry valid, else None."""
    try:
        body, sig = token.split(".")
        expected = hmac.new(_secret_key(), body.encode("utf-8"), hashlib.sha256).digest()
        if not hmac.compare_digest(sig, _b64e(expected)):
            return None
        payload = json.loads(_b64d(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# ── FastAPI dependencies ─────────────────────────────────────────────────
_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    token: Optional[str] = Query(None, alias="token"),
) -> dict:
    """Authenticate request via Bearer token or token query parameter. 401/403 when missing/invalid/expired/suspended."""
    raw_token = credentials.credentials if credentials else token
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authentication required. Please log in.")
    payload = decode_token(raw_token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or expired token. Please log in again.")
    username = payload.get("sub", "")
    user = await get_user_by_username(username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="User account no longer exists.")

    user_status = user.get("status", "ACTIVE") or "ACTIVE"
    if user_status == "SUSPENDED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been suspended. Please contact system administrator."
        )
    if user_status == "INVITED":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account invitation has not been activated yet."
        )

    # Validate token_version for immediate invalidation upon role change or suspension
    token_v = payload.get("token_version")
    db_v = user.get("token_version", 1) or 1
    if token_v is not None and token_v != db_v:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or credentials changed. Please log in again."
        )

    return user


def require_roles(*roles: str):
    """Dependency factory — returns a guard that allows only listed roles."""

    async def _role_guard(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Insufficient privileges for this operation.")
        return user

    return _role_guard


async def public_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    token: Optional[str] = Query(None, alias="token"),
) -> Optional[dict]:
    """Optional auth — returns user dict or None (for mixed public/private endpoints)."""
    raw_token = credentials.credentials if credentials else token
    if not raw_token:
        return None
    payload = decode_token(raw_token)
    if payload is None:
        return None
    username = payload.get("sub", "")
    user = await get_user_by_username(username)
    if user:
        return user
    return {"username": username, "role": payload.get("role", "MERCHANT_PUBLIC"), "organization_id": ""}


get_current_user_optional = public_user


def check_tenant_access(user: Optional[dict], resource: Optional[dict], allow_public: bool = False, raise_exception: bool = False) -> bool:
    """
    Multi-tenant isolation security enforcement guard (Strictly Fail-Closed).
    Rules:
    1. If user is None or not authenticated:
       - If allow_public is True, allows access; else False (or 401).
    2. Admin (ROLE_ADMIN):
       - System-wide statutory oversight permitted across all organizations.
    3. Enforcement / Audit Officers (ROLE_ENFORCEMENT, ROLE_AUDIT):
       - Strictly scoped to their assigned organization_id.
       - Both user.organization_id and resource.organization_id must be non-empty and match.
       - Unassigned legacy resources (resource.organization_id == "") are ADMIN-only.
    4. Merchant / Public (ROLE_MERCHANT):
       - Strictly scoped to their organization_id.
       - Both user.organization_id and resource.organization_id must be non-empty and match.
       - Must ALSO match record ownership (owner_user_id == username or user.id).
    5. Unknown / Missing roles:
       - Deny access (403 Forbidden).
    
    Returns True if permitted, False otherwise (or raises HTTPException if raise_exception is True).
    """
    if not user:
        if allow_public:
            return True
        if raise_exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required."
            )
        return False

    if not resource:
        if raise_exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found."
            )
        return False

    user_role = user.get("role")
    if user_role == ROLE_ADMIN:
        return True

    user_org = (user.get("organization_id") or "").strip()
    res_org = (resource.get("organization_id") or "").strip()
    owner = (resource.get("owner_user_id") or "").strip()
    username = (user.get("username") or "").strip()
    uid = str(user.get("id", "")).strip() if user.get("id") is not None else ""

    # Officers (ROLE_ENFORCEMENT, ROLE_AUDIT) - strictly fail-closed
    if user_role in (ROLE_ENFORCEMENT, ROLE_AUDIT):
        if not user_org or not res_org or user_org != res_org:
            if raise_exception:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Resource does not belong to your organization or organization is not assigned."
                )
            return False
        return True

    # Merchants (ROLE_MERCHANT) - strictly fail-closed (org match + ownership)
    if user_role == ROLE_MERCHANT:
        if not user_org or not res_org or user_org != res_org:
            if raise_exception:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Resource does not belong to your organization or organization is not assigned."
                )
            return False
        
        is_owner = False
        if owner:
            is_owner = (owner.lower() == username.lower()) or (bool(uid) and owner == uid)
        else:
            is_owner = False

        if not is_owner:
            if raise_exception:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You do not have permission to access this resource."
                )
            return False
        return True

    if raise_exception:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Insufficient privileges."
        )
    return False