"""Centrální nastavení aplikace načítané z proměnných prostředí / souboru .env.

Žádný tajný údaj (API klíč, heslo k DB, SECRET_KEY) není v kódu – vše přichází z .env.
"""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "zmen-me-na-dlouhy-nahodny-retezec"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./studybuddy.db"
    secret_key: str = DEV_SECRET
    access_token_minutes: int = 60 * 24 * 7

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    cors_origins: str = "http://localhost:4321,http://127.0.0.1:4321"

    max_upload_mb: int = 10
    max_text_chars: int = 200_000

    @model_validator(mode="after")
    def _check_production(self):
        # V produkci nesmí běžet s ukázkovým klíčem – kdokoli by si mohl podepsat vlastní token.
        if self.environment == "production" and (self.secret_key == DEV_SECRET or len(self.secret_key) < 32):
            raise ValueError("V produkci nastav SECRET_KEY na náhodný řetězec (min. 32 znaků).")
        return self

    @property
    def sqlalchemy_url(self) -> str:
        """Render/Supabase dávají URL ve tvaru postgres://… – SQLAlchemy chce ovladač psycopg."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    @property
    def cors_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
