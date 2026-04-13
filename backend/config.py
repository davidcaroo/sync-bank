from pydantic_settings import BaseSettings

class Settings(BaseSettings):
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

    ADMIN_API_KEY: str | None = None
    
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    AI_SERVICE_URL: str = "http://localhost:8001"
    AI_CONFIDENCE_THRESHOLD: float = 0.65

    class Config:
        env_file = ".env"

settings = Settings()
