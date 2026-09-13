import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database.db import init_db
from api import analyze, ocr, extract, compliance_routes, history, demo, health, report, enforcement, integrations
from auth.routes import router as auth_router, admin_router

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown

app = FastAPI(title="MetrCheck AI API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.include_router(analyze.router, prefix="/api", tags=["Analyze"])
app.include_router(ocr.router, prefix="/api", tags=["OCR"])
app.include_router(extract.router, prefix="/api", tags=["Extract"])
app.include_router(compliance_routes.router, prefix="/api", tags=["Compliance"])
app.include_router(history.router, prefix="/api", tags=["History"])
app.include_router(demo.router, prefix="/api", tags=["Demo"])
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(report.router, prefix="/api", tags=["Report"])
app.include_router(auth_router, prefix="/api", tags=["Auth"])
app.include_router(admin_router, prefix="/api", tags=["Admin"])
app.include_router(enforcement.router, prefix="/api", tags=["Enforcement"])
app.include_router(integrations.router, prefix="/api", tags=["Integrations & Metrology"])

@app.get("/")
def read_root():
    return {"message": "Welcome to MetrCheck AI API", "docs": "/docs"}
