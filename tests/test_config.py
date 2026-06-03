from pathlib import Path

from dealfinder.config import load_settings


def test_load_settings_reads_yaml_and_env(tmp_path, monkeypatch):
    cfg = tmp_path / "default.yaml"
    cfg.write_text(
        "home:\n  name: Test\n  lat: -25.0\n  lng: 28.0\n  radius_km: 50\n"
        "fetch:\n  min_interval_seconds: 1.0\n  max_retries: 2\n  user_agent: UA\n"
        "validity:\n  min_price_zar: 1000\n  max_price_zar: 2000000\n"
        "sources:\n  webuycars:\n    enabled: true\n    max_pages: 1\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "key123")

    s = load_settings(config_path=cfg)

    assert s.home.radius_km == 50
    assert s.fetch.max_retries == 2
    assert s.validity.max_price_zar == 2000000
    assert s.supabase_url == "https://x.supabase.co"
    assert s.supabase_key == "key123"
    assert s.sources["webuycars"].enabled is True
