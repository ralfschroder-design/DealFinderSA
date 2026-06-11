from datetime import datetime, timezone

from dealfinder.adapters.base import Adapter
from dealfinder.config import SourceCfg
from dealfinder.db import InMemoryRepository
from dealfinder.models import Category, Listing
from dealfinder.pipeline import run_pipeline


class FakeAdapter(Adapter):
    key = "fake"
    name = "Fake"
    tier = 1

    def __init__(self, listings):
        self._listings = listings

    def fetch_listings(self, fetcher, settings):
        return self._listings


def _listing(lid, price, town="Pretoria", images=("https://img/1.jpg")):
    return Listing(
        source_key="fake",
        source_listing_id=lid,
        url=f"https://x/{lid}",
        category=Category.CAR,
        title="2019 Toyota Hilux",
        make="Toyota",
        model="Hilux",
        year=2019,
        price_zar=price,
        town=town,
        image_urls=list(images) if isinstance(images, (list, tuple)) else [images],
    )


def test_pipeline_upserts_valid_marks_invalid(settings):
    good = _listing("1", 339900)
    bad = _listing("2", 0)  # implausible price -> invalid
    repo = InMemoryRepository()

    stats = run_pipeline(
        adapters=[FakeAdapter([good, bad])], fetcher=None, repo=repo, settings=settings
    )

    assert stats.fetched == 2
    assert stats.upserted == 2          # both stored
    assert stats.invalid == 1           # one marked invalid
    stored_bad = repo.get("fake", "2")
    assert stored_bad.is_valid is False
    assert "price_implausible" in stored_bad.quality_flags
    stored_good = repo.get("fake", "1")
    assert stored_good.is_valid is True
    assert len(repo.runs) == 1


def test_pipeline_isolates_failing_adapter(settings):
    class BoomAdapter(FakeAdapter):
        key = "boom"

        def fetch_listings(self, fetcher, settings):
            raise RuntimeError("source down")

    repo = InMemoryRepository()
    stats = run_pipeline(
        adapters=[BoomAdapter([]), FakeAdapter([_listing("1", 339900)])],
        fetcher=None,
        repo=repo,
        settings=settings,
    )
    # one adapter blew up, the other still produced a listing
    assert stats.upserted == 1
    assert any("boom" in e for e in stats.errors)


def test_pipeline_fingerprints_extracts_phone_records_price(settings):
    from dealfinder.db import InMemoryRepository
    from dealfinder.pipeline import run_pipeline

    listing = _listing("1", 339900)
    listing.description = "Mint condition. Call 082 123 4567 to view."
    listing.seller_phone = None
    repo = InMemoryRepository()

    stats = run_pipeline(adapters=[FakeAdapter([listing])], fetcher=None, repo=repo, settings=settings)

    stored = repo.get("fake", "1")
    assert stored.fingerprint is not None and len(stored.fingerprint) == 16
    assert stored.seller_phone == "0821234567"
    assert stats.price_points == 1
    assert len(repo.prices) == 1


def test_pipeline_same_vehicle_shares_fingerprint(settings):
    from dealfinder.db import InMemoryRepository
    from dealfinder.pipeline import run_pipeline

    a = _listing("1", 339900)
    b = _listing("2", 351000)  # same car attrs, different id + price
    repo = InMemoryRepository()

    run_pipeline(adapters=[FakeAdapter([a, b])], fetcher=None, repo=repo, settings=settings)

    assert repo.get("fake", "1").fingerprint == repo.get("fake", "2").fingerprint


# ---------------------------------------------------------------------------
# Pipeline enrichment wiring (fetch_detail / enrich_posted_at)
# ---------------------------------------------------------------------------

class EnrichableAdapter(FakeAdapter):
    """FakeAdapter whose enrich_posted_at sets a fixed posted_at on undated listings."""

    def __init__(self, listings, fixed_date=None):
        super().__init__(listings)
        self.fixed_date = fixed_date or datetime(2026, 4, 24, tzinfo=timezone.utc)
        self.enrich_calls: list = []

    def enrich_posted_at(self, fetcher, listings, *, cap=None, now=None):
        self.enrich_calls.append({"count": len(listings), "cap": cap})
        dated = 0
        for listing in listings:
            if listing.posted_at is None:
                listing.posted_at = self.fixed_date
                dated += 1
        return dated


class _DetailFetcher:
    """Minimal fetcher stub — never actually called in these wiring tests."""
    def get_text(self, url, **kwargs):
        return ""


def _settings_with_fetch_detail(base_settings, fetch_detail=True, max_detail_fetches=60):
    """Return a copy of settings with gumtree/fake source config that has fetch_detail enabled."""
    from dealfinder.config import Home, FetchCfg, ValidityCfg, Settings
    return Settings(
        home=base_settings.home,
        fetch=base_settings.fetch,
        validity=base_settings.validity,
        sources={
            "fake": SourceCfg(
                enabled=True,
                max_pages=1,
                fetch_detail=fetch_detail,
                max_detail_fetches=max_detail_fetches,
            )
        },
    )


def test_pipeline_enriches_posted_at_when_fetch_detail_enabled(settings):
    """Pipeline calls enrich_posted_at before validity when fetch_detail=True."""
    listing = _listing("e1", 339900)
    listing.posted_at = None

    adapter = EnrichableAdapter([listing])
    repo = InMemoryRepository()
    cfg = _settings_with_fetch_detail(settings)
    fetcher = _DetailFetcher()

    run_pipeline(adapters=[adapter], fetcher=fetcher, repo=repo, settings=cfg)

    # enrich_posted_at must have been called
    assert len(adapter.enrich_calls) == 1
    # posted_at must be set on the stored listing
    stored = repo.get("fake", "e1")
    assert stored.posted_at == datetime(2026, 4, 24, tzinfo=timezone.utc)


def test_pipeline_skips_enrich_when_fetch_detail_disabled(settings):
    """Pipeline must NOT call enrich_posted_at when fetch_detail=False."""
    listing = _listing("e2", 339900)
    listing.posted_at = None

    adapter = EnrichableAdapter([listing])
    repo = InMemoryRepository()
    cfg = _settings_with_fetch_detail(settings, fetch_detail=False)
    fetcher = _DetailFetcher()

    run_pipeline(adapters=[adapter], fetcher=fetcher, repo=repo, settings=cfg)

    assert len(adapter.enrich_calls) == 0


def test_pipeline_skips_enrich_when_fetcher_is_none(settings):
    """Pipeline must NOT call enrich_posted_at when fetcher is None."""
    listing = _listing("e3", 339900)
    listing.posted_at = None

    adapter = EnrichableAdapter([listing])
    repo = InMemoryRepository()
    cfg = _settings_with_fetch_detail(settings, fetch_detail=True)

    run_pipeline(adapters=[adapter], fetcher=None, repo=repo, settings=cfg)

    assert len(adapter.enrich_calls) == 0


def test_pipeline_passes_cap_to_enrich(settings):
    """Pipeline passes max_detail_fetches as cap to enrich_posted_at."""
    listings = [_listing(str(i), 339900) for i in range(10)]
    for l in listings:
        l.posted_at = None

    adapter = EnrichableAdapter(listings)
    repo = InMemoryRepository()
    cfg = _settings_with_fetch_detail(settings, max_detail_fetches=3)
    fetcher = _DetailFetcher()

    run_pipeline(adapters=[adapter], fetcher=fetcher, repo=repo, settings=cfg)

    assert adapter.enrich_calls[0]["cap"] == 3


def test_pipeline_skips_already_dated_in_repo(settings):
    """Listings whose (source_key, id) are in repo.dated_keys() must not be passed to enrich."""
    # Two undated listings — we'll pre-seed one into the repo as already dated
    l1 = _listing("already", 339900)
    l1.posted_at = None
    l2 = _listing("fresh", 339900)
    l2.posted_at = None

    adapter = EnrichableAdapter([l1, l2])
    repo = InMemoryRepository()

    # Pre-seed l1 as already dated in the repo
    from copy import deepcopy
    seeded = deepcopy(l1)
    seeded.posted_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repo.upsert_listings([seeded])

    cfg = _settings_with_fetch_detail(settings)
    fetcher = _DetailFetcher()

    run_pipeline(adapters=[adapter], fetcher=fetcher, repo=repo, settings=cfg)

    # Only l2 (fresh) should have been passed to enrich
    assert adapter.enrich_calls[0]["count"] == 1
