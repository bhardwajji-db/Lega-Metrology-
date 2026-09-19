from datetime import datetime, timezone
from fastapi import APIRouter
from ocr.factory import get_ocr_engine
from database.db import get_db

router = APIRouter()

@router.get("/health")
async def health_check():
    """
    Real-time system health and service operational check.
    Performs real queries against SQLite database and inspects OCR engine state.
    Exposes zero secrets, credentials, internal paths, or tokens.
    """
    # 1. Check OCR Engine state
    ocr_engine = get_ocr_engine()
    ocr_ok = bool(ocr_engine and ocr_engine.is_available())
    ocr_service_status = "operational" if ocr_ok else "degraded"

    # 2. Check Database connectivity via real query
    db_ok = False
    try:
        db = await get_db()
        cursor = await db.execute("SELECT 1")
        row = await cursor.fetchone()
        db_ok = bool(row and row[0] == 1)
    except Exception:
        db_ok = False
    db_service_status = "operational" if db_ok else "unavailable"

    # 3. Derive aggregate health state
    if db_ok and ocr_ok:
        overall_status = "operational"
    elif db_ok or ocr_ok:
        overall_status = "degraded"
    else:
        overall_status = "offline"

    return {
        "status": overall_status,
        "services": {
            "backend": "operational",
            "database": db_service_status,
            "ocr": ocr_service_status,
        },
        "ocr_available": ocr_ok,
        "ocr_engine": ocr_engine.__class__.__name__ if ocr_engine else "Unavailable",
        "database": "connected" if db_ok else "unavailable",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.4.0"
    }
