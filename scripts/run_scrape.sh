#!/usr/bin/env bash
# DealFinderSA scheduled run (cron). Runs from the repo; all state in Supabase + .env.
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/python -m dealfinder.cli run-scrape
