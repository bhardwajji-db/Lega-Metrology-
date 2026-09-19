"""
MetrCheck AI — Authenticated & Authorized File Access Endpoint (SEC-01 Fix).

Replaces public /uploads static mount with role-guarded and ownership-checked file serving.
Enforces:
1. User Authentication (via Bearer token or query parameter ?token=...)
2. Filename validation & Path traversal prevention (ensure_path_contained)
3. Safe 404 on missing files (no internal filesystem leakage)
4. Role & Ownership based authorization (IDOR protection for Merchant users; Admin/Officer access)
5. Proper MIME Content-Type headers for images and PDF artworks
"""

import os
import mimetypes
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from config import settings
from auth.security import (
    get_current_user,
    check_tenant_access,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
)
from database.db import get_db, log_security_event
from services.image_service import ensure_path_contained

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Images"])


def _user_owns_record(user: dict, owner_user_id: Optional[str]) -> bool:
    """Check if the authenticated user matches the owner_user_id (username or user id)."""
    if not owner_user_id:
        return True
    username = user.get("username") or ""
    uid = str(user.get("id", "")) if user.get("id") is not None else ""
    return owner_user_id == username or (bool(uid) and owner_user_id == uid)


@router.get("/images/{filename}")
async def get_secure_file(
    filename: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Secure, authenticated file retrieval endpoint for uploaded product images and artworks.
    Guarantees strict containment within UPLOAD_DIR and verifies resource ownership and tenant isolation.
    """
    # ── Step 1 & 2: Filename validation and Path traversal check ──
    if not filename or ".." in filename or "/" in filename or "\\" in filename or "\x00" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename format or directory traversal attempt."
        )

    # ── Step 3: Strict directory containment verification ──
    target_path = os.path.abspath(os.path.join(settings.UPLOAD_DIR, filename))
    ensure_path_contained(target_path, settings.UPLOAD_DIR)

    # ── Step 4: Verify file existence ──
    if not os.path.exists(target_path) or not os.path.isfile(target_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested file not found."
        )

    # ── Step 5: Authorize Access (Role, Ownership & Tenant Isolation) ──
    user_role = current_user.get("role", ROLE_MERCHANT)
    username = current_user.get("username", "")

    # Admin has statutory oversight
    if user_role != ROLE_ADMIN:
        is_authorized = False
        db = await get_db()
        try:
            # 1. Search in analyses table
            cursor = await db.execute(
                """
                SELECT id, owner_user_id, organization_id, image_filename, images
                FROM analyses
                WHERE image_filename = ?
                   OR images LIKE ?
                   OR id = ?
                   OR ? LIKE id || '%'
                """,
                (filename, f'%{filename}%', filename, filename)
            )
            analysis_rows = await cursor.fetchall()

            for row in analysis_rows:
                row_dict = dict(row)
                if check_tenant_access(current_user, row_dict):
                    is_authorized = True
                    break

            # 2. If not yet authorized, search in artworks table (Pre-print artworks & page previews)
            if not is_authorized:
                cursor = await db.execute(
                    """
                    SELECT id, owner_user_id, organization_id, file_path, filename, pages_data
                    FROM artworks
                    WHERE file_path LIKE ?
                       OR filename = ?
                       OR pages_data LIKE ?
                       OR id = ?
                       OR ? LIKE id || '%'
                       OR ? LIKE 'preprint_' || id || '%'
                    """,
                    (f"%{filename}", filename, f"%{filename}%", filename, filename, filename)
                )
                artwork_rows = await cursor.fetchall()

                for row in artwork_rows:
                    row_dict = dict(row)
                    if check_tenant_access(current_user, row_dict):
                        is_authorized = True
                        break

            # If access is not authorized via linked analysis or artwork records
            if not is_authorized:
                client_ip = request.client.host if request.client else ""
                try:
                    await log_security_event(
                        event_type="UNAUTHORIZED_FILE_ACCESS",
                        actor_username=username,
                        ip_address=client_ip,
                        resource_id=filename,
                        details=f"User '{username}' attempted unauthorized access to file '{filename}' (cross-tenant or unlinked orphan)."
                    )
                except Exception as log_err:
                    logger.warning(f"Failed to record security audit log: {log_err}")

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. You do not have permission to access this file."
                )

        finally:
            await db.close()

    # ── Step 6: Determine MIME Content-Type & Serve File ──
    ext = os.path.splitext(filename)[1].lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".pdf": "application/pdf",
    }
    media_type = mime_map.get(ext) or mimetypes.guess_type(target_path)[0] or "application/octet-stream"

    return FileResponse(
        target_path,
        media_type=media_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600",
        }
    )
