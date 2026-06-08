"""Tests for GumtreeAdapter.parse_page — offline, against a saved fixture."""
from __future__ import annotations

from pathlib import Path

import pytest

from dealfinder.adapters.gumtree import GumtreeAdapter
from dealfinder.models import Category, Listing

FIXTURE = Path(__file__).parent / "fixtures" / "gumtree_cars.html"


@pytest.fixture(scope="module")
def listings() -> list[Listing]:
    html = FIXTURE.read_text(encoding="utf-8")
    return GumtreeAdapter().parse_page(html, Category.CAR)


def test_minimum_count(listings):
    assert len(listings) >= 15, f"Expected >=15 listings, got {len(listings)}"


def test_source_key_and_category(listings):
    for listing in listings:
        assert listing.source_key == "gumtree"
        assert listing.category == Category.CAR


def test_source_listing_id_truthy(listings):
    for listing in listings:
        assert listing.source_listing_id, f"Empty source_listing_id on {listing.url}"


def test_url_prefix(listings):
    for listing in listings:
        assert listing.url.startswith("https://www.gumtree.co.za/a-"), (
            f"Unexpected URL: {listing.url}"
        )


def test_at_least_10_prices(listings):
    priced = [l for l in listings if l.price_zar is not None and l.price_zar > 0]
    assert len(priced) >= 10, f"Expected >=10 priced listings, got {len(priced)}"


def test_at_least_10_towns(listings):
    with_town = [l for l in listings if l.town]
    assert len(with_town) >= 10, f"Expected >=10 listings with town, got {len(with_town)}"


def test_at_least_5_years(listings):
    with_year = [l for l in listings if l.year and 1990 <= l.year <= 2026]
    assert len(with_year) >= 5, f"Expected >=5 listings with valid year, got {len(with_year)}"


def test_unique_ids(listings):
    ids = [l.source_listing_id for l in listings]
    assert len(ids) == len(set(ids)), "Duplicate source_listing_id values found"
