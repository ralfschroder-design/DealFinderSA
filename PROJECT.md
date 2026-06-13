# Project: DealFinderSA
**Created:** 2026-06-02
**Status:** Active

---

## Goal & Scope
A personal **vehicle-flipping radar** for the Hartbeespoort area (100 km radius). It scrapes
South African listing sources (and, best-effort, social marketplaces) for **cars, motorbikes,
boats and jetskis**; normalises and **validates** every listing; **scores** them against the
live market to surface underpriced deals; and **emails** an alert whenever a saved watch matches
a high-scoring, valid listing.

Scrapers run **locally on Ralf's Windows PC** (scheduled, with catch-up on startup). Data lives
in **Supabase (cloud Postgres)** and a **hosted web UI** lets Ralf browse/triage on phone or
desktop. The project folder is self-contained and portable (all code/config/docs in-folder;
external services referenced via `.env`).

- **In scope (v1, built in layers):** Tier-1 source adapters, validity engine, dedup/clustering,
  market-value + condition scoring, watches, email alerts, hosted search UI.
- **Best-effort:** Tier-2 social sources (Facebook Marketplace / Instagram) — isolated, expected
  to break often, never allowed to corrupt data validity.
- **Out of scope (for now):** WhatsApp alerts, paid pricing data, multi-user, native mobile app,
  auto-contacting/bidding on sellers.

## Architecture Direction
Three principles locked 2026-06-08:
- Everything **runs from git** — scraper and scoring are deployable straight from the repo; no local-only state (Supabase + `.env` ensure this).
- The **real frontend will be a Lovable app** on Supabase. The local FastAPI UI (`dealfinder serve`) is a **test harness only** — do not over-invest in it.
- **Local = testing** for now; production deployment is git-based.

## Progress Log
| Date | What was done |
|------|--------------|
| 2026-06-02 | Brainstormed requirements and locked the design. Wrote design spec (`docs/specs/2026-06-02-dealfindersa-design.md`). Key decisions: flip use-case; cars+bikes+boats+jetskis; max-coverage sources (Tier-1 reliable + Tier-2 best-effort); scheduled scrape + hot-deal alerts; local Python scraper on Windows (portable); Supabase cloud DB + hosted UI; market-compare + condition scoring; **email** alerts (switched from WhatsApp); Hartbeespoort + 100 km default; docs in Markdown, no Confluence. |
| 2026-06-02 | Wrote **Plan 1 — walking skeleton** (`docs/plans/2026-06-02-plan-1-walking-skeleton.md`). Chose **WeBuyCars** as the primary first source (cars/bakkies, via its JSON inventory API); **Gumtree** is the fast-follow for bikes/boats/jetskis. Updated spec Tier-1 list accordingly. Plan covers: package scaffold, config, Listing model, polite fetch layer, WeBuyCars adapter, validity engine, Supabase schema + repository, pipeline + CLI — TDD, 9 tasks. |
| 2026-06-04 | Implemented Plan 1 (walking skeleton), Tasks 1-8, via subagent-driven development with per-task spec + quality review. Package `dealfinder`: config, Listing model, polite fetch layer, WeBuyCars adapter (fixture-driven), validity engine, Supabase schema + repository, pipeline + CLI. 19 tests passing. Commits 99c1809..5011679 on branch master. README added. Live WeBuyCars API reconciliation + real Supabase scrape remain user-gated (see README go-live checklist). |
| 2026-06-08 | Implemented **Plan 2 — dedup & clustering** (`docs/plans/2026-06-04-plan-2-dedup-clustering.md`), Tasks 1-6 via subagent-driven development with per-task review. Added: price-independent vehicle `fingerprint`, SA phone extraction, `price_history` (record-on-change) + `vehicle_clusters` view, wired into the pipeline. 36 tests passing. Image pHash + transitive phone-merge deferred. New migration `002_clustering.sql` is user-gated (apply in Supabase during go-live). |
| 2026-06-08 | **Gumtree becomes the primary source** (cars/bikes/boats/jetskis) scraping openly-served HTML. WeBuyCars dropped for automation — its inventory API is protected by a proof-of-work anti-bot; remains a future option only via an official dealer API (Ralf has a dealer account). Live data: ~126 listings in Supabase across all 4 categories; scrape is resilient (per-page failures isolated). |
| 2026-06-08 | Implemented **Plan 3 — deal scoring** (`docs/plans/2026-06-08-plan-3-deal-scoring.md`): price-vs-cohort-median + confidence model; `dealfinder score` CLI; auto-runs at end of `run-scrape` (skips gracefully if migration 003 not applied). Scoring proven in-memory on live data. Make/model parsing uses a known-makes dictionary (`src/dealfinder/vehicles.py`) for clean cohorts (Land Rover, Harley-Davidson, etc.). Local FastAPI search UI (`dealfinder serve`) with filters, "Best deal" sort, deal badges — test harness only. 100 tests passing. All code pushed to private GitHub (`ralfschroder-design/DealFinderSA`). |
| 2026-06-10 | **Plan 7 — scheduling + run-from-git deploy docs.** Created `docs/deploy.md` (one-time setup, scheduled command, Linux/cron production path, Windows Task Scheduler local-testing path, politeness guidance). Created `scripts/run_scrape.sh` (cron wrapper, no activate needed). Created `scripts/register_scheduled_task.ps1` (idempotent Windows Task Scheduler registration, SupportsShouldProcess, -WhatIf safe). No core code changes; 137 tests still passing. |
| 2026-06-11 | **Freshness v2 (detail-page dating) — DONE.** `parse_posted_at()` reads `availabilityStarts` ISO from Gumtree detail pages (fallback: "N ago" creation-date text) → `Listing.posted_at`. `enrich_posted_at()` fetches detail pages for undated listings (capped at `max_detail_fetches`=60/run, skipping already-dated keys via `dated_keys()`), wired into `run_pipeline` before validity. Stale FATAL flag now active (`max_listing_age_days`=120). Live: 240 listings, 84 dated, 10 stale excluded, 205 valid. **Min model-year filter — DONE.** `search_listings(min_year=...)` in Protocol + InMemory + Supabase repos; "Min year" field in local web UI. 170 tests passing. Commits: `0b15fe9` (freshness v2), `34e5da4` (min-year). |
| 2026-06-11 | **Cohort quality — make-alias normalisation.** Added `canonical_make()` in `src/dealfinder/vehicles.py` as the single source of truth for brand aliasing (VW↔Volkswagen, Mercedes/Merc↔Mercedes-Benz, Harley↔Harley-Davidson, GWM↔Great Wall, Chev↔Chevrolet). Applied at parse time (`split_make_model` now emits canonical makes) **and** defensively in `scoring.cohort_key` + `compute_fingerprint`, so split cohorts in the **existing** corpus collapse without a re-scrape. Directly attacks the scoring-density limiter — more listings reach the ≥2-comparable threshold. TDD; **182 tests passing** (+12). |
| 2026-06-11 | **Plan 8 — detail-page field extraction.** New `parse_detail()` in `src/dealfinder/adapters/gumtree.py` reads each listing's detail page (already fetched for dating) and extracts the full record from the JSON-LD (`Vehicle`/`Place`/`BreadcrumbList`) + the HTML attributes table: real make/model/year, **mileage_km**, **province + geo lat/lng**, **seller type**, description (+ transmission/fuel/body/colour/drive into `raw`). `enrich_posted_at` broadened to apply all of these. **No migration** (all fields already on the model/table). Verified on a live page (Audi RS5 → mileage 117 000, geo, Gauteng, Dealer). Unlocks the 100 km-from-Hartbeespoort radius and future condition-signal scoring. TDD; **193 tests passing** (+11). Plan: `docs/plans/2026-06-11-plan-8-detail-field-extraction.md`. |
| 2026-06-11 | **Plan 9 — distance-from-Hartbeespoort radius filter.** New pure `src/dealfinder/geo.py` (`haversine_km`, `is_within_radius` with keep-unknown-location policy). `search_listings(within_km=, home_lat=, home_lng=)` across Protocol/InMemory/Supabase; "Within km of Hartbeespoort" field in the local UI (home loaded from config). Honours the original brief's 100 km radius now that Plan 8 captures geo. No migration. TDD; **205 tests passing** (+12). Plan: `docs/plans/2026-06-11-plan-9-distance-filter.md`. _Note:_ Lovable frontend will need an SQL/RPC radius equivalent (this is the reference impl). |

## Key Files & Paths
| Path / URL | Purpose |
|-----------|---------|
| `docs/specs/2026-06-02-dealfindersa-design.md` | Approved design spec (authoritative) |
| `PROJECT.md` | This file — status, log, next steps |
| `CLAUDE.md` | Session bootstrap instructions |
| `docs/plans/2026-06-02-plan-1-walking-skeleton.md` | Plan 1 — walking skeleton (step-by-step build) |
| `README.md` | Setup, usage, and go-live checklist |
| `docs/plans/2026-06-04-plan-2-dedup-clustering.md` | Plan 2 — dedup & clustering (step-by-step build) |
| `docs/plans/2026-06-08-plan-3-deal-scoring.md` | Plan 3 — deal scoring design and task breakdown |
| `src/dealfinder/adapters/gumtree.py` | Gumtree adapter — primary scrape source (HTML); `parse_detail()` extracts full detail-page record (Plan 8) |
| `docs/plans/2026-06-11-plan-8-detail-field-extraction.md` | Plan 8 — detail-page field extraction (mileage, geo, province, seller) |
| `src/dealfinder/geo.py` | Great-circle distance + radius check (distance-from-home filter; North-Star building block) |
| `docs/plans/2026-06-11-plan-9-distance-filter.md` | Plan 9 — distance-from-Hartbeespoort radius filter |
| `src/dealfinder/scoring.py` | Deal scoring logic (price-vs-cohort-median, confidence) |
| `src/dealfinder/vehicles.py` | Known-makes dictionary for clean make/model cohort parsing |
| `src/dealfinder/web.py` | Local FastAPI search UI (test harness only) |
| `docs/deploy.md` | Deploy + scheduling guide (one-time setup, cron, Windows Task Scheduler) |
| `scripts/run_scrape.sh` | Linux/cron wrapper — production scheduled run |
| `scripts/register_scheduled_task.ps1` | Windows Task Scheduler registration — local testing only |
| `https://github.com/ralfschroder-design/DealFinderSA` | Private GitHub repo (all code) |

## Open Questions & Blockers
- [ ] **Migration 003 pending** — `003_scoring.sql` must be applied in Supabase to persist scores, show them in the UI, and enable deal-score alerts. This is the immediate live-scoring unlock.
- [ ] **SMTP credentials needed** for email alerts (Plan 4). Gmail app password recommended; Office 365 may be locked down by the Sun International tenant.
- [ ] **Data density** — cohort scoring quality improves as scheduled scraping accumulates more listings over time.
- [ ] **WeBuyCars** — only viable via an official dealer API (PoW anti-bot blocks automation). Ralf has a dealer account; pursue this as a future Tier-1 enhancement.
- [ ] Resale/cost assumptions for margin estimate (transport, recon, fees) — set sensible defaults when condition scoring is built (deferred).

## Next Steps
1. **Apply `003_scoring.sql`** in the Supabase SQL editor — unlocks persisted deal scores, score display in the local UI, and enables deal-score alerts.
2. **Plan 4 — email alerts** — watch model + SMTP dispatch when a high-scoring listing matches a saved watch.
3. ~~**Plan 7 — scheduling (git-deploy)**~~ — **DONE 2026-06-10**: `docs/deploy.md`, `scripts/run_scrape.sh`, `scripts/register_scheduled_task.ps1` created. Deploy and schedule docs complete.
4. ~~**Freshness v2 (stale listing exclusion)**~~ — **DONE 2026-06-11**: detail-page dating + stale FATAL flag; 10 listings caught live.
5. ~~**Min model-year filter**~~ — **DONE 2026-06-11**: `search_listings(min_year=...)` + local UI field.
6. ~~**Distance-from-Hartbeespoort filter**~~ — **DONE 2026-06-11 (Plan 9):** `geo.py` haversine + `search_listings(within_km=…)` + "Within km" UI field. Next geo step: a Supabase SQL/RPC radius function so the Lovable frontend can filter server-side.
7. **Make-alias + detail fields, keep mining** — promote transmission/fuel to first-class cohort dimensions (needs a migration); use mileage for condition-aware scoring.
8. **Lovable production frontend** — production search UI on Supabase (replaces the local FastAPI test harness). This is the next major build item once alerts are live.
7. **More sources** — AutoTrader, Cars.co.za, AutoMart; WeBuyCars via official dealer API when ready.
