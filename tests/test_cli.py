from unittest.mock import MagicMock, patch

from dealfinder.cli import cmd_init_db
from dealfinder.models import RunStats


def test_init_db_prints_all_migrations(capsys):
    cmd_init_db(None)
    out = capsys.readouterr().out
    assert "001_core.sql" in out
    assert "002_clustering.sql" in out
    assert "create table if not exists listings" in out
    assert "create table if not exists price_history" in out


def _fake_settings():
    s = MagicMock()
    s.supabase_url = "https://fake.supabase.co"
    s.supabase_key = "fake-key"
    s.fetch.min_interval_seconds = 0
    s.fetch.max_retries = 1
    s.fetch.user_agent = "test"
    return s


def _fake_stats():
    return RunStats(
        source_keys=["test_source"],
        fetched=5,
        upserted=3,
        invalid=1,
        price_points=2,
        errors=[],
    )


def test_run_scrape_scoring_failure_does_not_raise(capsys):
    """When run_scoring raises, cmd_run_scrape must NOT raise and must print the skip note."""
    fake_settings = _fake_settings()
    fake_repo = MagicMock()
    fake_fetcher = MagicMock()
    fake_fetcher.__enter__ = MagicMock(return_value=fake_fetcher)
    fake_fetcher.__exit__ = MagicMock(return_value=False)

    with (
        patch("dealfinder.cli.load_settings", return_value=fake_settings),
        patch("dealfinder.cli.build_enabled_adapters", return_value=[]),
        patch("dealfinder.cli.Fetcher", return_value=fake_fetcher),
        patch("dealfinder.cli.SupabaseRepository", return_value=fake_repo),
        patch("dealfinder.cli.run_pipeline", return_value=_fake_stats()),
        patch(
            "dealfinder.cli.run_scoring",
            side_effect=Exception("column deal_score does not exist"),
        ),
    ):
        # Must not raise
        cmd_run_scrape(None)

    out = capsys.readouterr().out
    assert "Scoring skipped" in out
    assert "003_scoring.sql" in out
    assert "deal_score" in out
    # The scrape summary line must still appear
    assert "Done." in out
    assert "upserted=3" in out


def test_run_scrape_scoring_success_includes_scored(capsys):
    """When run_scoring succeeds, cmd_run_scrape prints scored=N in the summary."""
    fake_settings = _fake_settings()
    fake_repo = MagicMock()
    fake_fetcher = MagicMock()

    with (
        patch("dealfinder.cli.load_settings", return_value=fake_settings),
        patch("dealfinder.cli.build_enabled_adapters", return_value=[]),
        patch("dealfinder.cli.Fetcher", return_value=fake_fetcher),
        patch("dealfinder.cli.SupabaseRepository", return_value=fake_repo),
        patch("dealfinder.cli.run_pipeline", return_value=_fake_stats()),
        patch("dealfinder.cli.run_scoring", return_value=7),
    ):
        cmd_run_scrape(None)

    out = capsys.readouterr().out
    assert "scored=7" in out
    assert "Scoring skipped" not in out
    assert "Done." in out


# Import here so the name is available for the test above
from dealfinder.cli import cmd_run_scrape  # noqa: E402
