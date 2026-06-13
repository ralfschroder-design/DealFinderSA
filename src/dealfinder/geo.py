"""Great-circle distance helpers (pure, no I/O).

Used by the distance-from-home search filter, and a building block for the
North-Star agentic phase (comparing deals across South African areas).
"""
from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0088  # IUGG mean Earth radius


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres between two (lat, lng) points (degrees)."""
    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def is_within_radius(
    lat: float | None,
    lng: float | None,
    home_lat: float,
    home_lng: float,
    radius_km: float,
) -> bool:
    """True if ``(lat, lng)`` is within ``radius_km`` of home.

    Points with unknown coordinates (``lat`` or ``lng`` is ``None``) are treated
    as 'within' (kept), so a radius filter never hides listings we simply have
    not geolocated yet — it only excludes listings whose *known* location lies
    beyond the radius.
    """
    if lat is None or lng is None:
        return True
    return haversine_km(lat, lng, home_lat, home_lng) <= radius_km
