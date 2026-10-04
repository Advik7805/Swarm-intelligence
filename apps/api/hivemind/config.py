"""Environment-driven configuration. Auto-falls into fully-offline DEMO MODE."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    # LLM (OpenAI-compatible)
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model_name: str = ""

    # Local Ollama (OpenAI-compatible endpoint)
    ollama_base_url: str = ""
    ollama_model: str = ""

    port: int = 8000
    database_url: str = "sqlite:///data/hivemind.db"
    demo_mode: str = "auto"  # auto | true | false

    @property
    def is_demo(self) -> bool:
        if self.demo_mode == "true":
            return True
        if self.demo_mode == "false":
            return False
        # auto: live only when a key (or ollama) is configured
        return not (self.llm_api_key or self.ollama_base_url)

    @property
    def db_path(self) -> Path:
        p = self.database_url.replace("sqlite:///", "")
        path = Path(p)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent / p
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
