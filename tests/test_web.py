"""Tests for dealfinder.web — uses TestClient + InMemoryRepository (offline)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dealfinder.db import InMemoryRepository
from dealfinder.models import Category, Listing
from dealfinder.web import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def repo() -> InMemoryRepository:
    r = InMemoryRepository()
    r.upsert_listings([
        Listing(
            source_key="test",
            source_listing_id="car-1",
            url="https://example.com/car-1",
            category=Category.CAR,
            title="2019 Toyota Hilux",
            make="Toyota",
            model="Hilux",
            year=2019,
            price_zar=339900,
            town="Pretoria",
            image_urls=["https://example.com/img/hilux.jpg"],
            is_valid=True,
        ),
        Listing(
            source_key="test",
            source_listing_id="bike-1",
            url="https://example.com/bike-1",
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
            source_key="test",
            source_listing_id="invalid-1",
            url="https://example.com/invalid-1",
            category=Category.CAR,
            title="Some broken listing",
            make=None,
            price_zar=None,
            is_valid=False,
        ),
    ])
    return r


@pytest.fixture()
def client(repo: InMemoryRepository) -> TestClient:
    return TestClient(create_app(repo))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_root_returns_200(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200


def test_root_shows_valid_listings_only(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Toyota" in resp.text
    assert "Yamaha" in resp.text
    # invalid listing must not appear
    assert "Some broken listing" not in resp.text


def test_category_filter_bike(client: TestClient) -> None:
    resp = client.get("/?category=bike")
    assert resp.status_code == 200
    assert "Yamaha" in resp.text
    assert "Toyota" not in resp.text


def test_max_price_filter(client: TestClient) -> None:
    resp = client.get("/?max_price=200000")
    assert resp.status_code == 200
    assert "Yamaha" in resp.text
    assert "339" not in resp.text  # Hilux price R339,900 should not appear


def test_q_filter_hilux(client: TestClient) -> None:
    resp = client.get("/?q=hilux")
    assert resp.status_code == 200
    assert "Toyota" in resp.text
    assert "Yamaha" not in resp.text


def test_healthz(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_blank_price_fields_do_not_error(repo: InMemoryRepository) -> None:
    """Empty string from blank form inputs must NOT cause a 422."""
    client = TestClient(create_app(repo))
    r = client.get("/?q=&make=&min_price=&max_price=&town=&category=&sort=recent")
    assert r.status_code == 200          # was 422 before fix
    assert "Toyota" in r.text            # still renders results


def test_valid_only_can_be_disabled(repo: InMemoryRepository) -> None:
    """valid_only=0 must show invalid listings; default (absent) must hide them."""
    client = TestClient(create_app(repo))
    # Default — invalid listing absent
    default_resp = client.get("/")
    assert default_resp.status_code == 200
    assert "Some broken listing" not in default_resp.text
    # Explicit valid_only=0 — invalid listing present
    all_resp = client.get("/?valid_only=0")
    assert all_resp.status_code == 200
    assert "Some broken listing" in all_resp.text


def test_sort_deal_returns_200(client: TestClient) -> None:
    resp = client.get("/?sort=deal")
    assert resp.status_code == 200


def test_min_score_param_returns_200(client: TestClient) -> None:
    resp = client.get("/?min_score=90")
    assert resp.status_code == 200


def test_deal_badge_shown_for_scored_listing() -> None:
    """A listing with deal_score set must display the deal badge text."""
    r = InMemoryRepository()
    r.upsert_listings([
        Listing(
            source_key="test",
            source_listing_id="deal-1",
            url="https://example.com/deal-1",
            category=Category.CAR,
            title="2019 Toyota Hilux",
            make="Toyota",
            model="Hilux",
            year=2019,
            price_zar=240_000,
            is_valid=True,
            deal_score=95,
            deal_delta_zar=60_000,
            deal_delta_pct=0.20,
            deal_confidence="high",
            estimated_market_price=300_000,
        ),
    ])
    c = TestClient(create_app(r))
    resp = c.get("/")
    assert resp.status_code == 200
    # Badge should contain score and some deal indicator
    assert "score" in resp.text.lower() or "under market" in resp.text.lower()


def test_deal_badge_not_shown_for_unscored_listing() -> None:
    """A listing with deal_score=None must not show deal badge noise."""
    r = InMemoryRepository()
    r.upsert_listings([
        Listing(
            source_key="test",
            source_listing_id="unscored-1",
            url="https://example.com/unscored-1",
            category=Category.CAR,
            title="2019 Nissan Navara",
            make="Nissan",
            model="Navara",
            year=2019,
            price_zar=250_000,
            is_valid=True,
            deal_score=None,
        ),
    ])
    c = TestClient(create_app(r))
    resp = c.get("/")
    assert resp.status_code == 200
    # "under market" badge text should NOT appear for an unscored listing
    assert "under market" not in resp.text


def test_min_year_filter_returns_200(client: TestClient) -> None:
    resp = client.get("/?min_year=2015")
    assert resp.status_code == 200


def test_min_year_filter_shows_recent_hides_old() -> None:
    """/?min_year=2015 must show the 2019 Hilux and 2020 Yamaha but hide a 1998 car."""
    r = InMemoryRepository()
    r.upsert_listings([
        Listing(
            source_key="test",
            source_listing_id="modern-1",
            url="https://example.com/modern-1",
            category=Category.CAR,
            title="2019 Toyota Hilux",
            make="Toyota",
            year=2019,
            price_zar=339900,
            is_valid=True,
        ),
        Listing(
            source_key="test",
            source_listing_id="ancient-1",
            url="https://example.com/ancient-1",
            category=Category.CAR,
            title="1998 Datsun 1400",
            make="Datsun",
            year=1998,
            price_zar=50000,
            is_valid=True,
        ),
    ])
    c = TestClient(create_app(r))
    resp = c.get("/?min_year=2015")
    assert resp.status_code == 200
    assert "Toyota" in resp.text
    assert "Datsun" not in resp.text


def test_min_year_prefilled_in_form() -> None:
    """The min_year input must be pre-filled when the filter is active."""
    r = InMemoryRepository()
    r.upsert_listings([
        Listing(
            source_key="test",
            source_listing_id="car-x",
            url="https://example.com/car-x",
            category=Category.CAR,
            title="2020 BMW 3 Series",
            make="BMW",
            year=2020,
            price_zar=400000,
            is_valid=True,
        ),
    ])
    c = TestClient(create_app(r))
    resp = c.get("/?min_year=2018")
    assert resp.status_code == 200
    assert 'value="2018"' in resp.text


def test_xss_escaping() -> None:
    """Titles with HTML special chars must be escaped, not rendered raw."""
    r = InMemoryRepository()
    r.upsert_listings([
        Listing(
            source_key="test",
            source_listing_id="xss-1",
            url="https://example.com/xss",
            category=Category.CAR,
            # No year/make/model so title is used as the card title line
            title="<script>x</script>",
            make=None,
            model=None,
            year=None,
            price_zar=100000,
            is_valid=True,
        )
    ])
    c = TestClient(create_app(r))
    resp = c.get("/")
    assert resp.status_code == 200
    # raw script tag must NOT appear in the response
    assert "<script>x</script>" not in resp.text
    # but the escaped form should be present
    assert "&lt;script&gt;" in resp.text
