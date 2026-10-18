from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    PROJECT_NAME: str = "AI-Powered Software Digital Twin"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    APP_ENV: str = "development"

    # Security & Auth Settings
    SECRET_KEY: str = "digitaltwin_insecure_default_secret_key_change_in_production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    ALLOWED_WORKSPACE_ROOTS: List[str] = []

    # CORS Settings (SEC-06 remediation)
    CORS_ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOWED_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"]
    CORS_ALLOWED_HEADERS: List[str] = [
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "User-Agent",
        "X-Requested-With",
    ]

    # Request Governance & Abuse Settings
    MAX_REQUEST_BODY_BYTES: int = 10 * 1024 * 1024   # 10 MB global limit
    MAX_AUTH_BODY_BYTES: int = 64 * 1024             # 64 KB auth endpoints
    AUTH_MAX_LOGIN_ATTEMPTS: int = 5                 # Max failed logins before temporary lockout
    AUTH_LOCKOUT_SECONDS: int = 300                  # 5 minute lockout window

    def validate_cors(self):
        """Enforces that wildcard origins are never combined with credentials (SEC-06)."""
        if "*" in self.CORS_ALLOWED_ORIGINS and self.CORS_ALLOW_CREDENTIALS:
            raise ValueError("SEC-06 Invariant: CORS wildcard '*' cannot be combined with allow_credentials=True.")


    # Database Settings
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5434
    POSTGRES_USER: str = "digitaltwin"
    POSTGRES_PASSWORD: str = "digitaltwin"
    POSTGRES_DB: str = "digitaltwin_db"
    DATABASE_URL_OVERRIDE: Optional[str] = None

    # LLM Settings (multi-provider abstraction)
    LLM_PROVIDER: str = "gemini"  # gemini, openai, anthropic, mock
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    LLM_MODEL_NAME: Optional[str] = None

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            return self.DATABASE_URL_OVERRIDE
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
