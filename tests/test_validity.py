from datetime import datetime, timedelta, timezone

from dealfinder.models import Category, Listing
from dealfinder.validity import evaluate_validity


def _listing(**over):
    base = dict(
        source_key="webuycars",
        source_listing_id="1",
        url="https://x/1",
        category=Category.CAR,
        title="2019 Toyota Hilux",
        make="Toyota",
        model="Hilux",
        year=2019,
        price_zar=339900,
        town="Pretoria",
        image_urls=["https://img/1.jpg"],
    )
    base.update(over)
    return Listing(**base)


def test_complete_listing_is_valid(settings):
    result = evaluate_validity(_listing(), settings)
    assert result.is_valid is True
    assert result.flags == []


def test_missing_price_is_invalid(settings):
    result = evaluate_validity(_listing(price_zar=None), settings)
    assert result.is_valid is False
    assert "missing_price" in result.flags


def test_zero_price_flagged_as_implausible(settings):
    result = evaluate_validity(_listing(price_zar=0), settings)
    assert result.is_valid is False
    assert "price_implausible" in result.flags


def test_no_images_flagged_but_not_fatal(settings):
    result = evaluate_validity(_listing(image_urls=[]), settings)
    assert "missing_images" in result.flags
    # missing images is a quality warning, not fatal on its own
    assert result.is_valid is True


def test_missing_identity_is_invalid(settings):
    result = evaluate_validity(_listing(make=None, model=None, title=None), settings)
    assert result.is_valid is False
    assert "missing_identity" in result.flags


# ── freshness / stale tests ─────────────────────────────────────────────────

def test_very_old_listing_is_stale_and_invalid(settings):
    """A listing posted 3 years ago must be flagged 'stale' and be invalid."""
    old_date = datetime.now(timezone.utc) - timedelta(days=3 * 365)
    result = evaluate_validity(_listing(posted_at=old_date), settings)
    assert "stale" in result.flags
    assert result.is_valid is False


def test_recent_listing_is_not_stale(settings):
    """A listing posted today must not be flagged stale and must remain valid."""
    now = datetime.now(timezone.utc)
    result = evaluate_validity(_listing(posted_at=now), settings)
    assert "stale" not in result.flags
    assert result.is_valid is True


def test_no_posted_at_is_not_stale(settings):
    """A listing with posted_at=None must not be flagged stale (no crash)."""
    result = evaluate_validity(_listing(posted_at=None), settings)
    assert "stale" not in result.flags


def test_naive_posted_at_treated_as_utc(settings):
    """A naive (no tzinfo) posted_at that is very old must still be flagged stale."""
    old_naive = datetime.utcnow() - timedelta(days=3 * 365)
    result = evaluate_validity(_listing(posted_at=old_naive), settings)
    assert "stale" in result.flags
    assert result.is_valid is False
