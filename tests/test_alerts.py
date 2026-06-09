"""Tests for alerts selection logic (Plan 4, Task A)."""
from dealfinder.alerts import select_new_deals
from dealfinder.models import Category, Listing


def _listing(source_listing_id: str, deal_score: int | None, is_valid: bool = True) -> Listing:
    return Listing(
        source_key="src",
        source_listing_id=source_listing_id,
        url=f"https://example.com/{source_listing_id}",
        category=Category.CAR,
        title=f"Listing {source_listing_id}",
        price_zar=200000,
        deal_score=deal_score,
        is_valid=is_valid,
    )


def test_returns_only_above_threshold():
    listings = [
        _listing("above", 90),
        _listing("at-threshold", 80),
        _listing("below", 79),
    ]
    result = select_new_deals(listings, alerted_keys=set(), min_score=80)
    ids = {l.source_listing_id for l in result}
    assert "above" in ids
    assert "at-threshold" in ids
    assert "below" not in ids


def test_excludes_invalid_listings():
    listings = [
        _listing("valid", 90, is_valid=True),
        _listing("invalid", 90, is_valid=False),
    ]
    result = select_new_deals(listings, alerted_keys=set(), min_score=80)
    ids = {l.source_listing_id for l in result}
    assert "valid" in ids
    assert "invalid" not in ids


def test_excludes_none_score():
    listings = [
        _listing("scored", 85),
        _listing("no-score", None),
    ]
    result = select_new_deals(listings, alerted_keys=set(), min_score=80)
    ids = {l.source_listing_id for l in result}
    assert "scored" in ids
    assert "no-score" not in ids


def test_excludes_already_alerted_keys():
    listings = [
        _listing("fresh", 90),
        _listing("already-sent", 95),
    ]
    alerted = {("src", "already-sent")}
    result = select_new_deals(listings, alerted_keys=alerted, min_score=80)
    ids = {l.source_listing_id for l in result}
    assert "fresh" in ids
    assert "already-sent" not in ids


def test_sorted_descending_by_score():
    listings = [
        _listing("low", 81),
        _listing("high", 99),
        _listing("mid", 85),
    ]
    result = select_new_deals(listings, alerted_keys=set(), min_score=80)
    scores = [l.deal_score for l in result]
    assert scores == sorted(scores, reverse=True)


def test_empty_listings_returns_empty():
    assert select_new_deals([], alerted_keys=set(), min_score=80) == []


def test_all_filtered_returns_empty():
    listings = [_listing("low", 50)]
    assert select_new_deals(listings, alerted_keys=set(), min_score=80) == []
