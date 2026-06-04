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

## Progress Log
| Date | What was done |
|------|--------------|
| 2026-06-02 | Brainstormed requirements and locked the design. Wrote design spec (`docs/specs/2026-06-02-dealfindersa-design.md`). Key decisions: flip use-case; cars+bikes+boats+jetskis; max-coverage sources (Tier-1 reliable + Tier-2 best-effort); scheduled scrape + hot-deal alerts; local Python scraper on Windows (portable); Supabase cloud DB + hosted UI; market-compare + condition scoring; **email** alerts (switched from WhatsApp); Hartbeespoort + 100 km default; docs in Markdown, no Confluence. |
| 2026-06-02 | Wrote **Plan 1 — walking skeleton** (`docs/plans/2026-06-02-plan-1-walking-skeleton.md`). Chose **WeBuyCars** as the primary first source (cars/bakkies, via its JSON inventory API); **Gumtree** is the fast-follow for bikes/boats/jetskis. Updated spec Tier-1 list accordingly. Plan covers: package scaffold, config, Listing model, polite fetch layer, WeBuyCars adapter, validity engine, Supabase schema + repository, pipeline + CLI — TDD, 9 tasks. |
| 2026-06-04 | Implemented Plan 1 (walking skeleton), Tasks 1-8, via subagent-driven development with per-task spec + quality review. Package `dealfinder`: config, Listing model, polite fetch layer, WeBuyCars adapter (fixture-driven), validity engine, Supabase schema + repository, pipeline + CLI. 19 tests passing. Commits 99c1809..5011679 on branch master. README added. Live WeBuyCars API reconciliation + real Supabase scrape remain user-gated (see README go-live checklist). |

## Key Files & Paths
| Path / URL | Purpose |
|-----------|---------|
| `docs/specs/2026-06-02-dealfindersa-design.md` | Approved design spec (authoritative) |
| `PROJECT.md` | This file — status, log, next steps |
| `CLAUDE.md` | Session bootstrap instructions |
| `docs/plans/2026-06-02-plan-1-walking-skeleton.md` | Plan 1 — walking skeleton (step-by-step build) |
| `README.md` | Setup, usage, and go-live checklist |

## Open Questions & Blockers
- [ ] Confirm Tier-1 source list (AutoTrader, Cars.co.za, Gumtree, AutoMart + boat/jetski sites) — add/drop any?
- [ ] SMTP provider for email alerts (Gmail app password recommended; Office 365 may be locked down by the Sun International tenant).
- [ ] Supabase project + API keys to be created at build time.
- [ ] Resale/cost assumptions for the margin estimate (transport, recon, fees) — set sensible defaults, refine later.

## Next Steps
1. **Go live (user-gated)** — follow the go-live checklist in `README.md`: create Supabase project + `.env`, apply schema via `dealfinder init-db`, capture a real WeBuyCars API response and reconcile the adapter, then `dealfinder run-scrape` and verify rows.
2. **Plan 2 — dedup & clustering** (fingerprint + image pHash + phone match, price history).
3. Subsequent: Plan 3 scoring → Plan 4 email alerts → Plan 5 UI → Plan 6 more sources (Gumtree/AutoTrader/Cars.co.za) → Plan 7 scheduling + Tier-2 social.
