# DealFinderSA

Personal vehicle-flipping deal radar. Scrapes South African vehicle sources, validates and
(later) scores listings, and surfaces underpriced deals near Hartbeespoort.

## Setup (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env   # then fill in SUPABASE_URL + SUPABASE_KEY
```

Apply the database schema: run `dealfinder init-db` and paste the printed SQL into the
Supabase SQL editor (one-time).

## Use

```powershell
dealfinder init-db      # print SQL for all migrations (paste into Supabase SQL editor)
dealfinder run-scrape   # scrape Gumtree (cars/bikes/boats/jetskis) into Supabase, then score
dealfinder score        # (re-)score all listings in Supabase against the live market
dealfinder serve        # start local FastAPI search UI at http://localhost:8000 (test harness)
pytest -q               # run the test suite
```

> The local web UI (`dealfinder serve`) is a **test harness** only. The production frontend is
> planned as a [Lovable](https://lovable.dev) app on Supabase.

Configuration (home location, radius, politeness, enabled sources) lives in
`config/default.yaml`. Secrets live in `.env` (never committed).

## Status

Plan 1–3 (scrape → validate → dedup → score). Primary source: **Gumtree** (cars/bikes/boats/jetskis, openly-served HTML). ~126 live listings in Supabase. ~100 tests passing. Private GitHub: `ralfschroder-design/DealFinderSA`. See `docs/plans/` and `docs/specs/` for the full design and roadmap.

## Go-live checklist (user-gated)

These steps need a Supabase account and live network, so they are done by the project owner:

1. Create a free Supabase project; put the Project URL + `service_role` key in `.env`.
2. Run `dealfinder init-db` and execute the printed SQL in the Supabase SQL editor.
   - **Migration 001** (`001_core.sql`) — core schema (`listings`, `runs`).
   - **Migration 002** (`002_clustering.sql`) — adds `fingerprint`, `price_history`, `vehicle_clusters` view.
   - **Migration 003** (`003_scoring.sql`) — adds deal-score columns; **required** for scoring/alerts/UI to work.
3. Run `dealfinder run-scrape` and confirm valid listings appear in the Supabase `listings`
   table (and a row in `runs`). Scores are computed automatically at the end of the scrape
   once migration 003 is applied.
4. Open `dealfinder serve` to browse listings with deal scores and "Best deal" sort.

> **WeBuyCars note:** The WeBuyCars inventory API is protected by a proof-of-work anti-bot and
> is not used for automation. It may be added in future via an official dealer API.
