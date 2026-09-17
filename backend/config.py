from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"

    IMAP_HOST: str = "imap.gmail.com"
    IMAP_PORT: int = 993
    IMAP_USER: str
    IMAP_PASS: str
    
    ALEGRA_EMAIL: str
    ALEGRA_TOKEN: str
    ALEGRA_CUENTA_DEFAULT_GASTOS: str = "5001"
    
    DATABASE_URL: str
    DB_POOL_MIN_SIZE: int = 1
    DB_POOL_MAX_SIZE: int = 5

    ADMIN_API_KEY: str | None = None
    
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    AI_SERVICE_URL: str = "http://localhost:8001"
    AI_CONFIDENCE_THRESHOLD: float = 0.65

    METRICS_ENABLED: bool = True
    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "sync-bank-backend"
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None

settings = Settings()
