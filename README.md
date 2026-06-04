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
dealfinder run-scrape   # scrape enabled sources into Supabase
pytest -q               # run the test suite
```

Configuration (home location, radius, politeness, enabled sources) lives in
`config/default.yaml`. Secrets live in `.env` (never committed).

## Status

Plan 1 (walking skeleton) — WeBuyCars -> validate -> Supabase. 19 tests passing. See
`docs/plans/` and `docs/specs/` for the full design and roadmap.

## Go-live checklist (user-gated)

These steps need a Supabase account and live network, so they are done by the project owner:

1. Create a free Supabase project; put the Project URL + `service_role` key in `.env`.
2. Run `dealfinder init-db` and execute the printed SQL in the Supabase SQL editor.
3. Capture one real WeBuyCars inventory API response (browser DevTools -> Network -> XHR),
   save it over `tests/fixtures/webuycars_search.json`, and reconcile `SEARCH_URL` + the
   field names in `src/dealfinder/adapters/webuycars.py` (`_map_record`) to match. Re-run
   `pytest tests/test_webuycars.py` until green against the real shape.
4. Run `dealfinder run-scrape` and confirm valid listings appear in the Supabase `listings`
   table (and a row in `runs`).
