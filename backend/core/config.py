from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# __file__ = this config.py file → backend/core/config.py
# .parent   = backend/core/
# .parent   = backend/
# .parent   = project root (where .env lives)
ROOT_DIR = Path(__file__).parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    """
    Central settings class for the application.
    
    pydantic-settings automatically reads values from:
    1. Environment variables
    2. .env file (because of model_config below)
    
    If a required variable is missing, app will CRASH at startup
    with a clear error — better than crashing at runtime!
    """

    # Database
    DATABASE_URL: str

    # Supabase
    SUPABASE_URL: str
    SUPABASE_PUBLISHABLE_KEY: str
    SUPABASE_SECRET_KEY: str

    # AI & LLM (NVIDIA NIM & LlamaParse)
    NVIDIA_API_KEY: str
    LLAMA_PARSE_API_KEY: str

    # Storage bucket names (we define them here so they're configurable)
    BUCKET_JD: str = "job-descriptions"       # Default value
    BUCKET_CV: str = "candidate-cvs"          # Default value

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),   # Absolute path to .env in project root
        env_file_encoding="utf-8",
        extra="ignore",           # Ignore extra vars in .env (no errors)
    )


# Create a single shared instance — import this everywhere
# "Singleton pattern" — ek hi object banta hai poore app mein
settings = Settings()
