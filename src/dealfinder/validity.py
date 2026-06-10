from __future__ import annotations

from datetime import datetime, timezone

from dealfinder.config import Settings
from dealfinder.models import Listing, ValidityResult

# Flags that make a listing unusable (not alertable).
FATAL_FLAGS = {"missing_price", "price_implausible", "missing_identity", "missing_location", "stale"}


def evaluate_validity(listing: Listing, settings: Settings) -> ValidityResult:
    flags: list[str] = []

    if listing.price_zar is None:
        flags.append("missing_price")
    elif (
        listing.price_zar < settings.validity.min_price_zar
        or listing.price_zar > settings.validity.max_price_zar
    ):
        flags.append("price_implausible")

    if not (listing.make or listing.model or listing.title):
        flags.append("missing_identity")

    if not (listing.town or listing.province):
        flags.append("missing_location")

    if not listing.image_urls:
        flags.append("missing_images")

    if listing.posted_at is not None:
        posted = listing.posted_at
        # Treat naive datetimes as UTC so subtraction never raises.
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - posted).days
        if age_days > settings.validity.max_listing_age_days:
            flags.append("stale")

    is_valid = not (set(flags) & FATAL_FLAGS)
    return ValidityResult(is_valid=is_valid, flags=flags)
