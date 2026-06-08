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
