import os
from fastapi import UploadFile, HTTPException
from config import settings

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024

def validate_image_file(file: UploadFile):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File extension {ext} not allowed. Supported: {ALLOWED_EXTENSIONS}")
        
    # We can't easily check file size before reading without seeking, 
    # but we can rely on FastAPI's underlying mechanisms or check content length if provided
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max size is {settings.MAX_FILE_SIZE_MB}MB")
