import os
import sys
import aiosqlite
import json
from typing import Optional, List, Dict, Any
from config import settings, PROD_DATABASE_PATH


def _check_safety_guard():
    is_pytest = "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ
    if settings.TEST_MODE or os.environ.get("TEST_MODE") == "1" or is_pytest:
        resolved_db = os.path.abspath(settings.DATABASE_PATH)
        if resolved_db == PROD_DATABASE_PATH:
            raise RuntimeError(
                f"SAFETY ERROR: Automated tests cannot run against the production/development database ({PROD_DATABASE_PATH})!\n"
                f"Please ensure tests use isolated_test_env() or conftest with a dedicated temporary database."
            )


async def get_db():
    _check_safety_guard()
    db = await aiosqlite.connect(settings.DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL;")
    await db.execute("PRAGMA busy_timeout=5000;")
    return db



async def init_db():
    db = await get_db()
    try:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                product_name TEXT,
                image_filename TEXT,
                ocr_text TEXT,
                extracted_data TEXT,
                compliance_result TEXT,
                score REAL,
                status TEXT,
                created_at TEXT,
                images TEXT,
                owner_user_id TEXT DEFAULT ''
            )
        ''')
        await db.commit()
        # Ensure column exists if table was created previously without 'images' or 'owner_user_id'
        try:
            await db.execute('ALTER TABLE analyses ADD COLUMN images TEXT')
            await db.commit()
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE analyses ADD COLUMN owner_user_id TEXT DEFAULT ''")
            await db.commit()
        except Exception:
            pass

        # ── Users table (role-based access) ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'MERCHANT_PUBLIC',
                full_name TEXT DEFAULT '',
                jurisdiction TEXT DEFAULT '',
                email TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                invitation_token_hash TEXT DEFAULT '',
                invitation_expires_at TEXT DEFAULT '',
                invited_at TEXT DEFAULT '',
                activated_at TEXT DEFAULT '',
                token_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        ''')
        await db.commit()

        # Idempotently ensure email and provisioning columns exist
        for col, typedef in [
            ("email", "TEXT DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'ACTIVE'"),
            ("invitation_token_hash", "TEXT DEFAULT ''"),
            ("invitation_expires_at", "TEXT DEFAULT ''"),
            ("invited_at", "TEXT DEFAULT ''"),
            ("activated_at", "TEXT DEFAULT ''"),
            ("token_version", "INTEGER NOT NULL DEFAULT 1"),
        ]:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {typedef}")
                await db.commit()
            except Exception:
                pass

        # Ensure existing user records have status and token_version populated
        try:
            await db.execute("UPDATE users SET status = 'ACTIVE' WHERE status IS NULL OR status = ''")
            await db.execute("UPDATE users SET token_version = 1 WHERE token_version IS NULL OR token_version < 1")
            await db.commit()
        except Exception:
            pass

        # Idempotently create unique index for non-empty email
        try:
            await db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email IS NOT NULL AND email != ''"
            )
            await db.commit()
        except Exception:
            pass

        # ── Password Resets table ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL
            )
        ''')
        await db.commit()

        # ── Account Security Audit Logs table ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS account_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_username TEXT,
                target_username TEXT,
                event_type TEXT NOT NULL,
                details TEXT DEFAULT '',
                ip_address TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        ''')
        await db.commit()

        # Idempotently clean up any legacy demo and synthetic test fixtures from SQLite table
        await db.execute("DELETE FROM analyses WHERE id LIKE 'demo-%' OR id LIKE 'test-%' OR id IN ('1', '2', '3')")
        await db.commit()

        # Seed default accounts for demo/presentation (idempotent)
        await seed_default_users()
    finally:
        await db.close()


async def save_analysis(data: dict):
    db = await get_db()
    try:
        await db.execute('''
            INSERT INTO analyses (id, product_name, image_filename, ocr_text, extracted_data, compliance_result, score, status, created_at, images, owner_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['id'],
            data['product_name'],
            data['image_filename'],
            data['ocr_text'],
            json.dumps(data['extracted_data']),
            json.dumps(data['compliance_result']),
            data['score'],
            data['status'],
            data['created_at'],
            json.dumps(data.get('images', [])),
            data.get('owner_user_id', '') or ''
        ))
        await db.commit()
    finally:
        await db.close()


async def get_analyses():
    """Retrieve all real user screening analyses, excluding synthetic demo fixtures."""
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM analyses WHERE id NOT LIKE 'demo-%' AND id NOT IN ('1', '2', '3') ORDER BY created_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_analysis(id: str):
    db = await get_db()
    try:
        async with db.execute('SELECT * FROM analyses WHERE id = ?', (id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await db.close()


def classify_analysis_outcome(analysis: dict) -> str:
    """
    Classify analysis outcome into 'FAILURE', 'NEEDS_REVIEW', or 'COMPLIANT'.
    Authoritative rule outcomes precedence: FAILED > REVIEW > COMPLIANT.
    Score is NEVER used to determine bucket classification.
    """
    cr = analysis.get('compliance_result')
    if isinstance(cr, str):
        try:
            cr = json.loads(cr)
        except Exception:
            cr = None

    if isinstance(cr, dict):
        checks = cr.get('checks')
        if isinstance(checks, list) and len(checks) > 0:
            has_fail = False
            has_review = False
            has_pass = False

            for c in checks:
                st = (c.get('status') if isinstance(c, dict) else getattr(c, 'status', '')) or ''
                st = str(st).upper()
                if st in ('FAIL', 'NON_COMPLIANT', 'FAILED'):
                    has_fail = True
                elif st in ('NEEDS_REVIEW', 'WARNING', 'REVIEW_REQUIRED', 'REVIEW'):
                    has_review = True
                elif st in ('PASS', 'COMPLIANT', 'PASSED'):
                    has_pass = True

            if has_fail:
                return 'FAILURE'
            if has_review:
                return 'NEEDS_REVIEW'
            if has_pass:
                return 'COMPLIANT'
        else:
            failed_count = cr.get('failed_rules')
            if failed_count is not None and failed_count > 0:
                return 'FAILURE'

            needs_review_count = (cr.get('needs_review_rules', 0) or 0) + (cr.get('warning_rules', 0) or 0)
            if needs_review_count > 0:
                return 'NEEDS_REVIEW'

            passed_count = cr.get('passed_rules', 0) or 0
            if passed_count > 0 or str(cr.get('status', '')).upper() == 'COMPLIANT':
                return 'COMPLIANT'

    status_str = str(analysis.get('status') or '').upper()
    if 'FAIL' in status_str or 'NON_COMPLIANCE' in status_str or 'NON-COMPLIANCE' in status_str:
        return 'FAILURE'
    if 'REVIEW' in status_str or 'WARNING' in status_str:
        return 'NEEDS_REVIEW'
    if 'COMPLIANT' in status_str or 'PASS' in status_str:
        return 'COMPLIANT'

    return 'NEEDS_REVIEW'


async def get_stats(user: Optional[dict] = None):
    analyses = await get_analyses()

    # Workspace/Role filtering for merchant accounts
    if user and user.get("role") == "MERCHANT_PUBLIC":
        username = (user.get("username") or "").lower()
        user_id_str = str(user.get("id", "")) if user.get("id") is not None else ""
        analyses = [
            a for a in analyses
            if a.get("owner_user_id") and (
                a.get("owner_user_id", "").lower() == username or
                (user_id_str and a.get("owner_user_id", "") == user_id_str)
            )
        ]

    packages_screened = len(analyses)
    compliant_packages = 0
    review_findings = 0
    failed_findings = 0

    for a in analyses:
        # 1. Package-level verdict
        outcome = classify_analysis_outcome(a)
        if outcome == 'COMPLIANT':
            compliant_packages += 1

        # 2. Finding-level counts (individual compliance requirements)
        cr = a.get('compliance_result')
        if isinstance(cr, str):
            try:
                cr = json.loads(cr)
            except Exception:
                cr = None

        if isinstance(cr, dict):
            checks = cr.get('checks')
            if isinstance(checks, list) and len(checks) > 0:
                for c in checks:
                    st = (c.get('status') if isinstance(c, dict) else getattr(c, 'status', '')) or ''
                    st = str(st).upper()
                    if st in ('FAIL', 'NON_COMPLIANT', 'FAILED'):
                        failed_findings += 1
                    elif st in ('NEEDS_REVIEW', 'WARNING', 'REVIEW_REQUIRED', 'REVIEW'):
                        review_findings += 1
            else:
                failed_findings += int(cr.get('failed_rules', 0) or 0)
                review_findings += int((cr.get('needs_review_rules', 0) or 0) + (cr.get('warning_rules', 0) or 0))

    avg_score = sum(a['score'] for a in analyses) / packages_screened if packages_screened > 0 else 0.0
    return {
        'total_analyzed': packages_screened,
        'packages_screened': packages_screened,
        'compliant': compliant_packages,
        'compliant_packages': compliant_packages,
        'needs_review': review_findings,
        'review_findings': review_findings,
        'failures': failed_findings,
        'failed_findings': failed_findings,
        'violations': failed_findings,
        'average_score': avg_score,
        'recent': analyses[:5]
    }


async def delete_analysis(id: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute('DELETE FROM analyses WHERE id = ?', (id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def delete_all_user_analyses() -> int:
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM analyses WHERE id NOT LIKE 'demo-%' AND id NOT IN ('1', '2', '3')")
        await db.commit()
        return cursor.rowcount
    finally:
        await db.close()


# ═══════════════════════════════════════════════════════════════════════
# USER AUTHENTICATION (role-based access)
# ═══════════════════════════════════════════════════════════════════════

async def create_user(username: str, password_hash: str, salt: str, role: str,
                      full_name: str = "", jurisdiction: str = "", email: str = "") -> bool:
    """Insert a user. Returns False if username or email already exists."""
    import datetime
    db = await get_db()
    try:
        await db.execute('''
            INSERT INTO users (username, password_hash, salt, role, full_name, jurisdiction, email, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, password_hash, salt, role, full_name, jurisdiction, email.strip().lower() if email else "",
              datetime.datetime.now().isoformat(timespec="seconds")))
        await db.commit()
        return True
    except Exception:
        return False
    finally:
        await db.close()


async def get_user_by_username(username: str):
    db = await get_db()
    try:
        async with db.execute('SELECT * FROM users WHERE username = ?', (username,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await db.close()


async def get_user_by_email(email: str):
    """Lookup user by normalized lowercase email."""
    if not email or not email.strip():
        return None
    normalized = email.strip().lower()
    db = await get_db()
    try:
        async with db.execute('SELECT * FROM users WHERE LOWER(email) = ? AND email != ""', (normalized,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await db.close()


async def get_user_by_identifier(identifier: str):
    """Lookup user by username OR recovery email."""
    if not identifier or not identifier.strip():
        return None
    raw = identifier.strip()
    normalized = raw.lower()
    db = await get_db()
    try:
        # First check username exact/case-insensitive
        async with db.execute('SELECT * FROM users WHERE LOWER(username) = ?', (normalized,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        # Then check email
        async with db.execute('SELECT * FROM users WHERE LOWER(email) = ? AND email != ""', (normalized,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        return None
    finally:
        await db.close()


async def list_users(role: str | None = None):
    db = await get_db()
    try:
        if role:
            async with db.execute('SELECT * FROM users WHERE role = ? ORDER BY id', (role,)) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute('SELECT * FROM users ORDER BY id') as cursor:
                rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()

async def update_user(username: str, full_name: str = None, jurisdiction: str = None,
                      role: str = None, password_hash: str = None, salt: str = None,
                      email: str = None) -> bool:
    """Update user by username. Only set columns that are not None. Returns True if affected."""
    fields = []
    params = []
    if full_name is not None:
        fields.append("full_name = ?")
        params.append(full_name)
    if jurisdiction is not None:
        fields.append("jurisdiction = ?")
        params.append(jurisdiction)
    if role is not None:
        fields.append("role = ?")
        params.append(role)
    if password_hash is not None:
        fields.append("password_hash = ?")
        params.append(password_hash)
    if salt is not None:
        fields.append("salt = ?")
        params.append(salt)
    if email is not None:
        fields.append("email = ?")
        params.append(email.strip().lower() if email else "")

    if not fields:
        return False

    params.append(username)
    db = await get_db()
    try:
        cursor = await db.execute(
            f"UPDATE users SET {', '.join(fields)} WHERE username = ?",
            params
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def create_invited_user(username: str, email: str, role: str, full_name: str = "",
                              jurisdiction: str = "", token_hash: str = "", expires_at: str = "") -> bool:
    """Insert a provisioned user in INVITED status."""
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        await db.execute('''
            INSERT INTO users (
                username, password_hash, salt, role, full_name, jurisdiction, email,
                status, invitation_token_hash, invitation_expires_at, invited_at, token_version, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            username.strip(),
            "",  # Unset password until activation
            "",
            role,
            full_name.strip(),
            jurisdiction.strip(),
            email.strip().lower() if email else "",
            "INVITED",
            token_hash,
            expires_at,
            now_iso,
            1,
            now_iso
        ))
        await db.commit()
        return True
    except Exception:
        return False
    finally:
        await db.close()


async def get_valid_invitation(token_hash: str):
    """Lookup user by invitation token hash if status is INVITED and token is unexpired."""
    import datetime
    if not token_hash:
        return None
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM users WHERE invitation_token_hash = ? AND status = 'INVITED' AND invitation_expires_at > ?",
            (token_hash, now_iso)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await db.close()


async def activate_user_account(username: str, password_hash: str, salt: str) -> bool:
    """Activate user account: set password, status=ACTIVE, clear token hash, increment token_version."""
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        cursor = await db.execute('''
            UPDATE users
            SET password_hash = ?, salt = ?, status = 'ACTIVE', activated_at = ?,
                invitation_token_hash = '', invitation_expires_at = '',
                token_version = token_version + 1
            WHERE username = ? AND status = 'INVITED'
        ''', (password_hash, salt, now_iso, username))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def resend_invitation_record(username: str, token_hash: str, expires_at: str) -> bool:
    """Update invitation token hash and expiration for an INVITED account."""
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        cursor = await db.execute('''
            UPDATE users
            SET invitation_token_hash = ?, invitation_expires_at = ?, invited_at = ?
            WHERE username = ? AND status = 'INVITED'
        ''', (token_hash, expires_at, now_iso, username))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def suspend_user(username: str) -> bool:
    """Suspend user account and increment token_version to invalidate active sessions."""
    db = await get_db()
    try:
        cursor = await db.execute('''
            UPDATE users
            SET status = 'SUSPENDED', token_version = token_version + 1
            WHERE username = ?
        ''', (username,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def reactivate_user(username: str) -> bool:
    """Reactivate suspended account."""
    db = await get_db()
    try:
        cursor = await db.execute('''
            UPDATE users
            SET status = 'ACTIVE', token_version = token_version + 1
            WHERE username = ? AND status = 'SUSPENDED'
        ''', (username,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def change_user_role(username: str, new_role: str) -> bool:
    """Change user role and increment token_version to immediately revoke stale permissions."""
    db = await get_db()
    try:
        cursor = await db.execute('''
            UPDATE users
            SET role = ?, token_version = token_version + 1
            WHERE username = ?
        ''', (new_role, username))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def revoke_invitation(username: str) -> bool:
    """Revoke/delete an account that is currently in INVITED status."""
    db = await get_db()
    try:
        cursor = await db.execute('''
            DELETE FROM users
            WHERE username = ? AND status = 'INVITED'
        ''', (username,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def log_account_audit_event(actor_username: str, target_username: str, event_type: str,
                                 details: str = "", ip_address: str = "") -> bool:
    """Record security-sensitive account provisioning or lifecycle event."""
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        await db.execute('''
            INSERT INTO account_audit_logs (actor_username, target_username, event_type, details, ip_address, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (actor_username, target_username, event_type, details, ip_address, now_iso))
        await db.commit()
        return True
    except Exception:
        return False
    finally:
        await db.close()


async def get_account_audit_logs(limit: int = 50):
    """Retrieve newest account security audit logs."""
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM account_audit_logs ORDER BY id DESC LIMIT ?",
            (int(limit),)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        await db.close()


async def delete_user(username: str) -> bool:
    """Delete user by username. Returns True if a row was affected."""
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM users WHERE username = ?", (username,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def seed_default_users():
    """Create operational demo accounts on first run (idempotent, demo mode only):
       officer / officer123 (ENFORCEMENT_OFFICER)
       audit / audit123   (AUDIT_OFFICER)
       merchant / merchant123 (MERCHANT_PUBLIC)

       NOTE: Admin accounts are NEVER seeded automatically. System administrators
       must be provisioned explicitly via CLI bootstrap (bootstrap_admin.py).
    """
    is_prod = (
        os.environ.get("METRCHECK_ENV") == "production" 
        or os.environ.get("ENVIRONMENT") == "production"
        or getattr(settings, "ENVIRONMENT", "") == "production"
    )
    is_demo_explicit = (
        getattr(settings, "METRCHECK_DEMO_MODE", False) is True
        and os.environ.get("METRCHECK_DEMO_MODE", "true").lower() in ("true", "1")
    )
    if is_prod or not is_demo_explicit:
        return

    from auth.security import hash_password, ROLE_ENFORCEMENT, ROLE_AUDIT, ROLE_MERCHANT

    defaults = [
        ("officer", "officer123", ROLE_ENFORCEMENT, "Demo Enforcement Officer", "Consumer Affairs & Legal Metrology Directorate"),
        ("audit", "audit123", ROLE_AUDIT, "Demo Audit Inspector", "Quality & Compliance Verification Directorate"),
        ("merchant", "merchant123", ROLE_MERCHANT, "Demo Merchant Brand", "Commercial Packager"),
    ]
    for username, password, role, full_name, jurisdiction in defaults:
        existing = await get_user_by_username(username)
        if existing:
            continue
        pw_hash, salt = hash_password(password)
        await create_user(username, pw_hash, salt, role, full_name, jurisdiction)


# ═══════════════════════════════════════════════════════════════════════
# PASSWORD RESETS
# ═══════════════════════════════════════════════════════════════════════

async def create_password_reset_record(username: str, token_hash: str, expires_at: str) -> bool:
    """Store a new password reset token hash and invalidate previous unused tokens for the user."""
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        # Invalidate existing unused tokens for this user
        await db.execute(
            "UPDATE password_resets SET used_at = ? WHERE username = ? AND used_at IS NULL",
            (now_iso, username)
        )
        # Insert new reset token
        await db.execute('''
            INSERT INTO password_resets (username, token_hash, expires_at, created_at)
            VALUES (?, ?, ?, ?)
        ''', (username, token_hash, expires_at, now_iso))
        await db.commit()
        return True
    except Exception:
        return False
    finally:
        await db.close()


async def get_valid_password_reset(token_hash: str):
    """Retrieve password reset record if it exists, is unused, and not expired."""
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM password_resets WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
            (token_hash, now_iso)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await db.close()


async def apply_password_reset(username: str, reset_id: int, new_pw_hash: str, new_salt: str) -> bool:
    """Atomically update user password hash/salt and mark the reset token as used."""
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        # Update user password
        cursor = await db.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE username = ?",
            (new_pw_hash, new_salt, username)
        )
        if cursor.rowcount == 0:
            await db.rollback()
            return False

        # Mark reset token used
        await db.execute(
            "UPDATE password_resets SET used_at = ? WHERE id = ?",
            (now_iso, reset_id)
        )
        await db.commit()
        return True
    except Exception:
        await db.rollback()
        return False
    finally:
        await db.close()


# ═══════════════════════════════════════════════════════════════════════
# SEARCH + TRENDS (for retrieval facility & dashboard)
# ═══════════════════════════════════════════════════════════════════════

async def search_analyses(query: str = "", status: str = "", limit: int = 50):
    """Case-insensitive search over product name / product id / extracted data.
    Returns newest-first, excluding synthetic demo fixtures."""
    db = await get_db()
    try:
        sql = "SELECT * FROM analyses WHERE id NOT LIKE 'demo-%' AND id NOT IN ('1','2','3')"
        params: list = []
        q = (query or "").strip()
        if q:
            sql += " AND (LOWER(product_name) LIKE ? OR LOWER(id) LIKE ? OR LOWER(extracted_data) LIKE ?)"
            like = f"%{q.lower()}%"
            params += [like, like, like]
        if status and status.upper() != "ALL":
            sql += " AND UPPER(status) LIKE ?"
            params.append(f"%{status.upper()}%")
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(int(limit))
        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_trend_stats(days: int = 14):
    """Daily counts (total / compliant / violations) over the last N days."""
    import datetime
    db = await get_db()
    try:
        since = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
        async with db.execute(
            "SELECT date(created_at) AS d, "
            "COUNT(*) AS total, "
            "SUM(CASE WHEN status = 'COMPLIANT' THEN 1 ELSE 0 END) AS compliant "
            "FROM analyses "
            "WHERE id NOT LIKE 'demo-%' AND id NOT IN ('1','2','3') AND created_at >= ? "
            "GROUP BY d ORDER BY d",
            (since,),
        ) as cursor:
            rows = await cursor.fetchall()

        by_date = {dict(r)["d"]: dict(r) for r in rows if dict(r)["d"]}
        labels, totals, compliants, violations = [], [], [], []
        for i in range(days - 1, -1, -1):
            day = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
            r = by_date.get(day, {})
            t = r.get("total") or 0
            c = r.get("compliant") or 0
            labels.append(day[5:])       # MM-DD
            totals.append(t)
            compliants.append(c)
            violations.append(t - c)
        return {"labels": labels, "total": totals, "compliant": compliants, "violations": violations}
    finally:
        await db.close()

