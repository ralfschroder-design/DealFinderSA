from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dealfinder.adapters import build_enabled_adapters
from dealfinder.config import load_settings
from dealfinder.db import SupabaseRepository
from dealfinder.fetch import Fetcher
from dealfinder.pipeline import run_pipeline


def _require_supabase(settings):
    if not settings.supabase_url or not settings.supabase_key:
        print("ERROR: SUPABASE_URL / SUPABASE_KEY missing. Copy .env.example to .env.", file=sys.stderr)
        raise SystemExit(2)


def cmd_init_db(_args) -> None:
    migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
    files = sorted(migrations_dir.glob("*.sql"))
    print("Run the following SQL in the Supabase SQL editor (in order):\n")
    for path in files:
        print(f"-- ===== {path.name} =====")
        print(path.read_text("utf-8"))
        print()


def cmd_run_scrape(_args) -> None:
    settings = load_settings()
    _require_supabase(settings)
    adapters = build_enabled_adapters(settings)
    fetcher = Fetcher(
        min_interval=settings.fetch.min_interval_seconds,
        max_retries=settings.fetch.max_retries,
        user_agent=settings.fetch.user_agent,
    )
    repo = SupabaseRepository(settings.supabase_url, settings.supabase_key)
    try:
        stats = run_pipeline(adapters=adapters, fetcher=fetcher, repo=repo, settings=settings)
    finally:
        fetcher.close()
    print(
        f"Done. sources={stats.source_keys} fetched={stats.fetched} "
        f"upserted={stats.upserted} invalid={stats.invalid} "
        f"price_points={stats.price_points} errors={stats.errors}"
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="dealfinder")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="Print the SQL to create tables in Supabase").set_defaults(
        func=cmd_init_db
    )
    sub.add_parser("run-scrape", help="Scrape enabled sources into Supabase").set_defaults(
        func=cmd_run_scrape
    )
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
