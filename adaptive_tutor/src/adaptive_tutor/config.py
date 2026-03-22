from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()

# Canonical workspace root: .../KnowledgeQuest
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = WORKSPACE_ROOT / "data" / "app.db"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    APP_DB_PATH: str = str(DEFAULT_DB_PATH)

    PASS_THRESHOLD: int = 4
    QUESTIONS_PER_LEVEL: int = 5
    CONSECUTIVE_WRONG_FOR_TEACHING: int = 2
    MAX_LEVELS: int = 8
    MIN_LEVELS: int = 4


settings = Settings()


def ensure_data_dir() -> Path:
    db_path = Path(settings.APP_DB_PATH)
    if not db_path.is_absolute():
        db_path = WORKSPACE_ROOT / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path
