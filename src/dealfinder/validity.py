from __future__ import annotations

from dealfinder.config import Settings
from dealfinder.models import Listing, ValidityResult

# Flags that make a listing unusable (not alertable).
FATAL_FLAGS = {"missing_price", "price_implausible", "missing_identity", "missing_location"}


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

    is_valid = not (set(flags) & FATAL_FLAGS)
    return ValidityResult(is_valid=is_valid, flags=flags)
