from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from dealfinder.models import Category, Listing, RunStats


def _dedup_listings(listings: list[Listing]) -> list[Listing]:
    """Collapse listings sharing (source_key, source_listing_id), keeping the last (freshest)."""
    by_key: dict[tuple[str, str], Listing] = {}
    for item in listings:
        by_key[(item.source_key, item.source_listing_id)] = item
    return list(by_key.values())


def listing_to_row(listing: Listing) -> dict:
    """Map a Listing to a Supabase row. Omits first_seen_at so it is preserved on update."""
    data = listing.model_dump(mode="json", exclude={"raw"})
    data["raw"] = listing.raw
    data["last_seen_at"] = datetime.now(timezone.utc).isoformat()
    return data


class ListingRepository(Protocol):
    def upsert_listings(self, listings: list[Listing]) -> int: ...
    def record_run(self, run: RunStats) -> None: ...
    def record_price_if_changed(self, listing: Listing) -> bool: ...
    def search_listings(
        self,
        *,
        category: Category | None = None,
        make: str | None = None,
        q: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        town: str | None = None,
        valid_only: bool = True,
        sort: str = "recent",
        limit: int = 200,
        min_score: int | None = None,
    ) -> list[Listing]: ...
    def alerted_keys(self) -> set[tuple[str, str]]: ...
    def record_alerts(self, listings: list[Listing]) -> int: ...


class InMemoryRepository:
    """Test/dev repository. Keyed by (source_key, source_listing_id)."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], Listing] = {}
        self.runs: list[RunStats] = []
        self.prices: list[dict] = []
        self._last_price: dict[tuple[str, str], int] = {}
        self.alerts: set[tuple[str, str]] = set()

    def upsert_listings(self, listings: list[Listing]) -> int:
        deduped = _dedup_listings(listings)
        for listing in deduped:
            self._store[(listing.source_key, listing.source_listing_id)] = listing
        return len(deduped)

    def record_run(self, run: RunStats) -> None:
        self.runs.append(run)

    def record_price_if_changed(self, listing: Listing) -> bool:
        if listing.price_zar is None:
            return False
        key = (listing.source_key, listing.source_listing_id)
        if self._last_price.get(key) == listing.price_zar:
            return False
        self._last_price[key] = listing.price_zar
        self.prices.append(
            {
                "source_key": listing.source_key,
                "source_listing_id": listing.source_listing_id,
                "fingerprint": listing.fingerprint,
                "price_zar": listing.price_zar,
            }
        )
        return True

    def get(self, source_key: str, source_listing_id: str) -> Listing | None:
        return self._store.get((source_key, source_listing_id))

    def all(self) -> list[Listing]:
        return list(self._store.values())

    def search_listings(
        self,
        *,
        category: Category | None = None,
        make: str | None = None,
        q: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        town: str | None = None,
        valid_only: bool = True,
        sort: str = "recent",
        limit: int = 200,
        min_score: int | None = None,
    ) -> list[Listing]:
        results: list[Listing] = []
        price_bound_active = min_price is not None or max_price is not None

        for listing in self._store.values():
            if valid_only and not listing.is_valid:
                continue
            if category is not None and listing.category != category:
                continue
            if make is not None and (
                listing.make is None
                or make.lower() not in listing.make.lower()
            ):
                continue
            if q is not None and (
                listing.title is None
                or q.lower() not in listing.title.lower()
            ):
                continue
            if price_bound_active and listing.price_zar is None:
                continue
            if min_price is not None and listing.price_zar is not None and listing.price_zar < min_price:
                continue
            if max_price is not None and listing.price_zar is not None and listing.price_zar > max_price:
                continue
            if town is not None and (
                listing.town is None
                or town.lower() not in listing.town.lower()
            ):
                continue
            if min_score is not None and (
                listing.deal_score is None or listing.deal_score < min_score
            ):
                continue
            results.append(listing)

        if sort == "price_asc":
            results.sort(key=lambda x: (x.price_zar is None, x.price_zar or 0))
        elif sort == "price_desc":
            results.sort(key=lambda x: (x.price_zar is None, -(x.price_zar or 0)))
        elif sort == "deal":
            results.sort(
                key=lambda l: (l.deal_score if l.deal_score is not None else -1),
                reverse=True,
            )
        # "recent" keeps insertion order (dict preserves insertion order in Python 3.7+)

        return results[:limit]

    def alerted_keys(self) -> set[tuple[str, str]]:
        return set(self.alerts)

    def record_alerts(self, listings: list[Listing]) -> int:
        added = 0
        for listing in listings:
            key = (listing.source_key, listing.source_listing_id)
            if key not in self.alerts:
                self.alerts.add(key)
                added += 1
        return added


class SupabaseRepository:
    """Real repository backed by Supabase (PostgREST)."""

    def __init__(self, url: str, key: str) -> None:
        from supabase import create_client

        self._client = create_client(url, key)

    def upsert_listings(self, listings: list[Listing]) -> int:
        deduped = _dedup_listings(listings)
        if not deduped:
            return 0
        rows = [listing_to_row(item) for item in deduped]
        self._client.table("listings").upsert(
            rows, on_conflict="source_key,source_listing_id"
        ).execute()
        return len(deduped)

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

    def record_price_if_changed(self, listing: Listing) -> bool:
        if listing.price_zar is None:
            return False
        resp = (
            self._client.table("price_history")
            .select("price_zar")
            .eq("source_key", listing.source_key)
            .eq("source_listing_id", listing.source_listing_id)
            .order("observed_at", desc=True)
            .limit(1)
            .execute()
        )
        last = resp.data[0]["price_zar"] if resp.data else None
        if last == listing.price_zar:
            return False
        self._client.table("price_history").insert(
            {
                "source_key": listing.source_key,
                "source_listing_id": listing.source_listing_id,
                "fingerprint": listing.fingerprint,
                "price_zar": listing.price_zar,
            }
        ).execute()
        return True

    def search_listings(
        self,
        *,
        category: Category | None = None,
        make: str | None = None,
        q: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        town: str | None = None,
        valid_only: bool = True,
        sort: str = "recent",
        limit: int = 200,
        min_score: int | None = None,
    ) -> list[Listing]:
        query = self._client.table("listings").select("*")
        if category is not None:
            query = query.eq("category", category.value)
        if make is not None:
            query = query.ilike("make", f"%{make}%")
        if q is not None:
            query = query.ilike("title", f"%{q}%")
        if min_price is not None:
            query = query.gte("price_zar", min_price)
        if max_price is not None:
            query = query.lte("price_zar", max_price)
        if town is not None:
            query = query.ilike("town", f"%{town}%")
        if valid_only:
            query = query.eq("is_valid", True)
        if min_score is not None:
            query = query.gte("deal_score", min_score)
        if sort == "price_asc":
            query = query.order("price_zar", desc=False)
        elif sort == "price_desc":
            query = query.order("price_zar", desc=True)
        elif sort == "deal":
            query = query.order("deal_score", desc=True)
        else:
            query = query.order("last_seen_at", desc=True)
        query = query.limit(limit)
        resp = query.execute()
        return [Listing(**row) for row in resp.data]

    def alerted_keys(self) -> set[tuple[str, str]]:
        resp = (
            self._client.table("alerts_sent")
            .select("source_key, source_listing_id")
            .execute()
        )
        return {(row["source_key"], row["source_listing_id"]) for row in resp.data}

    def record_alerts(self, listings: list[Listing]) -> int:
        if not listings:
            return 0
        rows = [
            {
                "source_key": l.source_key,
                "source_listing_id": l.source_listing_id,
                "deal_score": l.deal_score,
            }
            for l in listings
        ]
        self._client.table("alerts_sent").upsert(
            rows, on_conflict="source_key,source_listing_id"
        ).execute()
        return len(rows)
