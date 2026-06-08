from __future__ import annotations

import statistics

from dealfinder.models import Listing


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def cohort_key(listing: Listing) -> tuple | None:
    if not (listing.make and listing.model):
        return None
    return (listing.category.value, _norm(listing.make), _norm(listing.model), listing.year)


def build_market_reference(listings: list[Listing]) -> dict[tuple, dict]:
    buckets: dict[tuple, list[int]] = {}
    for item in listings:
        if not item.is_valid or item.price_zar is None:
            continue
        key = cohort_key(item)
        if key is None:
            continue
        buckets.setdefault(key, []).append(item.price_zar)
    return {
        key: {"median": statistics.median(prices), "count": len(prices)}
        for key, prices in buckets.items()
    }


def _confidence(count: int) -> str:
    if count >= 15:
        return "high"
    if count >= 5:
        return "medium"
    return "low"


def score_listing(listing: Listing, reference: dict[tuple, dict]) -> dict | None:
    """Return scoring fields for a listing, or None if it can't be scored."""
    if listing.price_zar is None:
        return None
    key = cohort_key(listing)
    if key is None:
        return None
    stat = reference.get(key)
    if not stat or stat["count"] < 2 or not stat["median"]:
        return None
    median = stat["median"]
    delta_zar = int(round(median - listing.price_zar))
    delta_pct = (median - listing.price_zar) / median
    score = max(0, min(100, int(round(50 + 250 * delta_pct))))
    return {
        "estimated_market_price": int(round(median)),
        "deal_delta_zar": delta_zar,
        "deal_delta_pct": round(delta_pct, 4),
        "deal_score": score,
        "deal_confidence": _confidence(stat["count"]),
    }
