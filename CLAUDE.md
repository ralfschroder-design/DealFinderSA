# DealFinderSA

At the start of every session in this directory, read PROJECT.md before doing anything else.
Confirm: "Resuming DealFinderSA — I've read the project context." then summarise the
current status and next steps in 3–5 bullet points.

When significant work is done in a session, update PROJECT.md:
- Add a dated entry to the Progress Log
- Update Next Steps
- Update Open Questions & Blockers
- Update Key Files & Paths if new files/configs were introduced

## Project-specific notes
- **Docs live here as Markdown only — no Confluence for this project** (per Ralf's instruction,
  2026-06-02). Keep all documentation under `docs/`. Do not create or update a Confluence page
  for DealFinderSA.
- **Self-contained & portable:** keep all code, config and docs inside this folder. External
  dependencies (Supabase, SMTP, hosted UI) are referenced via `.env` only — so moving this folder
  plus `.env` to another machine yields a working scraper.
- **Authoritative design:** `docs/specs/2026-06-02-dealfindersa-design.md`.
- **Legal/ethical posture:** Tier-1 sources are scraped politely (rate-limited, low volume,
  personal use). Tier-2 social sources are best-effort and against those platforms' terms — Ralf
  has accepted that risk; keep them isolated and never let them compromise data validity. Do not
  build anything that mass-harvests personal data or evades security controls for malicious ends.
