from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


class Home(BaseModel):
    name: str
    lat: float
    lng: float
    radius_km: int


class FetchCfg(BaseModel):
    min_interval_seconds: float
    max_retries: int
    user_agent: str


class ValidityCfg(BaseModel):
    min_price_zar: int
    max_price_zar: int


class SourceCfg(BaseModel):
    enabled: bool = False
    max_pages: int = 1


class Settings(BaseModel):
    home: Home
    fetch: FetchCfg
    validity: ValidityCfg
    sources: dict[str, SourceCfg]
    supabase_url: str | None = None
    supabase_key: str | None = None


def load_settings(config_path: Path | None = None) -> Settings:
    load_dotenv()
    path = config_path or DEFAULT_CONFIG
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Settings(
        **data,
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_key=os.getenv("SUPABASE_KEY"),
    )
