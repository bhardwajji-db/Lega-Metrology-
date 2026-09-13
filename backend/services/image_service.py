import os
import aiofiles
from PIL import Image, UnidentifiedImageError
from fastapi import UploadFile, HTTPException
from config import settings

MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024


async def process_and_save_image(file: UploadFile, dest_path: str):
    """
    Reads, validates, sanitizes, and stores the uploaded image file.
    Enforces server-side size limits, non-empty content, and valid image headers.
    """
    # 1. Read file content safely
    content = await file.read()
    if not content or len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail=f"Uploaded file '{file.filename}' is empty (0 bytes)."
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File '{file.filename}' exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB."
        )

    # 2. Save raw content to destination
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    async with aiofiles.open(dest_path, 'wb') as out_file:
        await out_file.write(content)

    # 3. Validate image integrity and sanitize dimensions/color channels
    try:
        with Image.open(dest_path) as img:
            # Force decode of image data to detect corrupt files early
            img.verify()

        # Reopen after verify() (verify invalidates image object)
        with Image.open(dest_path) as img:
            # Convert palette/transparency to RGB
            if img.mode in ('RGBA', 'P', 'LA', 'L', 'CMYK'):
                img = img.convert('RGB')

            # Resize if longest side > 1800px (optimal for fast crisp OCR)
            max_size = 1800
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            img.save(dest_path, format="JPEG", quality=95)

    except (UnidentifiedImageError, OSError, ValueError) as err:
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except Exception:
                pass
        raise HTTPException(
            status_code=400,
            detail=f"Uploaded file '{file.filename}' is not a valid or readable image: {str(err)}"
        )

