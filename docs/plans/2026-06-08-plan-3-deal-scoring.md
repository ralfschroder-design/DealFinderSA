# DealFinderSA — Plan 3: Deal Scoring

**Date:** 2026-06-08 · Builds on Plan 1 + 2 (live Gumtree data in Supabase). Status: in build.

## Goal
Flag **underpriced** listings by scoring each one against the live market, so the flipper sees the best deals first.

## Architecture context (per Ralf, 2026-06-08)
- Everything we build **runs from git** (the scraper/scoring is deployable straight from the repo; no local-only state — Supabase + `.env` already ensure this).
- The **real frontend will be a Lovable app** on Supabase. The local FastAPI page is a **test harness** to prove functionality — do not over-invest in it.
- **Local = testing** for now.

## v1 scope — honest to the data we have
Current Gumtree listings reliably have: category, make, model (best-effort), year (some), **price**, town. They mostly **lack** mileage, GPS/province, and seller type. So v1 scoring = **price vs. cohort market-median + sample-size confidence**. The richer "condition signals" from the spec (mileage-vs-expected, transport distance from Hartbeespoort, seller type) are **deferred** until adapters extract those fields — noted, not built now.

## Method
- **Cohort key** = `(category, make_norm, model_norm, year)` over **valid, priced** listings. `year=None` forms its own bucket. Listings missing make+model are not scored.
- **Market reference** per cohort: `estimated_market_price = median(prices)`, plus `count`, `p25`, `p75`.
- **Per listing** (only if its cohort has `count >= 2`):
  - `deal_delta_zar = estimated_market_price - price_zar` (positive = below market = good)
  - `deal_delta_pct = deal_delta_zar / estimated_market_price`
  - `deal_score = clamp(round(50 + 250 * deal_delta_pct), 0, 100)` → 50 = at market; ~75 = 10% under; 100 = ≥20% under; 0 = ≥20% over.
  - `deal_confidence` (text) from cohort `count`: `>=15` → "high", `5–14` → "medium", `2–4` → "low".
- Cohort `count < 2` → no score (fields left null), honest about thin data.

## Data model
Add to `Listing` + **migration `003_scoring.sql`** (columns on `listings`):
`estimated_market_price bigint`, `deal_delta_zar bigint`, `deal_delta_pct double precision`, `deal_score int`, `deal_confidence text`. Index `deal_score`.

## Runner + CLI
`scoring.py` (pure): `cohort_key`, `build_market_reference(listings)`, `score_listing(listing, ref)`.
`run_scoring(repo)`: read valid priced listings → build reference → score each → re-upsert (the dedup-safe `upsert_listings` writes the score fields back). New CLI: `dealfinder score`. Also chain it at the end of `run-scrape` so a scheduled git run scores automatically.

## UI (test harness)
Show a deal badge on each card (e.g. "12% under market · score 78 · medium"); add sort **"best deal"** (`deal_score desc`); optional `min_score` filter. Keep it light.

## Tasks
- **A:** Listing fields + migration 003 + `scoring.py` (pure) + tests.
- **B:** `run_scoring` + `dealfinder score` CLI + chain into run-scrape + UI surfacing + tests.
- **User-gated (live):** apply `003_scoring.sql` in Supabase (`dealfinder init-db` prints it), run `dealfinder score`, reload the UI.

## Deferred (future)
Condition signals (mileage/distance/seller), a stored `market_stats` table + price-trend history view, scam-risk scoring.
