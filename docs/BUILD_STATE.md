# DealFinderSA — Build State & Reference (living doc)

> **Purpose:** single source of truth for the build, written to survive context compaction.
> Search/reference this when resuming. Pair with `PROJECT.md` (status/log) and `docs/specs/` + `docs/plans/`.
> Last updated: 2026-06-11.

---

## 0. How to resume (cheat-sheet)
- Project root: `C:\Users\rschrode\Projects\DealFinderSA` (Windows). Python venv at `.venv`. Run python as `.\.venv\Scripts\python.exe`.
- Private GitHub repo: `https://github.com/ralfschroder-design/DealFinderSA` (branch `master`). `.env` is git-ignored (holds Supabase + SMTP secrets) — NEVER commit it.
- DB: Supabase (cloud Postgres). Creds in `.env` (`SUPABASE_URL`, `SUPABASE_KEY` = service_role).
- Run tests: `.\.venv\Scripts\python.exe -m pytest -q` (currently **193 passing**).
- CLI: `python -m dealfinder.cli {init-db|run-scrape|score|alert|serve}`.
- Network ops (scrape/push/serve) need the shell sandbox disabled.

---

## 1. Original brief & Vision / North Star
**Brief (Ralf):** an app to search vehicles, motorbikes, boats (+ jetskis); a scraper pulling SA listing sources for the latest deals; **listings MUST be valid**; flip/resell use-case; alerts on hot deals; base = Hartbeespoort, 100 km radius.

**North-star vision (Ralf, 2026-06-10):** make it big, smart, elegant, profitable. A **Gemini LLM as "master" orchestrator** with **Claude + OpenAI API keys**, driving **agents / workers / scrapers** that canvass different **areas of South Africa**, compare findings across areas, learn **which vehicles are in demand where**, and surface deals to **"swaai" (flip) quickly**. Strategy toggles between **quality-over-quantity** and **quantity-over-quality** as conditions warrant.
→ The current app is the **foundation** (reliable scrape→validate→dedup→score→alert + storage). The agentic/multi-LLM/demand-mapping layer is the evolution (see Roadmap §13).

---

## 2. Architecture principles (locked)
- **Runs from git** — scraper + scoring deploy straight from the repo; all state in Supabase + `.env` (no local-only state).
- **Real frontend = a Lovable app** on Supabase. The local FastAPI UI (`dealfinder serve`) is a **test harness only** — don't over-invest in it.
- **Local = testing**; production = git-deploy (cron) on a server.
- **Ethics/legal line:** scrape openly-served pages politely (grey-area, accepted), but **never circumvent anti-bot/security controls** (this is why WeBuyCars was dropped — see §7). No mass-harvest of personal data.
- **Process:** brainstorm → spec → plan → subagent-driven TDD with per-task spec+quality review. Frequent small commits. Honest about limitations.

---

## 3. Pipeline (what `run-scrape` does)
```
Gumtree (cars/bikes/boats/jetskis)
  → adapter fetch (resilient: per-page failures isolated)
  → normalise to Listing
  → compute fingerprint (price-independent vehicle key) + extract SA phone
  → enrich_posted_at (fetch detail pages for undated listings, capped; Plan 8: extracts make/year/mileage/province/geo/seller/desc + date)
  → validity gate (completeness + price sanity + freshness — stale listings FATALed)
  → record price_history (on change)
  → upsert to Supabase (dedup-safe batch)
  → run_scoring (market-median deal score)   [needs migration 003; skips gracefully if absent]
  → run_alerts (email new high-score deals)  [needs 003+004+SMTP; skips gracefully]
```

---

## 4. Module map (`src/dealfinder/`)
| File | Responsibility |
|---|---|
| `config.py` | `Settings` from `config/default.yaml` + `.env`. Models: Home, FetchCfg, ValidityCfg, SourceCfg (`fetch_detail`, `max_detail_fetches` — default 60), AlertsCfg. SMTP fields from env. |
| `models.py` | `Listing` (central model), enums `Category`(car/bike/boat/jetski)/`SellerType`/`ListingStatus`, `ValidityResult`, `RunStats`. Pydantic v2 (ignores extra fields → `Listing(**db_row)` is safe). |
| `fetch.py` | `Fetcher` — polite httpx client: rate-limit (min_interval), retry/backoff on 429/5xx + transport errors, User-Agent, injectable `sleep`. `get_json`/`get_text`. |
| `adapters/base.py` | `Adapter` ABC: `key/name/tier` + `fetch_listings(fetcher, settings) -> list[Listing]`. `enrich_posted_at(listings, repo, fetcher, settings)` no-op default (overridden by Gumtree). |
| `adapters/__init__.py` | `_ALL` registry + `build_enabled_adapters(settings)`. |
| `adapters/webuycars.py` | WeBuyCars adapter (JSON API). **Disabled** — blocked by proof-of-work anti-bot (see §7). |
| `adapters/gumtree.py` | **PRIMARY** source. HTML scrape of Gumtree category pages; per-listing data from the `/a-<cat>/<town>/<slug>/<id>` anchor + card (price `span.ad-price`, image `img[data-src]`). Global cross-category dedup; per-page failure isolation. Category→path map (cars `/s-cars-bakkies/v1c9077`, bikes `/s-motorcycles-scooters/v1c9027`, boats `/s-boats-watercraft/v1c9101`, jetski `/s-boats-jet-skis/v1c9102`); page N = path+`p{N}`. **Freshness v2:** `parse_posted_at(html)` reads `availabilityStarts` ISO from detail-page JSON (fallback: "N ago" creation-date text) → `Listing.posted_at`. `enrich_posted_at()` fetches detail pages only for undated listings (skips keys already in `repo.dated_keys()`), capped by `SourceCfg.max_detail_fetches`. **Plan 8 — `parse_detail(html)`** extracts the full record from each detail page (JSON-LD `Vehicle`/`Place`/`BreadcrumbList` + the HTML `div.attributes` table): real make/model/year, **mileage**, **province + geo lat/lng**, seller type, description; transmission/fuel/body/colour/drive → `raw`. `enrich_posted_at` now applies all of these (upgrade identity, fill the rest, price only when missing), not just the date; `cap` limits fetches. |
| `vehicles.py` | Known-makes lookup + `split_make_model(slug)` — handles multi-word makes (Land Rover, Harley-Davidson, Mercedes-Benz) for clean scoring cohorts. **`canonical_make(make)`** = single source of truth for brand aliasing (VW↔Volkswagen, Mercedes/Merc↔Mercedes-Benz, Harley↔Harley-Davidson, GWM↔Great Wall, Chev↔Chevrolet); applied at parse time so stored makes are canonical, and defensively in the scorer + fingerprint so the existing corpus collapses without a re-scrape. |
| `validity.py` | `evaluate_validity(listing, settings)` — flags: missing_price, price_implausible, missing_identity, missing_location (FATAL) + missing_images (warning). **Freshness: stale FATAL flag** — listing rejected if `posted_at` is older than `validity.max_listing_age_days` (default 120). Listings without a `posted_at` pass through (dated on next enrichment run). |
| `dedup`/`fingerprint.py` | `compute_fingerprint(listing)` = sha1 of (category, **canonical_make**, model, variant, year, mileage-band, province) — **excludes price** so same car at different prices clusters; canonical make so "VW Golf" and "Volkswagen Golf" cluster together. |
| `phone.py` | `extract_phone`/`normalize_phone` — SA numbers → `0XXXXXXXXX`. |
| `scoring.py` | `cohort_key` (category, **canonical_make**, model, year), `build_market_reference(listings)` (median + count per cohort), `score_listing(listing, ref)` → estimated_market_price, deal_delta_zar, deal_delta_pct, deal_score (0-100; 50=at market, 100=≥20% under), deal_confidence (low/med/high by cohort count). Cohort needs ≥2 to score. |
| `db.py` | `listing_to_row` (omits first_seen_at, sets last_seen_at), `_dedup_listings`, `ListingRepository` Protocol, `InMemoryRepository` (tests), `SupabaseRepository` (live). Methods: upsert_listings, record_run, record_price_if_changed, `search_listings` (filters + `min_score` + `min_year` + `sort` incl. "deal"), alerted_keys, record_alerts, `dated_keys()` (returns set of source_listing_ids that already have a `posted_at` — used to skip re-fetching detail pages). |
| `pipeline.py` | `run_pipeline(...)` (scrape→**enrich_posted_at**→validate→fingerprint→phone→price→upsert, per-source isolation) + `run_scoring(repo)`. |
| `alerts.py` | `select_new_deals(listings, alerted_keys, min_score)` + `run_alerts(repo, sender, settings)` + `format_digest`. |
| `email.py` | `EmailSender` — SMTP via smtplib, injectable factory, `is_configured`, `send(subject, body)`. (Module name `email.py` does NOT shadow stdlib under absolute imports — verified.) |
| `web.py` | `create_app(repo)` FastAPI search UI + `render_page` (escaped). Filters: category/make/q/price/town/valid-only/min_score/**min_year**; sort incl. "Best deal"; deal badges. **Test harness only.** |
| `cli.py` | argparse CLI: `init-db` (prints all migrations), `run-scrape` (scrape→score→alert, each resilient), `score`, `alert`, `serve --port`. |

---

## 5. Data model (Supabase / Postgres)
- **`listings`** — normalised listings. Key cols: source_key, source_listing_id (unique together), url, category, title, make, model, variant, year, price_zar, mileage_km, engine_hours, province, town, lat, lng, seller_type, seller_name, seller_phone, description, image_urls(jsonb), posted_at, first_seen_at, last_seen_at, status, is_valid, quality_flags(jsonb), raw(jsonb), fingerprint, estimated_market_price, deal_delta_zar, deal_delta_pct, deal_score, deal_confidence.
- **`price_history`** — source_key, source_listing_id, fingerprint, price_zar, observed_at (record-on-change).
- **`vehicle_clusters`** (view) — groups valid listings by fingerprint (count, min/max price, sources).
- **`alerts_sent`** — source_key+source_listing_id (unique), deal_score, sent_at (alert dedup).
- **`sources`**, **`runs`**, **`sources_health`** — registry / run log / per-source health.

### Migrations (`migrations/`) — apply in order via Supabase SQL editor (`dealfinder init-db` prints all):
- `001_core.sql` — sources, listings (core cols), runs, sources_health. **APPLIED.**
- `002_clustering.sql` — listings.fingerprint, price_history, vehicle_clusters view. **APPLIED.**
- `003_scoring.sql` — listings deal-score columns. **NOT applied (user-gated)** → blocks persisted scores/UI-sort/alerts.
- `004_alerts.sql` — alerts_sent table. **NOT applied (user-gated)** → blocks alert dedup.

---

## 6. Live state (2026-06-11)
- ~240 listings in Supabase; **84 dated** (have a `posted_at`), **10 flagged stale and excluded** (older than 120 days), **205 valid**. Dated coverage grows ~60 listings/run until the full corpus is enriched.
- Scoring proven **in-memory** on live data (found e.g. a Harley + a boat under market) but **not persisted** (003 pending). Only ~3 cohorts had ≥2 comparables → density is the limiter.
- Local UI runs at `http://127.0.0.1:8000` (via `dealfinder serve`, background process; restart after code changes). Min-year filter now available.
- 193 tests passing. All code pushed to GitHub.

---

## 7. Sources — status & lessons
- **Gumtree (PRIMARY, working):** openly-served HTML, no anti-bot challenge on listing pages or detail pages. Covers all 4 categories. Fragile to layout changes (golden-file fixture test). `posted_at` captured from detail-page `availabilityStarts` ISO (freshness v2, see §4).
- **WeBuyCars (DROPPED for automation):** inventory API (`appgateway.webuycars.co.za/website-elastic-backend/api/search`) requires an `x-proof-of-work-token` anti-bot. We will NOT circumvent it. **Possible future via official dealer API** — Ralf has a dealer/business account; pursue authorised access only.
- **cars.co.za:** Cloudflare-walled (403 challenge). **autotrader.co.za:** reachable but data behind a JS API + captcha. **automart:** reachable, needs the right URL. All need careful per-source work; check for anti-bot before building.

---

## 8. Config & secrets
- `config/default.yaml`: home (Hartbeespoort, lat -25.7457, lng 27.8540, radius_km 100), fetch (min_interval 2.5s, retries, UA), validity (min/max price), sources (gumtree enabled max_pages; webuycars disabled), alerts (min_score 80).
- `.env` (git-ignored): `SUPABASE_URL`, `SUPABASE_KEY` (service_role), `SMTP_HOST/PORT/USER/PASS`, `ALERT_EMAIL_TO`. Template = `.env.example`.

---

## 9. Go-live (to fully activate scoring + alerts)
1. Apply `003_scoring.sql` + `004_alerts.sql` in Supabase SQL editor (`dealfinder init-db` prints them).
2. Optionally set SMTP creds in `.env` for email alerts.
3. `dealfinder run-scrape` then does scrape→score→alert; UI sorts by best deal.
- Scheduling: `docs/deploy.md` (cron from git on a server; `scripts/run_scrape.sh`; Windows test task via `scripts/register_scheduled_task.ps1`).

---

## 10. Test suite (193)
Per-module: config, models, fetch (respx), webuycars (fixture), gumtree (fixture + resilience + dedup + **freshness v2**: `parse_posted_at`, `enrich_posted_at`, detail-page fixture), validity (**stale FATAL flag**), dedup/fingerprint, phone, db (mapping + repos + price + search + alerts + **dated_keys** + **min_year search**), pipeline (incl. scoring runner + enrich wiring), scoring, vehicles, web (TestClient + **min_year field**), cli, alerts, email, smoke. Golden-file HTML fixtures for adapters (no live calls in tests).

---

## 11. KNOWN ISSUES / TECH DEBT
- **STALE LISTINGS — RESOLVED (freshness v2, 2026-06-11):** `parse_posted_at()` extracts `availabilityStarts` ISO from each listing's detail page (fallback: "N ago" creation-date text); `enrich_posted_at()` fetches detail pages for undated listings (capped at 60/run, skips already-dated keys). The validity "stale" FATAL flag now rejects listings older than `max_listing_age_days` (default 120 days). Live: 10 stale listings caught and excluded on first run. _Caveat:_ very fresh scrapes may briefly contain undated listings until the next run dates them (coverage grows ~60/run until the corpus is fully enriched).
- **Scoring density:** few cohorts have ≥2 comparables at ~126 listings → few scored. Fixed over time by scheduled scraping (corpus grows) + more sources.
- **Make/model heuristic:** slug-based; good for cars/bikes with known makes, weak for boats/jetskis (slugs lack real brands) → poor boat cohorts. `vehicles.py` dictionary helps; extend it.
- ~~**VW vs Volkswagen** create separate cohorts~~ — **RESOLVED (2026-06-11):** `canonical_make()` in `vehicles.py` is the single alias map (VW↔Volkswagen, Mercedes/Merc↔Mercedes-Benz, Harley↔Harley-Davidson, GWM↔Great Wall, Chev↔Chevrolet); applied at parse time + defensively in the scorer/fingerprint. Extend the `_MAKE_ALIASES` dict to add more.
- ~~**mileage / GPS / seller-type** not captured~~ — **RESOLVED (Plan 8, 2026-06-11):** `parse_detail()` now extracts mileage, geo lat/lng, province, seller type (+ transmission/fuel/body/colour/drive into `raw`) from detail pages. Still deferred: *using* these in scoring (condition signals, mileage-aware cohorts) and the distance-from-Hartbeespoort filter (geo now available) — both need follow-up work; transmission/fuel as cohort dimensions need a migration. Note: only newly-fetched detail pages are enriched, so coverage grows ~`max_detail_fetches`/run (legacy listings back-fill as re-scraped).
- **WeBuyCars** only via official dealer API (PoW blocks scraping).
- **email.py** module name is unconventional (works under absolute imports) — could rename to `mailer.py` later.
- Local UI server must be manually restarted after code changes (no auto-reload).

---

## 12. Git / commit highlights
master @ `34e5da4`. Notable: Plan 1 skeleton (99c1809..5011679), Plan 2 dedup, Gumtree adapter (1ddc2d3) + dedup fix (eabd5e9) + resilience (433f10a), Plan 5 UI (e4750ec) + blank-filter fix (1be94cd), Plan 3 scoring (1924e01, 9274d6b), make/model dict (8b5fceb), Plan 4 alerts (995e535, 64b7dfa), Plan 7 deploy (66de015), **freshness v2** (0b15fe9), **min-year filter** (34e5da4), **make-alias normalisation** (canonical_make → tighter cohorts), **detail-field extraction** (Plan 8: mileage/geo/province/seller/etc. from detail pages).

---

## 13. Roadmap
**Immediate:**
1. ~~**Freshness fix**~~ — **DONE (2026-06-11):** `parse_posted_at` + `enrich_posted_at` on detail pages; stale FATAL flag; 10 listings caught on first live run. Coverage grows ~60/run.
2. ~~**Min model-year filter**~~ — **DONE (2026-06-11):** `search_listings(min_year=...)` + local UI field.
3. ~~**Make-alias cohorts + detail-field extraction**~~ — **DONE (2026-06-11):** `canonical_make` merges split cohorts; `parse_detail` pulls mileage/geo/province/seller/etc. from detail pages (verified on a live page). **Geo now enables a distance-from-Hartbeespoort filter** — strong next candidate.
4. Apply migrations 003/004 + SMTP → scoring/alerts live (user-gated).
5. **Lovable production frontend** (real UI) — Lovable app reading Supabase; needs read-only anon key + RLS policies (never the service_role key in-browser). I can supply Lovable prompts + the RLS SQL.

**Toward the North Star (agentic):**
4. **More sources / more areas** — additional adapters; parameterise scrapes by SA region/area (suburb/town/province) so "workers" canvass different areas.
5. **Demand mapping & analytics** — which makes/models sell fast / command premiums by area; price-trend + days-on-market signals (needs posted_at, now being captured); cross-area arbitrage (buy cheap area X → sell hot area Y).
6. **Condition-signal scoring** — capture mileage/year/seller; refine deal score + margin estimate (transport from Hartbeespoort, recon, fees).
7. **Agent/worker orchestration** — a coordinator (the "master") dispatching area-scoped scrape workers + analysis agents; pluggable LLMs (Gemini master, Claude/OpenAI workers) for parsing messy listings, judging deals, summarising. Keep deterministic core (scrape/validate/score) + LLM for judgment/summarisation. Strategy modes: quality-vs-quantity toggle.
8. Scam-risk scoring; image perceptual-hash dedup; saved-search "watches"; WhatsApp (if a compliant provider) — all previously deferred.

---

## 14. Conventions
- TDD; subagent-driven per-task with spec+quality review. Exact file paths. No placeholders.
- Commit/push only on Ralf's intent (he wants it on GitHub — keep it current). `.env` never committed (guard checks `git ls-files .env` before every push).
- South African English. Honest about trade-offs and limitations.
- No Confluence for this project (Ralf's instruction) — docs live here as Markdown.
