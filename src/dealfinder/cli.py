from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dealfinder.adapters import build_enabled_adapters
from dealfinder.alerts import run_alerts
from dealfinder.config import load_settings
from dealfinder.db import SupabaseRepository
from dealfinder.email import EmailSender
from dealfinder.fetch import Fetcher
from dealfinder.pipeline import run_pipeline, run_scoring


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


def cmd_serve(args) -> None:
    settings = load_settings()
    _require_supabase(settings)
    from dealfinder.db import SupabaseRepository
    from dealfinder.web import create_app
    import uvicorn
    app = create_app(SupabaseRepository(settings.supabase_url, settings.supabase_key))
    port = getattr(args, "port", 8000)
    uvicorn.run(app, host="127.0.0.1", port=port)


def cmd_score(_args) -> None:
    settings = load_settings()
    _require_supabase(settings)
    from dealfinder.db import SupabaseRepository
    from dealfinder.pipeline import run_scoring
    repo = SupabaseRepository(settings.supabase_url, settings.supabase_key)
    n = run_scoring(repo)
    print(f"Scored {n} listings against the live market.")


def cmd_alert(_args) -> None:
    settings = load_settings()
    _require_supabase(settings)
    repo = SupabaseRepository(settings.supabase_url, settings.supabase_key)
    sender = EmailSender(settings)
    if not sender.is_configured:
        print(
            "Email not configured — set SMTP_HOST/SMTP_USER/SMTP_PASS/ALERT_EMAIL_TO in .env"
        )
        return
    n = run_alerts(repo, sender, settings)
    print(f"Sent alerts for {n} new deal(s).")


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
    try:
        scored = run_scoring(repo)
        scored_part = f"scored={scored} "
    except Exception as e:
        scored_part = ""
        short_err = str(e).splitlines()[0][:120]
        print(
            f"Scoring skipped (apply migrations/003_scoring.sql in Supabase to enable). "
            f"Reason: {short_err}"
        )
    alerted_part = ""
    try:
        sender = EmailSender(settings)
        n = run_alerts(repo, sender, settings)
        alerted_part = f"alerted={n} "
    except Exception as e:
        short_err = str(e).splitlines()[0][:120]
        print(f"Alerts skipped: {short_err}")
    print(
        f"Done. sources={stats.source_keys} fetched={stats.fetched} "
        f"upserted={stats.upserted} invalid={stats.invalid} "
        f"price_points={stats.price_points} {scored_part}{alerted_part}errors={stats.errors}"
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
    sub.add_parser("score", help="Score all valid listings against the live-market median").set_defaults(
        func=cmd_score
    )
    sub.add_parser("alert", help="Send email digest of new deals above the score threshold").set_defaults(
        func=cmd_alert
    )
    serve_parser = sub.add_parser("serve", help="Start local search UI web server")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    serve_parser.set_defaults(func=cmd_serve)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
