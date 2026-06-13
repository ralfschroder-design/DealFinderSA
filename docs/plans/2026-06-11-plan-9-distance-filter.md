# DealFinderSA — Plan 9: Distance-from-Hartbeespoort radius filter

**Date:** 2026-06-11 · Builds on Plan 8 (detail pages now yield geo `lat`/`lng`). Status: in build.

## Goal
Honour a *core* line of the original brief — "base is Hartbeespoort, anything in a radius of 100 km" — now that listings carry real coordinates. Let a search restrict to listings within *N* km of home (config `home.lat/lng` = −25.7457, 27.8540).

## Method
- **New pure module `geo.py`:** `haversine_km(lat1, lng1, lat2, lng2) -> float` (great-circle, km) and `is_within_radius(lat, lng, home_lat, home_lng, radius_km) -> bool`.
- **Keep-unknown policy:** `is_within_radius` returns **True** when `lat`/`lng` is `None`. A radius filter must not hide listings we simply haven't geolocated yet (geo coverage grows ~`max_detail_fetches`/run). It only *excludes* listings whose **known** location is beyond the radius. Documented in the UI label.
- **`search_listings(..., within_km=None, home_lat=None, home_lng=None)`** on the Protocol + InMemory + Supabase repos. InMemory: in-loop filter. Supabase: post-filter after fetch (PostgREST can't do haversine inline; correct + simple at this corpus size). No-op if `within_km` or home coords absent.
- **Local UI (`web.py`):** load home from `load_settings()` in `create_app`; add a "Within km" field; pass `within_km` + home coords to the search. (Test harness — kept light.)

`geo.haversine_km` is also a **North-Star building block** (cross-area comparison / demand mapping in the agentic phase), so it lives in its own module, not buried in the repo.

## Data model
**No migration** — `lat`/`lng` already on the model + `listings` table (populated by Plan 8).

## Tasks
- **A:** `geo.py` + tests (distance to self = 0, symmetry, known CPT↔JHB ≈ 1265 km, Harties↔JHB ≈ 52 km, radius true/false, keep-unknown). TDD.
- **B:** `within_km` filter across the three repos + InMemory tests (far excluded, near kept, unknown kept, no-op without home). TDD.
- **C:** UI field + route param + light TestClient test. TDD.

## Deferred (future)
A Postgres/PostGIS distance function or RPC so the **Lovable** frontend can filter by radius server-side (this Python filter is the reference implementation + serves the local UI/CLI). Sort-by-distance. Per-area canvassing (group by region) for the agentic phase.
