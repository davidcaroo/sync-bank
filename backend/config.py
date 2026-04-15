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
    
    SUPABASE_URL: str
    SUPABASE_KEY: str | None = None
    SUPABASE_SERVICE_KEY: str | None = None
    SUPABASE_REQUIRE_SERVICE_KEY: bool = True

    ADMIN_API_KEY: str | None = None
    
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    AI_SERVICE_URL: str = "http://localhost:8001"
    AI_CONFIDENCE_THRESHOLD: float = 0.65

    REDIS_URL: str = "redis://redis:6379/0"
    JOB_QUEUE_NAME: str = "syncbank.jobs"

    METRICS_ENABLED: bool = True
    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "sync-bank-backend"
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None

settings = Settings()
