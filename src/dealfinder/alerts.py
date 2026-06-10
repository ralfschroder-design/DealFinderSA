"""Alert selection logic and alert runner for DealFinderSA (Plan 4, Tasks A & B)."""
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


def format_digest(listings: list[Listing]) -> str:
    """Format a list of deal listings as a human-readable digest (one line per deal)."""
    lines: list[str] = []
    for listing in listings:
        score = listing.deal_score or 0
        year = listing.year or "?"
        make = listing.make or "?"
        model = listing.model or "?"
        price = f"R{listing.price_zar:,}" if listing.price_zar is not None else "R?"
        delta_pct = (
            f" ({listing.deal_delta_pct:+.1f}% under market)"
            if listing.deal_delta_pct is not None
            else ""
        )
        town = listing.town or "?"
        url = listing.url
        lines.append(f"{score}/100 · {year} {make} {model} · {price}{delta_pct} · {town} · {url}")
    return "\n".join(lines)


def run_alerts(repo, sender, settings) -> int:
    """Fetch new deals, send a digest email, and record alerted keys.

    Returns the number of alerts sent (0 if nothing qualifies or sender unconfigured).
    If the sender is not configured, alerts are NOT recorded so the backlog is preserved.
    """
    listings = repo.search_listings(valid_only=True, limit=10000)
    new = select_new_deals(listings, repo.alerted_keys(), settings.alerts.min_score)
    if not new:
        return 0
    if not sender.is_configured:
        return 0
    body = format_digest(new)
    sender.send(f"DealFinderSA: {len(new)} new deal(s)", body)
    repo.record_alerts(new)
    return len(new)
