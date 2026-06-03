import pytest

from dealfinder.config import Settings, Home, FetchCfg, ValidityCfg, SourceCfg
from dealfinder.models import Category, Listing


@pytest.fixture
def settings() -> Settings:
    return Settings(
        home=Home(name="Test", lat=-25.0, lng=28.0, radius_km=100),
        fetch=FetchCfg(min_interval_seconds=0.0, max_retries=2, user_agent="UA"),
        validity=ValidityCfg(min_price_zar=5000, max_price_zar=15000000),
        sources={"webuycars": SourceCfg(enabled=True, max_pages=1)},
        supabase_url="https://x.supabase.co",
        supabase_key="key",
    )


@pytest.fixture
def sample_listing() -> Listing:
    return Listing(
        source_key="webuycars",
        source_listing_id="123",
        url="https://www.webuycars.co.za/buy-a-car/123",
        category=Category.CAR,
        title="2019 Toyota Hilux 2.4 GD-6 SRX",
        make="Toyota",
        model="Hilux",
        variant="2.4 GD-6 SRX",
        year=2019,
        price_zar=339900,
        mileage_km=145000,
        province="Gauteng",
        town="Pretoria",
        image_urls=["https://img/1.jpg"],
    )
