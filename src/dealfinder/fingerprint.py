from __future__ import annotations

import hashlib
import re

from dealfinder.models import Listing
from dealfinder.vehicles import canonical_make


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _alnum(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _mileage_band(km: int | None) -> str:
    return "na" if km is None else str(km // 10000)  # 10,000 km bands


def compute_fingerprint(listing: Listing) -> str:
    """Deterministic same-vehicle key. Excludes price on purpose, so the same
    car listed at different prices clusters together."""
    parts = [
        listing.category.value,
        _norm(canonical_make(listing.make)),
        _norm(listing.model),
        _alnum(listing.variant),
        str(listing.year or ""),
        _mileage_band(listing.mileage_km),
        _norm(listing.province),
    ]
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
