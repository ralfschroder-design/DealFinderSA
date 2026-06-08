from __future__ import annotations

from dealfinder.adapters.base import Adapter
from dealfinder.config import Settings
from dealfinder.db import ListingRepository
from dealfinder.fetch import Fetcher
from dealfinder.models import RunStats
from dealfinder.fingerprint import compute_fingerprint
from dealfinder.phone import extract_phone
from dealfinder.validity import evaluate_validity
from dealfinder.scoring import build_market_reference, score_listing


def run_pipeline(
    *,
    adapters: list[Adapter],
    fetcher: Fetcher | None,
    repo: ListingRepository,
    settings: Settings,
) -> RunStats:
    stats = RunStats(source_keys=[a.key for a in adapters])

    for adapter in adapters:
        try:
            listings = adapter.fetch_listings(fetcher, settings)
        except Exception as exc:  # isolate per-source failures
            stats.errors.append(f"{adapter.key}: {exc}")
            continue

        for listing in listings:
            stats.fetched += 1
            listing.fingerprint = compute_fingerprint(listing)
            if not listing.seller_phone:
                listing.seller_phone = extract_phone(listing.description)
            result = evaluate_validity(listing, settings)
            listing.is_valid = result.is_valid
            listing.quality_flags = result.flags
            if not result.is_valid:
                stats.invalid += 1
            elif repo.record_price_if_changed(listing):
                stats.price_points += 1

        stats.upserted += repo.upsert_listings(listings)

    repo.record_run(stats)
    return stats


def run_scoring(repo: ListingRepository, *, limit: int = 10000) -> int:
    """Score all valid listings against the live-market median; persist scores. Returns count scored."""
    listings = repo.search_listings(valid_only=True, limit=limit)
    reference = build_market_reference(listings)
    scored = []
    for item in listings:
        result = score_listing(item, reference)
        if result is None:
            continue
        for field, value in result.items():
            setattr(item, field, value)
        scored.append(item)
    if scored:
        repo.upsert_listings(scored)
    return len(scored)
