"""Tests for run_scoring pipeline step (TDD — written before implementation)."""
from __future__ import annotations

from dealfinder.db import InMemoryRepository
from dealfinder.models import Category, Listing


def _car(lid: str, price: int | None, make="Toyota", model="Hilux", year=2019, valid=True) -> Listing:
    return Listing(
        source_key="test",
        source_listing_id=lid,
        url=f"https://example.com/{lid}",
        category=Category.CAR,
        make=make,
        model=model,
        year=year,
        price_zar=price,
        is_valid=valid,
    )


def _seeded_repo() -> InMemoryRepository:
    """
    Seed:
      - 5 Toyota Hilux 2019 at 280k/290k/300k/310k/320k  (median 300k, count 5)
      - 1 Toyota Hilux 2019 at 240k                       (20% under market -> score 100)
      - 1 Mini Cooper 2018 at 150k                        (singleton -> count 1 -> no score)
    """
    repo = InMemoryRepository()
    cohort = [
        _car("h1", 280_000),
        _car("h2", 290_000),
        _car("h3", 300_000),
        _car("h4", 310_000),
        _car("h5", 320_000),
    ]
    under_priced = _car("h6", 240_000)
    singleton = _car("mini1", 150_000, make="Mini", model="Cooper", year=2018)
    repo.upsert_listings(cohort + [under_priced, singleton])
    return repo


def test_run_scoring_returns_count_scored():
    from dealfinder.pipeline import run_scoring

    repo = _seeded_repo()
    n = run_scoring(repo)
    # cohort of 5+1=6 Toyota Hilux can be scored; singleton cannot (count=1)
    assert n == 6


def test_run_scoring_underpriced_gets_high_score():
    from dealfinder.pipeline import run_scoring

    repo = _seeded_repo()
    run_scoring(repo)

    # h6 at 240k is well under the cohort median (~295k with 6 members).
    # Score formula: 50 + 250 * delta_pct.  ~18.6% under → score ~97 (>= 90).
    under = repo.get("test", "h6")
    assert under.deal_score is not None
    assert under.deal_score >= 90, f"expected >= 90, got {under.deal_score}"
    assert under.deal_confidence is not None


def test_run_scoring_at_market_gets_mid_score():
    from dealfinder.pipeline import run_scoring

    repo = _seeded_repo()
    run_scoring(repo)

    # h3 is at exactly 300k (the median) → score 50
    at_market = repo.get("test", "h3")
    assert at_market.deal_score is not None
    # Score should be around the middle, not at extremes
    assert 30 <= at_market.deal_score <= 70, f"expected mid-range score, got {at_market.deal_score}"


def test_run_scoring_singleton_not_scored():
    from dealfinder.pipeline import run_scoring

    repo = _seeded_repo()
    run_scoring(repo)

    # Mini Cooper has count=1 — too thin to score
    mini = repo.get("test", "mini1")
    assert mini.deal_score is None, f"expected None, got {mini.deal_score}"


def test_run_scoring_persists_scores_via_upsert():
    from dealfinder.pipeline import run_scoring

    repo = _seeded_repo()
    run_scoring(repo)

    # After run_scoring, re-fetch from repo and verify scores were written back
    scored_listings = repo.search_listings(valid_only=True)
    scored = [l for l in scored_listings if l.deal_score is not None]
    assert len(scored) == 6
