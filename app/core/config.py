from __future__ import annotations

import json
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


def build_db_url(
    host: str,
    port: int | str,
    user: str,
    password: str,
    dbname: str,
    ssl_ca: Optional[str] = None,
) -> str:
    qs = f"?ssl_ca={ssl_ca}" if ssl_ca else ""
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{dbname}{qs}"


class Settings(BaseSettings):
    # --- App ---
    PROJECT_NAME: str = "ChartAgent"
    API_V1_STR: str = "/api/v1"

    # --- Security ---
    API_KEYS: List[str] | str = []  # acepta lista, CSV o JSON

    # --- CORS ---
    BACKEND_CORS_ORIGINS: List[str] | str = []  # acepta lista, CSV o JSON

    # --- DB fields (se leen del .env directamente) ---
    DB_HOST: str = Field(default="127.0.0.1")
    DB_PORT: int = Field(default=3306)
    DB_USER: str = Field(default="root")
    DB_PASS: str = Field(default="")
    DB_NAME: str = Field(default="chartagentstore")
    DB_SSL_CA: Optional[str] = None

    # --- LLM Provider Settings ---
    LLM_PROVIDER_TYPE: str = Field(
        default="gemini", description="The type of LLM provider to use (gemini, openai, ollama)."
    )
    GEMINI_API_KEY: Optional[str] = Field(None, description="API key for Google Gemini.")
    GEMINI_MODEL: str = Field(
        default="gemini-1.5-pro-latest", description="The name of the model to use with Gemini."
    )
    OPENAI_API_KEY: Optional[str] = Field(None, description="API key for OpenAI.")
    OPENAI_MODEL: str = Field(
        default="gpt-4o", description="The name of the model to use with OpenAI."
    )
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434", description="Base URL for the Ollama API."
    )
    OLLAMA_MODEL: str = Field(
        default="llama3", description="The name of the model to use with Ollama."
    )
    TWELVE_DATA_KEY: Optional[str] = Field(None, description="API key for Twelve Data.")

    # Puedes pasar DATABASE_URL directamente si quieres
    DATABASE_URL: Optional[str] = None

    # --- Debug / DX ---
    DEBUG_SQL: bool = False

    # ---------- Validadores híbridos (CSV/JSON) ----------
    @field_validator("API_KEYS", mode="before")
    @classmethod
    def _parse_api_keys(cls, v):
        if v is None:
            return []
        if isinstance(v, (list, tuple)):
            return [str(x).strip().strip('"').strip("'") for x in v if str(x).strip()]
        s = str(v).strip()
        if s.startswith("["):
            try:
                arr = json.loads(s)
                return [str(x).strip().strip('"').strip("'") for x in arr if str(x).strip()]
            except Exception:
                pass
        return [p.strip().strip('"').strip("'") for p in s.split(",") if p.strip()]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors(cls, v):
        if v is None:
            return []
        if isinstance(v, (list, tuple)):
            return [str(x).strip() for x in v if str(x).strip()]
        s = str(v).strip()
        if s.startswith("["):
            try:
                arr = json.loads(s)
                return [str(x).strip() for x in arr if str(x).strip()]
            except Exception:
                pass
        return [p.strip() for p in s.split(",") if p.strip()]

    # ---------- Helpers ----------
    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return build_db_url(
            host=self.DB_HOST,
            port=self.DB_PORT,
            user=self.DB_USER,
            password=self.DB_PASS,
            dbname=self.DB_NAME,
            ssl_ca=self.DB_SSL_CA,
        )

    @property
    def api_keys_list(self) -> List[str]:
        v = self.API_KEYS
        if isinstance(v, str):
            # Ya parseado arriba en la práctica; fallback por seguridad
            if v.strip().startswith("["):
                try:
                    arr = json.loads(v)
                    return [str(x).strip().strip('"').strip("'") for x in arr if str(x).strip()]
                except Exception:
                    pass
            return [p.strip().strip('"').strip("'") for p in v.split(",") if p.strip()]
        return [str(x).strip().strip('"').strip("'") for x in v if str(x).strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        v = self.BACKEND_CORS_ORIGINS
        if isinstance(v, str):
            if v.strip().startswith("["):
                try:
                    arr = json.loads(v)
                    return [str(x).strip() for x in arr if str(x).strip()]
                except Exception:
                    pass
            return [p.strip() for p in v.split(",") if p.strip()]
        return [str(x).strip() for x in v if str(x).strip()]

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",  # por si dejas otras envs no declaradas
    }


settings = Settings()
