import os
from pydantic_settings import BaseSettings
from pydantic import field_validator

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROD_DATABASE_PATH = os.path.abspath(os.path.join(_BACKEND_DIR, 'metrc_check.db'))
PROD_UPLOAD_DIR = os.path.abspath(os.path.join(_BACKEND_DIR, 'uploads'))

class Settings(BaseSettings):
    OCR_ENGINE: str = 'paddleocr'
    UPLOAD_DIR: str = PROD_UPLOAD_DIR
    DATABASE_PATH: str = PROD_DATABASE_PATH
    MAX_FILE_SIZE_MB: int = 10
    LLM_API_KEY: str = ''
    CORS_ORIGINS: list[str] = ['*']
    TEST_MODE: bool = False
    ENVIRONMENT: str = 'development'
    SECRET_KEY: str = 'metrcheck-dev-secret-change-in-prod'
    TOKEN_EXPIRE_MINUTES: int = 480
    # Font height px->mm calibration for Legal Metrology Rule 12:
    # mm = px * factor; factor = 25.4 / DPI when OCR_IMAGE_DPI > 0.
    # Default 0.18 implies ~141 DPI (25.4 / 0.18). For 300 DPI scans use 0.0847.
    FONT_PX_TO_MM_FACTOR: float = 0.18
    OCR_IMAGE_DPI: int = 0
    # Phase 6: External Integrations & Calibration
    FSSAI_API_ENABLED: bool = False
    FSSAI_API_URL: str = ""
    FSSAI_API_KEY: str = ""
    FSSAI_API_TIMEOUT_SEC: float = 3.0
    GS1_API_ENABLED: bool = False
    GS1_API_URL: str = ""
    GS1_API_KEY: str = ""
    GS1_API_TIMEOUT_SEC: float = 3.0
    CALIBRATION_ENABLED: bool = True
    CALIBRATION_DEFAULT_TARGET_MM: float = 50.0  # 50mm standard ArUco target
    # Phase 7.1.8: SMTP & Password Recovery Delivery Configuration
    METRCHECK_SMTP_HOST: str = ""
    METRCHECK_SMTP_PORT: int = 587
    METRCHECK_SMTP_USER: str = ""
    METRCHECK_SMTP_PASS: str = ""
    METRCHECK_SMTP_FROM: str = "noreply@metrcheck.gov.in"
    METRCHECK_SMTP_TLS: bool = True
    METRCHECK_FRONTEND_URL: str = ""
    METRCHECK_DEMO_MODE: bool = True
    @field_validator('UPLOAD_DIR', 'DATABASE_PATH', mode='after')
    @classmethod
    def resolve_paths(cls, v: str) -> str:
        if not os.path.isabs(v):
            return os.path.abspath(os.path.join(_BACKEND_DIR, v))
        return os.path.abspath(v)

    def verify_test_isolation(self) -> None:
        """Enforces that if TEST_MODE is True, storage paths MUST be isolated from production/development files."""
        if self.TEST_MODE or os.environ.get("TEST_MODE") == "1":
            resolved_db = os.path.abspath(self.DATABASE_PATH)
            if resolved_db == PROD_DATABASE_PATH:
                raise RuntimeError(
                    f"SAFETY ERROR: Automated tests cannot run against the production/development database!\n"
                    f"  Attempted DB Path: {resolved_db}\n"
                    f"  Production DB Path: {PROD_DATABASE_PATH}\n"
                    f"  Please configure an isolated test database (e.g. via testing_utils.isolated_test_env)."
                )

    class Config:
        env_file = os.path.join(_BACKEND_DIR, ".env")

    def model_post_init(self, __context: object) -> None:
        """Ensure mobile/Capacitor origins are always in CORS_ORIGINS regardless of .env."""
        required = {
            'https://localhost',
            'http://localhost',
            'capacitor://localhost',
        }
        current = set(self.CORS_ORIGINS)
        if '*' not in current:
            self.CORS_ORIGINS = list(current | required)

settings = Settings()


