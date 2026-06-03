from datetime import datetime

from dealfinder.db import InMemoryRepository, listing_to_row
from dealfinder.models import RunStats


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
