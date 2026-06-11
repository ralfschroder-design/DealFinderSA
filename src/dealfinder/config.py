from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

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
    max_listing_age_days: int = 120


class SourceCfg(BaseModel):
    enabled: bool = False
    max_pages: int = 1
    fetch_detail: bool = True
    max_detail_fetches: int = 60


class AlertsCfg(BaseModel):
    min_score: int = 80


class Settings(BaseModel):
    home: Home
    fetch: FetchCfg
    validity: ValidityCfg
    sources: dict[str, SourceCfg]
    alerts: AlertsCfg = Field(default_factory=AlertsCfg)
    supabase_url: str | None = None
    supabase_key: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_pass: str | None = None
    alert_email_to: str | None = None


def load_settings(config_path: Path | None = None) -> Settings:
    load_dotenv()
    path = config_path or DEFAULT_CONFIG
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    smtp_port_raw = os.getenv("SMTP_PORT")
    return Settings(
        **data,
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_key=os.getenv("SUPABASE_KEY"),
        smtp_host=os.getenv("SMTP_HOST"),
        smtp_port=int(smtp_port_raw) if smtp_port_raw else 587,
        smtp_user=os.getenv("SMTP_USER"),
        smtp_pass=os.getenv("SMTP_PASS"),
        alert_email_to=os.getenv("ALERT_EMAIL_TO"),
    )
