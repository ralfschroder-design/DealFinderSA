from datetime import datetime

from dealfinder.db import InMemoryRepository, listing_to_row
from dealfinder.models import Category, Listing, RunStats


def test_listing_to_row_serialises_enums_and_lists(sample_listing):
    sample_listing.quality_flags = ["missing_images"]
    row = listing_to_row(sample_listing)
    assert row["source_key"] == "webuycars"
    assert row["source_listing_id"] == "123"
    assert row["category"] == "car"           # enum -> value
    assert row["status"] == "active"
    assert row["image_urls"] == ["https://img/1.jpg"]
    assert row["quality_flags"] == ["missing_images"]
    assert "last_seen_at" in row              # refreshed each upsert
    assert "first_seen_at" not in row         # preserved by DB default/on insert


def test_inmemory_repo_upserts_by_natural_key(sample_listing):
    repo = InMemoryRepository()
    assert repo.upsert_listings([sample_listing]) == 1
    # second upsert of same natural key updates, not duplicates
    sample_listing.price_zar = 320000
    assert repo.upsert_listings([sample_listing]) == 1
    stored = repo.get("webuycars", "123")
    assert stored.price_zar == 320000
    assert len(repo.all()) == 1


def test_inmemory_repo_records_run():
    repo = InMemoryRepository()
    repo.record_run(RunStats(source_keys=["webuycars"], fetched=2, upserted=1, invalid=1))
    assert repo.runs[-1].fetched == 2


def test_record_price_if_changed(sample_listing):
    from dealfinder.db import InMemoryRepository

    repo = InMemoryRepository()
    # first observation is always recorded
    assert repo.record_price_if_changed(sample_listing) is True
    # same price again → not recorded
    assert repo.record_price_if_changed(sample_listing) is False
    # changed price → recorded
    sample_listing.price_zar = 329900
    assert repo.record_price_if_changed(sample_listing) is True
    assert len(repo.prices) == 2


def test_record_price_ignores_missing_price(sample_listing):
    from dealfinder.db import InMemoryRepository

    sample_listing.price_zar = None
    repo = InMemoryRepository()
    assert repo.record_price_if_changed(sample_listing) is False
    assert repo.prices == []


def test_upsert_dedups_batch_by_key(sample_listing):
    from copy import deepcopy
    from dealfinder.db import InMemoryRepository

    a = sample_listing
    b = deepcopy(sample_listing)
    b.price_zar = 111111  # same (source_key, source_listing_id), different price
    repo = InMemoryRepository()
    n = repo.upsert_listings([a, b])
    assert n == 1
    assert len(repo.all()) == 1
    assert repo.get("webuycars", "123").price_zar == 111111  # last wins


# ---------------------------------------------------------------------------
# search_listings tests
# ---------------------------------------------------------------------------

def _make_repo_with_three() -> InMemoryRepository:
    """Return an InMemoryRepository seeded with 3 listings for search tests."""
    repo = InMemoryRepository()
    repo.upsert_listings([
        Listing(
            source_key="s",
            source_listing_id="car-1",
            url="https://example.com/1",
            category=Category.CAR,
            title="2019 Toyota Hilux",
            make="Toyota",
            model="Hilux",
            year=2019,
            price_zar=339900,
            town="Pretoria",
            is_valid=True,
        ),
        Listing(
            source_key="s",
            source_listing_id="bike-1",
            url="https://example.com/2",
            category=Category.BIKE,
            title="2020 Yamaha R1",
            make="Yamaha",
            model="R1",
            year=2020,
            price_zar=185000,
            town="Cape Town",
            is_valid=True,
        ),
        Listing(
            source_key="s",
            source_listing_id="invalid-1",
            url="https://example.com/3",
            category=Category.CAR,
            title="Broken listing",
            make=None,
            price_zar=None,
            is_valid=False,
        ),
    ])
    return repo


def test_search_listings_category_filter():
    repo = _make_repo_with_three()
    results = repo.search_listings(category=Category.BIKE)
    assert len(results) == 1
    assert results[0].make == "Yamaha"


def test_search_listings_price_range():
    repo = _make_repo_with_three()
    # only Yamaha (185 000) fits under 200 000
    results = repo.search_listings(max_price=200000)
    titles = [r.title for r in results]
    assert any("Yamaha" in t for t in titles)
    assert not any("Hilux" in t for t in titles)


def test_search_listings_min_price():
    repo = _make_repo_with_three()
    # only Hilux (339 900) is above 250 000
    results = repo.search_listings(min_price=250000)
    assert len(results) == 1
    assert results[0].make == "Toyota"


def test_search_listings_sort_price_asc():
    repo = _make_repo_with_three()
    results = repo.search_listings(sort="price_asc")
    prices = [r.price_zar for r in results if r.price_zar is not None]
    assert prices == sorted(prices)


def test_search_listings_valid_only_excludes_invalid():
    repo = _make_repo_with_three()
    results = repo.search_listings(valid_only=True)
    assert all(r.is_valid for r in results)
    # with valid_only=False we should see the invalid one too
    all_results = repo.search_listings(valid_only=False)
    assert any(not r.is_valid for r in all_results)
