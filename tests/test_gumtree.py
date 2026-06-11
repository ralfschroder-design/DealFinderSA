"""Tests for GumtreeAdapter.parse_page — offline, against a saved fixture."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dealfinder.adapters.gumtree import GumtreeAdapter, parse_posted_at
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


# ---------------------------------------------------------------------------
# parse_posted_at — detail-page date extraction
# ---------------------------------------------------------------------------

DETAIL_FIXTURE = Path(__file__).parent / "fixtures" / "gumtree_detail.html"


def test_parse_posted_at_from_availability_starts():
    """Primary path: availabilityStarts JSON key yields exact UTC midnight date."""
    html = DETAIL_FIXTURE.read_text(encoding="utf-8")
    result = parse_posted_at(html)
    assert result is not None
    assert result == datetime(2026, 4, 24, tzinfo=timezone.utc)


def test_parse_posted_at_relative_only_with_injected_now():
    """Fallback: relative creation-date text is resolved against an injected now."""
    # HTML has only a relative date, no availabilityStarts
    html = '<span class="creation-date">9 days ago</span>'
    now = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    result = parse_posted_at(html, now=now)
    assert result is not None
    expected = now - timedelta(days=9)
    assert abs((result - expected).total_seconds()) < 86400  # within 1 day


def test_parse_posted_at_relative_weeks():
    """Fallback: '2 weeks ago' resolves to now minus 14 days."""
    html = '<span class="creation-date">2 weeks ago</span>'
    now = datetime(2026, 6, 10, 0, 0, 0, tzinfo=timezone.utc)
    result = parse_posted_at(html, now=now)
    assert result is not None
    expected = now - timedelta(days=14)
    assert abs((result - expected).total_seconds()) < 86400


def test_parse_posted_at_relative_months():
    """Fallback: '1 month ago' resolves to now minus 30 days."""
    html = '<span class="creation-date">1 month ago</span>'
    now = datetime(2026, 6, 10, 0, 0, 0, tzinfo=timezone.utc)
    result = parse_posted_at(html, now=now)
    assert result is not None
    expected = now - timedelta(days=30)
    assert abs((result - expected).total_seconds()) < 86400


def test_parse_posted_at_json_creation_date_fallback():
    """Fallback also picks up creationDate in inline JSON."""
    html = '{"creationDate":"3 days ago"}'
    now = datetime(2026, 6, 10, 0, 0, 0, tzinfo=timezone.utc)
    result = parse_posted_at(html, now=now)
    assert result is not None
    expected = now - timedelta(days=3)
    assert abs((result - expected).total_seconds()) < 86400


def test_parse_posted_at_empty_returns_none():
    """No date signals at all → None (graceful)."""
    assert parse_posted_at("") is None
    assert parse_posted_at("<html><body>no date here</body></html>") is None


def test_parse_posted_at_prefers_availability_starts_over_relative():
    """When both signals are present, structured date wins."""
    html = (
        '"availabilityStarts":"2026-03-15"'
        '<span class="creation-date">60 days ago</span>'
    )
    now = datetime(2026, 6, 10, 0, 0, 0, tzinfo=timezone.utc)
    result = parse_posted_at(html, now=now)
    assert result == datetime(2026, 3, 15, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# enrich_posted_at — GumtreeAdapter detail-page enrichment
# ---------------------------------------------------------------------------

class FakeFetcher:
    """Returns the detail fixture HTML for any URL."""

    def __init__(self, html: str):
        self.html = html
        self.calls: list[str] = []

    def get_text(self, url, **kwargs):
        self.calls.append(url)
        return self.html


def _undated_listing(lid: str) -> Listing:
    return Listing(
        source_key="gumtree",
        source_listing_id=lid,
        url=f"https://www.gumtree.co.za/a-cars-bakkies/durban/some-car/{lid}",
        category=Category.CAR,
        title="Some car",
        posted_at=None,
    )


def test_enrich_posted_at_sets_date_on_undated_listings():
    """enrich_posted_at fetches each undated listing's detail page and sets posted_at."""
    detail_html = DETAIL_FIXTURE.read_text(encoding="utf-8")
    fetcher = FakeFetcher(detail_html)
    listings = [_undated_listing("aaa"), _undated_listing("bbb")]

    count = GumtreeAdapter().enrich_posted_at(fetcher, listings)

    assert count == 2
    for listing in listings:
        assert listing.posted_at == datetime(2026, 4, 24, tzinfo=timezone.utc)
    assert len(fetcher.calls) == 2


def test_enrich_posted_at_respects_cap():
    """cap kwarg limits the number of detail fetches performed."""
    detail_html = DETAIL_FIXTURE.read_text(encoding="utf-8")
    fetcher = FakeFetcher(detail_html)
    listings = [_undated_listing(str(i)) for i in range(5)]

    count = GumtreeAdapter().enrich_posted_at(fetcher, listings, cap=2)

    assert count == 2
    assert len(fetcher.calls) == 2
    # Only the first two should have posted_at set
    assert listings[0].posted_at is not None
    assert listings[1].posted_at is not None
    assert listings[2].posted_at is None


def test_enrich_posted_at_skips_already_dated():
    """Listings that already have posted_at must not be re-fetched."""
    detail_html = DETAIL_FIXTURE.read_text(encoding="utf-8")
    fetcher = FakeFetcher(detail_html)

    already_dated = _undated_listing("already")
    already_dated.posted_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    undated = _undated_listing("fresh")

    count = GumtreeAdapter().enrich_posted_at(fetcher, [already_dated, undated])

    assert count == 1
    # already_dated unchanged
    assert already_dated.posted_at == datetime(2026, 1, 1, tzinfo=timezone.utc)
    # undated now dated
    assert undated.posted_at == datetime(2026, 4, 24, tzinfo=timezone.utc)
    assert len(fetcher.calls) == 1


def test_enrich_posted_at_tolerates_fetch_failure():
    """A failing detail fetch must not abort enrichment of subsequent listings."""

    class BrokenFetcher:
        def __init__(self, good_html: str):
            self.good_html = good_html
            self.calls = 0

        def get_text(self, url, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("network timeout")
            return self.good_html

    detail_html = DETAIL_FIXTURE.read_text(encoding="utf-8")
    fetcher = BrokenFetcher(detail_html)
    listings = [_undated_listing("fail"), _undated_listing("ok")]

    count = GumtreeAdapter().enrich_posted_at(fetcher, listings)

    # first listing failed (graceful), second succeeded
    assert count == 1
    assert listings[0].posted_at is None
    assert listings[1].posted_at == datetime(2026, 4, 24, tzinfo=timezone.utc)
