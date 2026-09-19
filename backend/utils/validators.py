import os
import re
from typing import Optional, Set
from fastapi import UploadFile, HTTPException
from config import settings

ALLOWED_IMAGE_EXTENSIONS: Set[str] = {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif'}
ALLOWED_DOCUMENT_EXTENSIONS: Set[str] = ALLOWED_IMAGE_EXTENSIONS.union({'.pdf'})
MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024


def sanitize_filename(filename: Optional[str]) -> str:
    """
    Sanitizes user-provided filename:
    - Removes path separators (directory traversal prevention)
    - Strips null bytes and control characters
    - Keeps only safe alphanumeric characters, dashes, underscores, and dots.
    """
    if not filename:
        return "unnamed_upload.jpg"
    
    # Strip directory components
    base = os.path.basename(filename).strip()
    
    # Remove null bytes and path traversal patterns
    base = base.replace('\x00', '').replace('..', '')
    
    # Regex sanitize: replace disallowed characters with underscore
    clean = re.sub(r'[^a-zA-Z0-9._-]', '_', base)
    
    # Ensure not empty or dot-only
    if not clean or clean.strip('.') == '':
        return "sanitized_upload.jpg"
    return clean[:120]


def check_magic_bytes(header: bytes, expected_mime: Optional[str] = None):
    """
    Inspects leading bytes to determine true file format by file signature.
    If expected_mime is provided, returns bool (True if magic bytes match expected mime).
    If expected_mime is None, returns format string ("JPEG", "PNG", "WEBP", "PDF", "TIFF") or None.
    """
    if not header or len(header) < 4:
        return False if expected_mime else None

    detected = None
    if header.startswith(b'\xff\xd8\xff'):
        detected = "JPEG"
    elif header.startswith(b'\x89PNG\r\n\x1a\n') or header.startswith(b'\x89PNG'):
        detected = "PNG"
    elif header.startswith(b'RIFF') and len(header) >= 12 and header[8:12] == b'WEBP':
        detected = "WEBP"
    elif header.startswith(b'%PDF'):
        detected = "PDF"
    elif header.startswith(b'II*\x00') or header.startswith(b'MM\x00*'):
        detected = "TIFF"

    if expected_mime:
        mime_map = {
            "image/jpeg": "JPEG",
            "image/jpg": "JPEG",
            "image/png": "PNG",
            "image/webp": "WEBP",
            "application/pdf": "PDF",
            "image/tiff": "TIFF",
        }
        exp_fmt = mime_map.get(expected_mime.lower())
        return detected is not None and exp_fmt is not None and detected == exp_fmt

    return detected


def validate_image_file(file: UploadFile, allow_pdf: bool = False):
    """
    Performs comprehensive pre-processing validation on an uploaded file:
    1. Filename path traversal detection
    2. Extension allowlist check
    3. File size check (header-based if present)
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename in upload.")

    raw_filename = file.filename
    if ".." in raw_filename or raw_filename.startswith(("/", "\\")):
        raise HTTPException(status_code=400, detail="Path traversal pattern detected in filename.")

    ext = os.path.splitext(raw_filename)[1].lower()
    allowed = ALLOWED_DOCUMENT_EXTENSIONS if allow_pdf else ALLOWED_IMAGE_EXTENSIONS
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"File extension '{ext}' not allowed. Allowed extensions: {sorted(list(allowed))}"
        )

    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum allowed limit of {settings.MAX_FILE_SIZE_MB}MB."
        )
