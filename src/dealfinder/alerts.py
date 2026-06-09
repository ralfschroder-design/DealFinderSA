"""Alert selection logic for DealFinderSA (Plan 4, Task A)."""
from __future__ import annotations

from dealfinder.models import Listing


def select_new_deals(
    listings: list[Listing],
    alerted_keys: set[tuple[str, str]],
    min_score: int,
) -> list[Listing]:
    """Return valid listings with deal_score >= min_score that haven't been alerted yet.

    Results are sorted descending by deal_score.
    """
    out = [
        l for l in listings
        if l.is_valid
        and l.deal_score is not None
        and l.deal_score >= min_score
        and (l.source_key, l.source_listing_id) not in alerted_keys
    ]
    out.sort(key=lambda l: l.deal_score, reverse=True)  # type: ignore[arg-type]
    return out
