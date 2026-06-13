from __future__ import annotations

import statistics

from dealfinder.models import Listing
from dealfinder.vehicles import canonical_make


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def cohort_key(listing: Listing) -> tuple | None:
    if not (listing.make and listing.model):
        return None
    return (listing.category.value, _norm(canonical_make(listing.make)), _norm(listing.model), listing.year)


def build_market_reference(listings: list[Listing]) -> dict[tuple, dict]:
    price_buckets: dict[tuple, list[int]] = {}
    mileage_buckets: dict[tuple, list[int]] = {}
    for item in listings:
        if not item.is_valid or item.price_zar is None:
            continue
        key = cohort_key(item)
        if key is None:
            continue
        price_buckets.setdefault(key, []).append(item.price_zar)
        if item.mileage_km is not None:
            mileage_buckets.setdefault(key, []).append(item.mileage_km)
    reference: dict[tuple, dict] = {}
    for key, prices in price_buckets.items():
        entry: dict = {"median": statistics.median(prices), "count": len(prices)}
        mileages = mileage_buckets.get(key)
        if mileages:
            entry["mileage_median"] = statistics.median(mileages)
            entry["mileage_count"] = len(mileages)
        reference[key] = entry
    return reference


def _confidence(count: int) -> str:
    if count >= 15:
        return "high"
    if count >= 5:
        return "medium"
    return "low"


MILEAGE_WEIGHT = 20  # max ± points the cohort-relative mileage can move the score


def score_listing(listing: Listing, reference: dict[tuple, dict]) -> dict | None:
    """Return scoring fields for a listing, or None if it can't be scored.

    ``deal_score`` is the price score (50 = at market, 100 = ≥20% under) adjusted
    by a bounded mileage term **when the cohort has ≥2 mileaged peers**: fewer-
    than-peer kilometres lift the score, more-than-peer kilometres discount it
    (capped at ±``MILEAGE_WEIGHT``). ``deal_delta_zar`` / ``deal_delta_pct`` stay
    pure price. With no mileage data the score is identical to price-only.
    """
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
    price_score = 50 + 250 * delta_pct

    mileage_adj = 0.0
    mileage_median = stat.get("mileage_median")
    if (
        listing.mileage_km is not None
        and mileage_median
        and stat.get("mileage_count", 0) >= 2
    ):
        m_delta = (mileage_median - listing.mileage_km) / mileage_median
        m_delta = max(-1.0, min(1.0, m_delta))
        mileage_adj = MILEAGE_WEIGHT * m_delta

    score = max(0, min(100, int(round(price_score + mileage_adj))))
    return {
        "estimated_market_price": int(round(median)),
        "deal_delta_zar": delta_zar,
        "deal_delta_pct": round(delta_pct, 4),
        "deal_score": score,
        "deal_confidence": _confidence(stat["count"]),
    }
