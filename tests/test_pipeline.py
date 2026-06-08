from dealfinder.adapters.base import Adapter
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
