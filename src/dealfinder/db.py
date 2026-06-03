from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from dealfinder.models import Listing, RunStats


def listing_to_row(listing: Listing) -> dict:
    """Map a Listing to a Supabase row. Omits first_seen_at so it is preserved on update."""
    data = listing.model_dump(mode="json", exclude={"raw"})
    data["raw"] = listing.raw
    data["last_seen_at"] = datetime.now(timezone.utc).isoformat()
    return data


class ListingRepository(Protocol):
    def upsert_listings(self, listings: list[Listing]) -> int: ...
    def record_run(self, run: RunStats) -> None: ...


class InMemoryRepository:
    """Test/dev repository. Keyed by (source_key, source_listing_id)."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], Listing] = {}
        self.runs: list[RunStats] = []

    def upsert_listings(self, listings: list[Listing]) -> int:
        for listing in listings:
            self._store[(listing.source_key, listing.source_listing_id)] = listing
        return len(listings)

    def record_run(self, run: RunStats) -> None:
        self.runs.append(run)

    def get(self, source_key: str, source_listing_id: str) -> Listing | None:
        return self._store.get((source_key, source_listing_id))

    def all(self) -> list[Listing]:
        return list(self._store.values())


class SupabaseRepository:
    """Real repository backed by Supabase (PostgREST)."""

    def __init__(self, url: str, key: str) -> None:
        from supabase import create_client

        self._client = create_client(url, key)

    def upsert_listings(self, listings: list[Listing]) -> int:
        if not listings:
            return 0
        rows = [listing_to_row(item) for item in listings]
        self._client.table("listings").upsert(
            rows, on_conflict="source_key,source_listing_id"
        ).execute()
        return len(rows)

    def record_run(self, run: RunStats) -> None:
        self._client.table("runs").insert(
            {
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "source_keys": run.source_keys,
                "fetched": run.fetched,
                "upserted": run.upserted,
                "invalid": run.invalid,
                "errors": run.errors,
            }
        ).execute()
