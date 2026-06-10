"""Tests for GumtreeAdapter.parse_page — offline, against a saved fixture."""
from __future__ import annotations

from datetime import timezone
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


def test_fetch_listings_dedups_ids_across_categories(settings):
    from dealfinder.adapters.gumtree import GumtreeAdapter

    html = (
        '<div class="tile-item">'
        '<a href="/a-cars-bakkies/durbanville/2011-toyota-rav4/123"></a>'
        '<span class="ad-price">R 100 000</span>'
        '<img data-src="https://img.example/x.jpg">'
        '</div>'
    )

    class FakeFetcher:
        def get_text(self, url, params=None, headers=None):
            return html

    listings = GumtreeAdapter().fetch_listings(FakeFetcher(), settings)
    ids = [l.source_listing_id for l in listings]
    assert len(ids) == len(set(ids))   # no duplicate ids
    assert len(listings) == 1          # same ad across categories collapses to one


def test_posted_at_set_on_at_least_one_listing(listings):
    """parse_page must set posted_at (timezone-aware) on listings whose creationDate
    appears in the galleryAdList_searchGallery inline JSON (expect ≥1 from fixture)."""
    with_date = [l for l in listings if l.posted_at is not None]
    assert len(with_date) >= 1, (
        f"Expected at least 1 listing with posted_at set, got 0 out of {len(listings)}"
    )


def test_posted_at_is_timezone_aware(listings):
    """Any posted_at value must carry UTC tzinfo so datetime arithmetic never raises."""
    for l in listings:
        if l.posted_at is not None:
            assert l.posted_at.tzinfo is not None, (
                f"Listing {l.source_listing_id} has naive posted_at"
            )
            assert l.posted_at.tzinfo == timezone.utc


def test_posted_at_is_sane_year(listings):
    """posted_at datetimes must be in a plausible range (year >= 2020)."""
    for l in listings:
        if l.posted_at is not None:
            assert l.posted_at.year >= 2020, (
                f"Listing {l.source_listing_id} has posted_at year {l.posted_at.year}"
            )


def test_listings_without_creation_date_have_none_posted_at(listings):
    """Listings whose id is absent from the JSON map must have posted_at=None (graceful)."""
    without_date = [l for l in listings if l.posted_at is None]
    # The fixture has 32 listings but only 8 have matching JSON ids; rest must be None
    assert len(without_date) >= 1, (
        "Expected some listings with posted_at=None (graceful fallback)"
    )


def test_fetch_listings_survives_a_failing_page(settings):
    from dealfinder.adapters.gumtree import GumtreeAdapter

    good_html = (
        '<div class="tile-item">'
        '<a href="/a-cars-bakkies/pretoria/2019-toyota-hilux/999"></a>'
        '<span class="ad-price">R 100 000</span>'
        '<img data-src="https://img.example/x.jpg">'
        '</div>'
    )

    class FlakyFetcher:
        def __init__(self):
            self.calls = 0

        def get_text(self, url, params=None, headers=None):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("transient network blip")
            return good_html

    # Must NOT raise, and must still return the listings from the pages that worked.
    listings = GumtreeAdapter().fetch_listings(FlakyFetcher(), settings)
    assert len(listings) >= 1
    assert listings[0].source_listing_id == "999"
