import os
from pydantic_settings import BaseSettings
from pydantic import field_validator

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROD_DATABASE_PATH = os.path.abspath(os.path.join(_BACKEND_DIR, 'metrc_check.db'))
PROD_UPLOAD_DIR = os.path.abspath(os.path.join(_BACKEND_DIR, 'uploads'))

KNOWN_INSECURE_SECRETS = {
    "metrcheck-dev-secret-change-in-prod",
    "change-me-in-production-secure-key",
    "CHANGE_ME_USE_A_LONG_RANDOM_SECRET",
    "CHANGE_ME_USE_A_LONG_RANDOM_SECRET_MIN_32_CHARS",
    "your-secure-random-secret-key-here",
    "secret",
    "secret_key",
    "changeme",
    "password",
    "admin",
    "12345678",
}

class Settings(BaseSettings):
    OCR_ENGINE: str = 'paddleocr'
    UPLOAD_DIR: str = PROD_UPLOAD_DIR
    DATABASE_PATH: str = PROD_DATABASE_PATH
    MAX_FILE_SIZE_MB: int = 10
    LLM_API_KEY: str = ''
    GEMINI_API_KEY: str = ''
    GEMINI_MODEL: str = 'gemini-2.5-flash'
    GEMINI_ENABLED: bool = True

    @property
    def active_gemini_api_key(self) -> str:
        return (self.GEMINI_API_KEY or self.LLM_API_KEY or os.environ.get("GEMINI_API_KEY") or os.environ.get("LLM_API_KEY") or "").strip()
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
    EXTERNAL_VERIFICATION_MODE: str = "mock"  # "mock" or "live"
    FSSAI_API_ENABLED: bool = False
    FSSAI_API_URL: str = ""
    FSSAI_API_KEY: str = ""
    FSSAI_API_TIMEOUT_SEC: float = 3.0
    GS1_API_ENABLED: bool = False
    GS1_API_URL: str = ""
    GS1_API_KEY: str = ""
    GS1_API_TIMEOUT_SEC: float = 3.0
    # Comprehensive Barcode / GTIN Product Lookup Configuration
    BARCODE_LOOKUP_ENABLED: bool = False
    BARCODE_LOOKUP_URL: str = ""
    BARCODE_LOOKUP_API_KEY: str = ""
    BARCODE_LOOKUP_TIMEOUT_SEC: float = 10.0

    @property
    def active_barcode_lookup_url(self) -> str:
        return (self.BARCODE_LOOKUP_URL or self.GS1_API_URL or os.environ.get("BARCODE_LOOKUP_URL") or os.environ.get("GS1_API_URL") or "").strip()

    @property
    def active_barcode_lookup_api_key(self) -> str:
        return (self.BARCODE_LOOKUP_API_KEY or self.GS1_API_KEY or os.environ.get("BARCODE_LOOKUP_API_KEY") or os.environ.get("GS1_API_KEY") or "").strip()

    @property
    def is_barcode_lookup_enabled(self) -> bool:
        env_val = os.environ.get("BARCODE_LOOKUP_ENABLED")
        if env_val is not None:
            return env_val.lower() in ("true", "1", "yes")
        return bool(self.BARCODE_LOOKUP_ENABLED or self.GS1_API_ENABLED)

    @property
    def barcode_lookup_timeout_sec(self) -> float:
        env_t = os.environ.get("BARCODE_LOOKUP_TIMEOUT_SEC")
        if env_t:
            try:
                return float(env_t)
            except Exception:
                pass
        return float(self.BARCODE_LOOKUP_TIMEOUT_SEC or self.GS1_API_TIMEOUT_SEC or 10.0)
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
    # Trusted Reverse Proxy Networks / IPs (SEC-AUD-03)
    TRUSTED_PROXIES: list[str] = [
        "127.0.0.1",
        "::1",
        "localhost",
    ]

    def __init__(self, **values):
        super().__init__(**values)
        self.validate_production_secrets()

    @field_validator('TRUSTED_PROXIES', mode='before')
    @classmethod
    def parse_trusted_proxies(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith('[') and v.endswith(']'):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [p.strip() for p in v.split(',') if p.strip()]
        return v

    @field_validator('UPLOAD_DIR', 'DATABASE_PATH', mode='after')
    @classmethod
    def resolve_paths(cls, v: str) -> str:
        if not os.path.isabs(v):
            return os.path.abspath(os.path.join(_BACKEND_DIR, v))
        return os.path.abspath(v)

    def validate_production_secrets(self) -> None:
        """Validates that cryptographic secrets are properly configured for production environments."""
        is_prod = (
            os.environ.get("METRCHECK_ENV") == "production"
            or os.environ.get("ENVIRONMENT") == "production"
            or (self.ENVIRONMENT or "").lower() == "production"
        )
        is_test = bool(self.TEST_MODE)

        if is_prod and not is_test:
            secret = (self.SECRET_KEY or "").strip()
            if not secret:
                raise ValueError("CRITICAL SECURITY ERROR: SECRET_KEY must be configured in production environments.")
            if secret in KNOWN_INSECURE_SECRETS or secret.lower() in {s.lower() for s in KNOWN_INSECURE_SECRETS}:
                raise ValueError("CRITICAL SECURITY ERROR: Default or known placeholder SECRET_KEY cannot be used in production.")
            if len(secret) < 32:
                raise ValueError("CRITICAL SECURITY ERROR: Production SECRET_KEY must be at least 32 characters long for cryptographic security.")

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


