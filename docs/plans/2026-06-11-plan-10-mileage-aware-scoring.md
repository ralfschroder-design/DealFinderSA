# DealFinderSA — Plan 10: Mileage-aware (condition) deal scoring

**Date:** 2026-06-11 · Builds on Plan 3 (price-vs-cohort scoring) + Plan 8 (mileage now captured). Status: in build.

## Goal
Make `deal_score` reflect **condition, not just price**. A bakkie that's cheap *because* it has 300 000 km isn't a real deal; a low-km car at market price is better than its price-only score says. Use the cohort's median mileage to nudge the score — honestly, only where the data supports it.

## Method (no migration — `deal_score` column already live via 003)
- **`build_market_reference`** also computes, per cohort, `mileage_median` + `mileage_count` from peers that have `mileage_km` (ignoring those that don't).
- **`score_listing`:** compute the price score as today (`50 + 250·price_delta_pct`). Then, **only if** the listing has `mileage_km` **and** the cohort has `mileage_count ≥ 2` and a positive `mileage_median`:
  - `m_delta = clamp((mileage_median − listing.mileage_km) / mileage_median, −1, +1)` (positive = fewer km than peers = better).
  - `deal_score = clamp(round(price_score + MILEAGE_WEIGHT · m_delta), 0, 100)`, with `MILEAGE_WEIGHT = 20` (so mileage moves the score at most ±20 points — price stays the dominant signal).
- `deal_delta_zar` / `deal_delta_pct` stay **pure price** (they describe the price gap); only `deal_score` becomes condition-adjusted (the holistic "how good a buy" number used for the best-deal sort).
- **No mileage data → behaviour is identical to today** (regression-safe; all existing scoring tests still pass). Boats/jetskis (no mileage) are unaffected.

## Tasks
- **A:** `build_market_reference` mileage stats + `score_listing` mileage adjustment + tests (reference includes mileage median; low-km scores above high-km at equal price; high-km discounts an otherwise-good price; bounded ±20; no-mileage unchanged). TDD.

## Deferred (needs decisions / more data)
- **Margin estimate** (resale − price − transport − recon − fees): needs cost assumptions from Ralf (R/km transport from Hartbeespoort — geo now gives distance — recon budget, fees). Not invented here.
- Mileage-vs-age plausibility flag (e.g. >40 000 km/yr = suspect). Engine-hours for boats/jetskis. Promoting transmission/fuel into cohorts (needs a migration). Surfacing mileage on UI cards (trivial follow-on).
