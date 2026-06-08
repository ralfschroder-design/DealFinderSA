# DealFinderSA — Design Spec

**Date:** 2026-06-02
**Status:** Approved (pending written-spec review)
**Owner:** Ralf Schröder
**Type:** Personal project — vehicle-flipping deal radar

---

## 1. Summary

DealFinderSA is a personal **vehicle-flipping radar**. Scrapers run on Ralf's Windows PC and push
normalised listings into a cloud database; a **validity engine** discards junk, dead and scam
listings; a **scoring engine** flags underpriced cars, motorbikes, boats and jetskis against the
live market; and **email alerts** fire when a saved watch matches a high-scoring, valid listing.
Ralf browses and triages from a **hosted web UI** on desktop or phone.

**Primary goal:** surface genuinely underpriced, *valid* listings within ~100 km of Hartbeespoort
fast enough to act on them, and never waste time on dead or fake listings.

---

## 2. Decisions locked (from brainstorm, 2026-06-02)

| Decision | Choice |
|---|---|
| Use-case | Buy & resell (flip) — arbitrage / margin focus |
| Vehicle scope | Cars, motorbikes, boats **and jetskis** |
| Sources | Max coverage: Tier-1 (reliable) + Tier-2 social (best-effort) |
| Freshness | Scheduled re-scrapes + **alerts on hot deals** |
| Compute | **Local** Python scraper on Windows PC; Task Scheduler; catch-up on startup; portable |
| Database | **Supabase** (cloud Postgres) |
| UI | Hosted web UI (Lovable + Supabase) — phone + desktop |
| Scoring | **Market compare + condition signals** |
| Alerts | **Email (SMTP)** — switched from WhatsApp |
| Location | **Hartbeespoort, 100 km radius** (configurable) |
| Docs | Markdown in-folder; **no Confluence** |
| Name | DealFinderSA; self-contained, portable folder |

---

## 3. Architecture

```
  YOUR PC (Windows)                           CLOUD                          YOU
 ┌───────────────────────┐         ┌─────────────────────────┐      ┌────────────────┐
 │ Scheduler (Task Sched) │        │  Supabase (Postgres)     │      │ Web UI         │
 │   every ~30–60 min     │        │  • listings + clusters   │◄────►│ (phone+desktop)│
 │         │              │        │  • price history         │      └────────────────┘
 │         ▼              │ upsert │  • market stats          │
 │  Scrape pipeline ──────┼──────► │  • watches / alerts_sent │      ┌────────────────┐
 │  fetch→normalise→dedup │        │  • sources_health / runs │─────►│ Email (SMTP)   │
 │  →validate→score       │        │                          │alert │  hot-deal pings │
 │   └ adapters (per site)│        └─────────────────────────┘      └────────────────┘
 └───────────────────────┘
```

**Principles**
- **Isolation:** every component (adapters, validity, dedup, scoring, alerts) is independent with a
  clear interface. One broken source never stops the rest.
- **Best-effort sources degrade gracefully:** Tier-2 (social) failures are logged, surfaced in the
  UI, and never block a run or corrupt data.
- **Portability:** all code/config/docs in the folder; external services via `.env`. Same code
  lifts onto a cheap always-on cloud box later (Task Scheduler → cron) with near-zero change.
- **Catch-up on startup:** if the PC was asleep, the first run after boot back-fills the gap.

---

## 4. Components

### 4.1 Source adapters (plug-in, tiered)
Each source implements one small interface so adding/removing sources never touches the core:
`search(criteria) → raw results` · `fetch_detail(url) → raw detail` · `parse(raw) → Listing` ·
plus metadata (rate limits, whether JS/Playwright is needed, legal posture).

- **Tier 1 — structured & reliable (built first):** **WeBuyCars.co.za — primary first build target**
  (JSON inventory API; cars/bakkies only), then AutoTrader.co.za, Cars.co.za, Gumtree SA, AutoMart,
  + bike/boat/jetski sources (e.g. Gumtree marine, JunkMail, marine/bike dealer sites). Because
  WeBuyCars is cars-only, **Gumtree** (all four categories) is the immediate fast-follow. These carry the app.
- **Tier 2 — best-effort & fragile:** Facebook Marketplace / groups, Instagram. Isolated; may need
  a logged-in browser session; **expected to break often**; flagged in UI; never corrupts data.
- **Health tracking:** each adapter records last-run / last-success / count / errors → `sources_health`.
- **Tech:** `httpx` for simple HTML/JSON; **Playwright** for JS-heavy/anti-bot sites. A shared
  polite-fetch layer handles rate limits, randomised delays, retries with backoff, and caching.

### 4.2 Validity engine — the "MUST be valid" core
A listing becomes **alertable** only if it clears every gate. Failures are flagged (with reason),
not silently dropped, so the UI can explain why something was excluded.

- **Live check** — re-fetch URL on a sweep; `404` / removed / "sold" markers → mark sold, drop from
  active. *Never chase a dead listing.*
- **Completeness** — must have price, ≥1 image, a location, and identifiable make/model/year.
- **Price sanity** — reject placeholders (R1, R123 456) and impossible prices for the model; genuine
  outliers are flagged, not deleted.
- **Scam heuristics** → `scam_risk` score from: too-good-to-be-true price; stock/stolen images
  (perceptual-hash duplicates across unrelated listings); classic scam text ("I'm overseas",
  "courier", "deposit first"); brand-new/no-history seller; location mismatch. High risk =
  **quarantined, never alerted**.
- **Freshness** — stale listings demoted in ranking.

### 4.3 Dedup / vehicle clustering
Group the same vehicle (cross-posted or reposted) into one **cluster** so it's seen once:
- Exact: same `source` + `source_listing_id`.
- Near-dup: fingerprint of (make, model, year, mileage band, price band, location) + **image pHash**
  + **phone number** extracted from the description (a strong signal in SA classifieds).
- UI shows one card with "also listed on Gumtree, Marketplace …".

### 4.4 Market value + deal scoring
- Build a **rolling market reference from the corpus itself**: per (category, make, model, year band,
  mileage band) compute a robust median / p25 / p75 of *current* prices (trimmed to ignore outliers)
  → `market_stats`.
- **Deal score (0–100)** = how far below expected the asking price sits, adjusted by **condition
  signals**: mileage-vs-expected-for-year, listing age, seller type (private vs dealer), and
  distance/transport cost from Hartbeespoort. Each score carries a **confidence** from sample size,
  so thin-data models don't false-alarm.
- Outputs per listing: `estimated_market_price`, `deal_delta_zar`, `deal_delta_pct`, `deal_score`,
  `deal_confidence`, and an **estimated margin** using configurable cost assumptions (transport,
  recon, fees).
- **Cold-start honesty:** early scores are rough (wider bands) and sharpen as the database fills.

### 4.5 Watches + email alerts
- A **Watch** = saved search: category, make/model, year & price range, max mileage / engine hours,
  radius from home, **min deal score**.
- An alert fires when a listing **newly** matches a watch **and** clears validity **and** beats the
  score threshold. `alerts_sent` prevents repeat pings for the same listing+watch.
- **Email (SMTP):** message carries photo, title, price, est. market, deal score, location and a
  tap-through link. Batched/throttled per run (or a digest when many) so it's never spammy.
- *Config:* SMTP host/user/app-password in `.env`. Gmail app password recommended; Office 365 may be
  restricted by the Sun International tenant.

### 4.6 Web UI (hosted, reads Supabase)
Search & filter · ranked **Deals feed** · listing detail (images, market comparison, deal score,
validity badges, "also listed on", live status, seller contact) · **Watches** manager ·
**price-history chart** per cluster · **Source health**. Supabase Auth (single user: Ralf).

---

## 5. Data model (Supabase / Postgres)

| Table | Purpose / key columns |
|---|---|
| `sources` | Registry: `key`, `name`, `tier`, `enabled`, `base_url`, `legal_notes` |
| `listings` | Normalised listing: identity (`source_key`, `source_listing_id`, `url`), `category`, `make`, `model`, `variant`, `year`, `price_zar`, `mileage_km`, `engine_hours`, `province`, `town`, `lat`, `lng`, `seller_type`, `seller_name`, `seller_phone`, `description`, `posted_at`, `first_seen_at`, `last_seen_at`, `status`, `cluster_id`, `fingerprint`, validity (`scam_risk`, `quality_flags`), scoring (`estimated_market_price`, `deal_delta_zar`, `deal_delta_pct`, `deal_score`, `deal_confidence`), `raw` (jsonb) |
| `listing_images` | `listing_id`, `url`, `is_primary`, `cached_url`, `phash` |
| `clusters` | Deduped vehicle: `category`, `make`, `model`, `year`, `canonical_listing_id`, `member_count`, `min_price` |
| `price_history` | `cluster_id`/`listing_id`, `price_zar`, `observed_at` |
| `market_stats` | Reference: `category`, `make`, `model`, `year_band`, `mileage_band`, `sample_size`, `median_price`, `p25`, `p75`, `updated_at` |
| `watches` | Saved search + thresholds (incl. `radius_km`, `min_deal_score`, `enabled`) |
| `alerts_sent` | Dedup: `watch_id`, `listing_id`, `channel`, `sent_at` |
| `sources_health` | `source_key`, `last_run_at`, `last_success_at`, `listings_found`, `errors`, `status` |
| `runs` | Pipeline run log: timings, sources run, new/updated counts, alerts sent |

Images: store URLs, and **cache the primary image** to Supabase storage so sold-listing comps
survive deletion. `seller_phone` is PII used for dedup — store with care; a personal-use tool, but
keep it out of any future shared/exported views.

---

## 6. Tech stack & repo layout

**Stack:** Python 3.12 · `httpx` + **Playwright** · Pydantic models · pipeline runner driven by
Windows Task Scheduler · Supabase (Postgres + Auth + Storage) · UI in **Lovable + Supabase** (can be
synced to the repo via Lovable's GitHub integration for portability). Secrets in `.env`.

```
DealFinderSA/
├─ PROJECT.md
├─ CLAUDE.md
├─ README.md
├─ .env.example
├─ .gitignore
├─ pyproject.toml            # or requirements.txt
├─ config/
│  └─ default.yaml           # home lat/lng, radius_km, cost assumptions, schedule
├─ docs/
│  ├─ specs/2026-06-02-dealfindersa-design.md
│  └─ setup/                 # Supabase, SMTP, Task Scheduler how-tos
├─ src/dealfinder/
│  ├─ adapters/              # base.py + one module per source
│  ├─ fetch/                 # polite fetch layer (httpx + playwright)
│  ├─ normalize/
│  ├─ dedup/
│  ├─ validity/
│  ├─ scoring/
│  ├─ alerts/                # email (SMTP) sender
│  ├─ db/                    # supabase client + access layer
│  ├─ pipeline/              # orchestrates a run
│  └─ cli.py                 # run-scrape, revalidate, init-db, etc.
├─ migrations/               # SQL for Supabase tables
├─ scripts/                  # Task Scheduler setup, helpers
├─ ui/                       # Lovable/React app (or GitHub-synced from Lovable)
└─ tests/
   ├─ fixtures/              # saved HTML for golden-file parsing tests
   └─ ...
```

**Configuration / `.env`:** `SUPABASE_URL`, `SUPABASE_KEY`, `SMTP_HOST`, `SMTP_USER`,
`SMTP_PASS`, `ALERT_EMAIL_TO`. Non-secret tunables (home location, radius, schedule, cost
assumptions) in `config/default.yaml`. Default home = Hartbeespoort, `radius_km: 100`.

---

## 7. Scheduling & portability
- Windows Task Scheduler runs `run-scrape` every ~30–60 min (configurable; deliberately polite).
- **Catch-up on startup** task back-fills after the PC was off/asleep.
- A lighter **revalidation sweep** re-checks active listings' live status + refreshes price less often.
- **Portable:** move folder + `.env` to any machine; on a 24/7 cloud box swap Task Scheduler → cron.

---

## 8. Testing strategy
- **Adapters:** golden-file parsing tests against **saved HTML fixtures** — tests never hit live
  sites, so they stay green when a site is merely slow/unreachable and fail loudly when its markup
  actually changes.
- **Validity / dedup / scoring:** unit tests with synthetic cases — a known scam, a known dup, a
  known bargain, a dead listing — asserting the expected flags/scores.
- **Pipeline:** integration test with a fake adapter + a temp/throwaway DB schema.
- TDD from there for new logic.

---

## 9. Legal / ethical posture (explicit)
- **Tier-1** sources are scraped **politely** — low volume, rate-limited, personal use. Per-source
  legal notes recorded in the `sources` registry.
- **Tier-2** social sources (Facebook Marketplace / Instagram) are **against those platforms' terms**.
  Ralf has accepted this risk for personal use; the app **isolates** them, keeps volumes low, and
  never lets them compromise data validity or the rest of the run.
- The app does **not** mass-harvest personal data or evade security controls for malicious ends. It
  is a personal deal-finder operating at low volume.

---

## 10. Open questions / assumptions to confirm
1. **Tier-1 source list** — confirm/extend: AutoTrader, Cars.co.za, Gumtree, AutoMart + specific
   boat/jetski sites Ralf rates.
2. **SMTP provider** — Gmail app password (recommended) vs other; Office 365 may be tenant-locked.
3. **Supabase project** — to be created at build time; keys into `.env`.
4. **Cost assumptions** for margin (transport, recon, fees) — set defaults, refine with use.
5. **Alert cadence** — per-run instant alerts vs a short digest when many deals land at once
   (default: instant, capped at N per run, digest beyond that).

## 11. Out of scope (YAGNI, for now)
WhatsApp alerts · paid/booked pricing data (TransUnion etc.) · multi-user · native mobile app ·
auto-contacting or auto-bidding on sellers · selling-side tooling.

## 12. Build order (layers)
1. DB schema + Supabase client + `init-db`.
2. Polite fetch layer + **first Tier-1 adapter (WeBuyCars, via its JSON inventory API)** with
   golden-file tests.
3. Normalisation → `listings` upsert.
4. Validity engine.
5. Dedup / clustering.
6. Market stats + deal scoring.
7. Watches + **email alerts**.
8. Hosted UI (search, deals feed, detail, watches, source health).
9. Remaining Tier-1 adapters (bikes, boats, jetskis).
10. Tier-2 best-effort adapters (Marketplace/Instagram), isolated.
11. Scheduling (Task Scheduler) + catch-up + revalidation sweep.
