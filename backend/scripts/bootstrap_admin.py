#!/usr/bin/env python3
"""
MetrCheck AI — Admin Bootstrap & Provisioning CLI Script

Safely provisions or restores the primary System Administrator (ADMIN) account
without exposing passwords in logs, without public endpoints, and without affecting
existing merchant accounts or analysis history.
"""

import os
import sys
import argparse
import getpass
import asyncio

# Ensure backend root is on sys.path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from config import settings
from database.db import (
    get_db,
    init_db,
    get_user_by_username,
    get_user_by_email,
    create_user,
    update_user,
    log_account_audit_event,
)
from auth.security import hash_password, ROLE_ADMIN


async def bootstrap_admin(
    username: str,
    password: str,
    email: str = "",
    full_name: str = "System Administrator",
    jurisdiction: str = "DoCA Legal Metrology Directorate",
    overwrite: bool = False,
) -> bool:
    """Idempotently bootstrap or restore the ADMIN account."""
    if not username or not username.strip():
        print("[!] Error: Admin username cannot be empty.", file=sys.stderr)
        return False

    username = username.strip()

    # Safety constraint: Do not allow bootstrapping over protected merchant accounts
    if username.lower() == "omsainikaul":
        print("[!] SAFETY ERROR: Cannot bootstrap admin account over protected merchant 'omsainikaul'!", file=sys.stderr)
        return False

    if not password or len(password) < 8:
        print("[!] Error: Admin password must be at least 8 characters long.", file=sys.stderr)
        return False

    email = email.strip().lower() if email else ""

    # Ensure DB schema is initialized
    await init_db()

    # Check for existing user with this username
    existing_user = await get_user_by_username(username)

    if existing_user:
        if existing_user.get("role") != ROLE_ADMIN:
            print(f"[!] SAFETY ERROR: User '{username}' exists with role '{existing_user.get('role')}'. Cannot overwrite non-admin account.", file=sys.stderr)
            return False

        if not overwrite:
            print(f"[*] Admin user '{username}' already exists. Use --overwrite to reset credentials.")
            return True

        # Overwrite existing admin credentials safely
        pw_hash, salt = hash_password(password)
        db = await get_db()
        try:
            await db.execute('''
                UPDATE users
                SET password_hash = ?, salt = ?, email = ?, full_name = ?, jurisdiction = ?,
                    status = 'ACTIVE', token_version = token_version + 1
                WHERE username = ? AND role = ?
            ''', (pw_hash, salt, email, full_name, jurisdiction, username, ROLE_ADMIN))
            await db.commit()
        finally:
            await db.close()

        await log_account_audit_event(
            actor_username="SYSTEM_CLI",
            target_username=username,
            event_type="ADMIN_PASSWORD_RESET",
            details="Admin account credentials updated via CLI bootstrap",
            ip_address="127.0.0.1",
        )
        print(f"[+] Successfully updated credentials for existing ADMIN account: @{username}")
        return True

    # If email provided, verify no collision with another user
    if email:
        email_user = await get_user_by_email(email)
        if email_user and email_user.get("username") != username:
            print(f"[!] Error: Email '{email}' is already registered to user '@{email_user.get('username')}'.", file=sys.stderr)
            return False

    # Create new admin account
    pw_hash, salt = hash_password(password)
    created = await create_user(
        username=username,
        password_hash=pw_hash,
        salt=salt,
        role=ROLE_ADMIN,
        full_name=full_name,
        jurisdiction=jurisdiction,
        email=email,
    )

    if not created:
        print(f"[!] Error: Failed to create admin user '{username}'.", file=sys.stderr)
        return False

    # Ensure status is ACTIVE and token_version is 1
    db = await get_db()
    try:
        await db.execute("UPDATE users SET status = 'ACTIVE', token_version = 1 WHERE username = ?", (username,))
        await db.commit()
    finally:
        await db.close()

    await log_account_audit_event(
        actor_username="SYSTEM_CLI",
        target_username=username,
        event_type="ADMIN_BOOTSTRAPPED",
        details="Initial system administrator account provisioned via CLI bootstrap",
        ip_address="127.0.0.1",
    )

    print(f"[+] Successfully provisioned ADMIN account: @{username} (Role: {ROLE_ADMIN})")
    if email:
        print(f"    - Recovery Email: {email}")
    return True


def parse_args():
    parser = argparse.ArgumentParser(
        description="Bootstrap or restore the MetrCheck AI System Administrator account."
    )
    parser.add_argument(
        "--username",
        "-u",
        default=os.environ.get("METRCHECK_ADMIN_USERNAME", "admin"),
        help="Admin username (default: 'admin' or $METRCHECK_ADMIN_USERNAME)",
    )
    parser.add_argument(
        "--password",
        "-p",
        default=os.environ.get("METRCHECK_ADMIN_PASSWORD", ""),
        help="Admin password (min 8 chars; if omitted, prompts interactively or uses $METRCHECK_ADMIN_PASSWORD)",
    )
    parser.add_argument(
        "--email",
        "-e",
        default=os.environ.get("METRCHECK_ADMIN_EMAIL", ""),
        help="Admin recovery email address",
    )
    parser.add_argument(
        "--full-name",
        default="System Administrator",
        help="Display name for administrator",
    )
    parser.add_argument(
        "--jurisdiction",
        default="DoCA Legal Metrology Directorate",
        help="Administrative jurisdiction/organization",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow resetting credentials if the admin account already exists",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    password = args.password
    if not password:
        # Prompt interactively if in a terminal
        if sys.stdin.isatty():
            password = getpass.getpass(f"Enter password for Admin '@{args.username}' (min 8 chars): ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("[!] Error: Passwords do not match.", file=sys.stderr)
                sys.exit(1)
        else:
            print("[!] Error: Password required via --password, $METRCHECK_ADMIN_PASSWORD, or interactive prompt.", file=sys.stderr)
            sys.exit(1)

    success = asyncio.run(
        bootstrap_admin(
            username=args.username,
            password=password,
            email=args.email,
            full_name=args.full_name,
            jurisdiction=args.jurisdiction,
            overwrite=args.overwrite,
        )
    )
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
