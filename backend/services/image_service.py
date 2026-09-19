import os
import io
import aiofiles
from PIL import Image, UnidentifiedImageError
from fastapi import UploadFile, HTTPException
from config import settings
from utils.validators import check_magic_bytes, sanitize_filename

# Protect against decompression bombs / huge pixel attacks
Image.MAX_IMAGE_PIXELS = 50_000_000  # 50 Megapixels max
MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024
MAX_IMAGE_DIMENSION = 10_000  # 10k pixels max width or height


def ensure_path_contained(target_path: str, base_dir: str = settings.UPLOAD_DIR) -> str:
    """
    Asserts that the resolved absolute target_path is strictly within base_dir.
    Raises HTTPException(400) if path traversal is attempted.
    """
    abs_base = os.path.abspath(base_dir)
    abs_target = os.path.abspath(target_path)
    if not abs_target.startswith(abs_base):
        raise HTTPException(
            status_code=400,
            detail="Security violation: Target file path attempts directory traversal."
        )
    return abs_target


async def process_and_save_image(file: UploadFile, dest_path: str):
    """
    Reads, validates, sanitizes, and stores the uploaded image file.
    Security controls:
    1. Size limit enforcement
    2. In-memory magic byte / file signature validation
    3. Strict directory containment verification
    4. Decompression bomb and dimension bounds checking
    5. PIL pixel verification and RGB conversion
    6. Safe temporary file cleanup without leaking filesystem paths
    """
    # 1. Path containment check
    contained_dest = ensure_path_contained(dest_path, settings.UPLOAD_DIR)

    # 2. Read file content safely into memory
    content = await file.read()
    if not content or len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail=f"Uploaded file '{sanitize_filename(file.filename)}' is empty (0 bytes)."
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB."
        )

    # 3. In-memory magic byte / signature check
    magic_format = check_magic_bytes(content[:32])
    if not magic_format or magic_format not in ("JPEG", "PNG", "WEBP", "TIFF"):
        raise HTTPException(
            status_code=400,
            detail="Invalid image signature. Uploaded file is corrupted or not a valid or readable image (supported: JPEG, PNG, WEBP, TIFF)."
        )

    # 4. Save raw content to validated destination
    os.makedirs(os.path.dirname(contained_dest), exist_ok=True)
    async with aiofiles.open(contained_dest, 'wb') as out_file:
        await out_file.write(content)

    # 5. Validate image integrity, bounds, and sanitize channels
    try:
        with Image.open(contained_dest) as img:
            # Force decode of image data to detect corrupt files or invalid streams early
            img.verify()

        # Reopen after verify() (verify invalidates image object)
        with Image.open(contained_dest) as img:
            # Dimension bounds check
            if img.width > MAX_IMAGE_DIMENSION or img.height > MAX_IMAGE_DIMENSION:
                raise ValueError(f"Image dimensions ({img.width}x{img.height}) exceed maximum allowed {MAX_IMAGE_DIMENSION}px.")

            # Convert palette/transparency to RGB
            if img.mode in ('RGBA', 'P', 'LA', 'L', 'CMYK'):
                img = img.convert('RGB')

            # Resize if longest side > 1800px (optimal for fast crisp OCR)
            max_size = 1800
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            img.save(contained_dest, format="JPEG", quality=95)

    except (UnidentifiedImageError, OSError, ValueError) as err:
        if os.path.exists(contained_dest):
            try:
                os.remove(contained_dest)
            except Exception:
                pass
        # Sanitize error detail to not leak local paths
        err_msg = str(err).split(":")[-1].strip() if ":" in str(err) else str(err)
        raise HTTPException(
            status_code=400,
            detail=f"Uploaded image could not be processed safely: {err_msg}"
        )
