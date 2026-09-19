import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from database.db import init_db, get_security_audit_logs, verify_security_audit_chain
from api import analyze, ocr, extract, compliance_routes, history, demo, health, report, enforcement, integrations, vision, barcode, images
from api import evidence, scoring_routes, preprint_routes, version_routes, review_routes, claims_routes, listing_routes
from auth.routes import router as auth_router, admin_router
from auth.security import require_roles, ROLE_ADMIN
from fastapi import Request, Response, Depends, Query

try:
    from version import get_version_metadata
    _has_version_module = True
except ImportError:
    _has_version_module = False

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

logger = logging.getLogger(__name__)

async def _warmup_ocr():
    """Pre-warm OCR predictor in background thread so user requests experience 0 cold-start delay."""
    try:
        from ocr.factory import get_ocr_engine
        engine = get_ocr_engine()
        sample_path = os.path.join(os.path.dirname(__file__), "fixtures", "temp_1.4.png")
        if os.path.exists(sample_path):
            await engine.extract(sample_path)
            logger.info("[OCR] Startup pre-warmup completed successfully.")
    except Exception as e:
        logger.debug(f"[OCR] Startup pre-warmup skipped: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup validation
    settings.verify_test_isolation()
    settings.validate_production_secrets()
    os.makedirs(os.path.abspath(settings.UPLOAD_DIR), exist_ok=True)
    await init_db()
    import asyncio
    asyncio.create_task(_warmup_ocr())
    yield
    # Shutdown

app = FastAPI(title="MetrCheck AI API", version="2.4.0", lifespan=lifespan)

# ── Security Headers Middleware (Section 15) ──
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(self), microphone=()"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(images.router, prefix="/api", tags=["Images"])

app.include_router(analyze.router, prefix="/api", tags=["Analyze"])
app.include_router(ocr.router, prefix="/api", tags=["OCR"])
app.include_router(extract.router, prefix="/api", tags=["Extract"])
app.include_router(compliance_routes.router, prefix="/api", tags=["Compliance"])
app.include_router(evidence.router)
app.include_router(history.router, prefix="/api", tags=["History"])
app.include_router(demo.router, prefix="/api", tags=["Demo"])
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(report.router, prefix="/api", tags=["Report"])
app.include_router(auth_router, prefix="/api", tags=["Auth"])
app.include_router(admin_router, prefix="/api", tags=["Admin"])
app.include_router(enforcement.router, prefix="/api", tags=["Enforcement"])
app.include_router(integrations.router, prefix="/api", tags=["Integrations & Metrology"])
app.include_router(vision.router)
app.include_router(barcode.router, prefix="/api")
app.include_router(scoring_routes.router)
app.include_router(preprint_routes.router)
app.include_router(version_routes.router)
app.include_router(review_routes.router)
app.include_router(claims_routes.router, prefix="/api")
app.include_router(listing_routes.router)

@app.get("/api/version", tags=["System Version"])
def get_system_version():
    """Returns canonical system, OCR pipeline, rule engine, and integrity hashing versions."""
    if _has_version_module:
        return get_version_metadata()
    return {"version": "2.4.0", "api": "MetrCheck AI"}

@app.get("/api/admin/security-logs", tags=["Admin Governance"])
async def list_security_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    event_type: str = Query(default=""),
    user: dict = Depends(require_roles(ROLE_ADMIN))
):
    """Retrieve immutable security audit logs with cryptographic hash blocks (Admin only)."""
    return await get_security_audit_logs(limit=limit, event_type=event_type)

@app.get("/api/admin/security-logs/verify-chain", tags=["Admin Governance"])
async def verify_audit_chain_endpoint(
    user: dict = Depends(require_roles(ROLE_ADMIN))
):
    """Verifies the complete cryptographic SHA-256 hash chain of security audit logs (Admin only)."""
    return await verify_security_audit_chain()

@app.get("/health")
async def root_health():
    """Root-level health check (convenience alias for /api/health)."""
    return {"status": "ok", "service": "metrcheck-api", "version": "2.4.0"}

# Mount frontend web application if dist directory exists (single-service web deployment)
_FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
_ASSETS_DIR = os.path.join(_FRONTEND_DIST, "assets")

if os.path.isdir(_ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=_ASSETS_DIR), name="frontend_assets")

@app.get("/")
def read_root():
    index_file = os.path.join(_FRONTEND_DIST, "index.html")
    if os.path.isfile(index_file):
        return FileResponse(index_file)
    return {"message": "Welcome to MetrCheck AI API", "docs": "/docs"}

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # Guard API, Docs, OpenAPI, and Upload paths from falling through to HTML
    if (
        full_path.startswith("api")
        or full_path.startswith("uploads")
        or full_path.startswith("docs")
        or full_path.startswith("redoc")
        or full_path.startswith("openapi.json")
    ):
        raise HTTPException(status_code=404, detail="Not Found")

    # Static asset in frontend/dist root (e.g., favicon.svg, icons.svg)
    file_path = os.path.join(_FRONTEND_DIST, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    # Missing static assets or file paths with extensions should return 404, not HTML
    base_name = os.path.basename(full_path)
    if "." in base_name and not base_name.endswith((".html", ".htm")):
        raise HTTPException(status_code=404, detail="Not Found")

    # Client-side SPA routing fallback (React Router: /login, /dashboard, /history, /admin, etc.)
    index_file = os.path.join(_FRONTEND_DIST, "index.html")
    if os.path.isfile(index_file):
        return FileResponse(index_file)

    return {"message": "Welcome to MetrCheck AI API", "docs": "/docs"}
