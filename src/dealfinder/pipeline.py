from __future__ import annotations

from dealfinder.adapters.base import Adapter
from dealfinder.config import Settings
from dealfinder.db import ListingRepository
from dealfinder.fetch import Fetcher
from dealfinder.models import RunStats
from dealfinder.validity import evaluate_validity


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
            result = evaluate_validity(listing, settings)
            listing.is_valid = result.is_valid
            listing.quality_flags = result.flags
            if not result.is_valid:
                stats.invalid += 1

        stats.upserted += repo.upsert_listings(listings)

    repo.record_run(stats)
    return stats
