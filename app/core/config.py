from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    vault_path: Path = Field(default=Path("Vault"), alias="LIFEOS_VAULT_PATH")
    db_path: Path = Field(default=Path("data/lifeos.db"), alias="LIFEOS_DB_PATH")
    timezone: str = Field(default="UTC", alias="LIFEOS_TIMEZONE")

    model_ingest: str = Field(default="gpt-5-mini", alias="LIFEOS_MODEL_INGEST")
    model_distill: str = Field(default="gpt-5-mini", alias="LIFEOS_MODEL_DISTILL")
    model_analysis: str = Field(default="gpt-5.2", alias="LIFEOS_MODEL_ANALYSIS")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
