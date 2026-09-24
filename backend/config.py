from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"

    IMAP_HOST: str = "imap.gmail.com"
    IMAP_PORT: int = 993
    IMAP_MAILBOX: str = "inbox"
    IMAP_USER: str
    IMAP_PASS: str

    ALEGRA_EMAIL: str
    ALEGRA_TOKEN: str
    ALEGRA_CUENTA_DEFAULT_GASTOS: str = "5001"

    DATABASE_URL: str
    DB_POOL_MIN_SIZE: int = 1
    DB_POOL_MAX_SIZE: int = 5

    ADMIN_API_KEY: str | None = None
    ADMIN_USERNAME: str = "admin"
    SESSION_SECRET: str | None = None
    COMPANY_NIT: str | None = None
    MIN_ISSUE_DATE: str = "2026-09-01"
    LEARNING_START_DATE: str = "2026-01-01"

    MAX_ATTACHMENT_BYTES: int = 20 * 1024 * 1024
    MAX_ZIP_ENTRIES: int = 100
    MAX_ZIP_EXPANDED_BYTES: int = 50 * 1024 * 1024
    MAX_ZIP_COMPRESSION_RATIO: int = 100

    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URI: str | None = None
    GOOGLE_ALLOWED_EMAILS: str = ""

    METRICS_ENABLED: bool = True
    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "sync-bank-backend"
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None


settings = Settings()


def validate_security_settings() -> None:
    if settings.APP_ENV == "production" and not (
        settings.ADMIN_API_KEY and settings.SESSION_SECRET and settings.COMPANY_NIT
    ):
        raise RuntimeError(
            "En produccion ADMIN_API_KEY, SESSION_SECRET y COMPANY_NIT son obligatorias"
        )


def google_allowed_emails() -> set[str]:
    extra = settings.GOOGLE_ALLOWED_EMAILS.split(",")
    return {e.strip().lower() for e in [settings.IMAP_USER, *extra] if e.strip()}
