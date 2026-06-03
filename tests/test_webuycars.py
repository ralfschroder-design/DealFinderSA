import json
from pathlib import Path

from dealfinder.adapters.webuycars import WeBuyCarsAdapter
from dealfinder.models import Category

FIXTURE = Path(__file__).parent / "fixtures" / "webuycars_search.json"


def test_parse_maps_records_to_listings():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    adapter = WeBuyCarsAdapter()

    listings = adapter.parse_page(payload)

    assert len(listings) == 2
    first = listings[0]
    assert first.source_key == "webuycars"
    assert first.source_listing_id == "1001"
    assert first.category == Category.CAR
    assert first.make == "Toyota"
    assert first.model == "Hilux"
    assert first.year == 2019
    assert first.price_zar == 339900
    assert first.mileage_km == 145000
    assert first.town == "Pretoria"
    assert first.province == "Gauteng"
    assert first.image_urls[0].endswith("a.jpg")
    assert first.url.endswith("/1001")
    assert first.raw["StockNumber"] == "WBC1001"


def test_parse_keeps_zero_price_record_for_validity_layer():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    listings = WeBuyCarsAdapter().parse_page(payload)
    second = listings[1]
    # Parsing does not judge validity; price 0 is passed through as-is.
    assert second.price_zar == 0
    assert second.image_urls == []
