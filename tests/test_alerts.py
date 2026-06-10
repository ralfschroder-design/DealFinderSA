"""Tests for alerts selection logic and run_alerts runner (Plan 4, Tasks A & B)."""
from dealfinder.alerts import run_alerts, select_new_deals
from dealfinder.db import InMemoryRepository
from dealfinder.models import Category, Listing


def _listing(source_listing_id: str, deal_score: int | None, is_valid: bool = True) -> Listing:
    return Listing(
        source_key="src",
        source_listing_id=source_listing_id,
        url=f"https://example.com/{source_listing_id}",
        category=Category.CAR,
        title=f"Listing {source_listing_id}",
        price_zar=200000,
        deal_score=deal_score,
        is_valid=is_valid,
    )


def test_returns_only_above_threshold():
    listings = [
        _listing("above", 90),
        _listing("at-threshold", 80),
        _listing("below", 79),
    ]
    result = select_new_deals(listings, alerted_keys=set(), min_score=80)
    ids = {l.source_listing_id for l in result}
    assert "above" in ids
    assert "at-threshold" in ids
    assert "below" not in ids


def test_excludes_invalid_listings():
    listings = [
        _listing("valid", 90, is_valid=True),
        _listing("invalid", 90, is_valid=False),
    ]
    result = select_new_deals(listings, alerted_keys=set(), min_score=80)
    ids = {l.source_listing_id for l in result}
    assert "valid" in ids
    assert "invalid" not in ids


def test_excludes_none_score():
    listings = [
        _listing("scored", 85),
        _listing("no-score", None),
    ]
    result = select_new_deals(listings, alerted_keys=set(), min_score=80)
    ids = {l.source_listing_id for l in result}
    assert "scored" in ids
    assert "no-score" not in ids


def test_excludes_already_alerted_keys():
    listings = [
        _listing("fresh", 90),
        _listing("already-sent", 95),
    ]
    alerted = {("src", "already-sent")}
    result = select_new_deals(listings, alerted_keys=alerted, min_score=80)
    ids = {l.source_listing_id for l in result}
    assert "fresh" in ids
    assert "already-sent" not in ids


def test_sorted_descending_by_score():
    listings = [
        _listing("low", 81),
        _listing("high", 99),
        _listing("mid", 85),
    ]
    result = select_new_deals(listings, alerted_keys=set(), min_score=80)
    scores = [l.deal_score for l in result]
    assert scores == sorted(scores, reverse=True)


def test_empty_listings_returns_empty():
    assert select_new_deals([], alerted_keys=set(), min_score=80) == []


def test_all_filtered_returns_empty():
    listings = [_listing("low", 50)]
    assert select_new_deals(listings, alerted_keys=set(), min_score=80) == []


# ---------------------------------------------------------------------------
# Helpers for run_alerts tests
# ---------------------------------------------------------------------------

class FakeSender:
    """Fake EmailSender for run_alerts tests."""

    def __init__(self, configured: bool = True) -> None:
        self._configured = configured
        self.send_calls: list[tuple[str, str]] = []  # (subject, body)

    @property
    def is_configured(self) -> bool:
        return self._configured

    def send(self, subject: str, body: str) -> bool:
        self.send_calls.append((subject, body))
        return self._configured


def _settings_stub(min_score: int = 80):
    """Return a lightweight object with alerts.min_score set."""
    class _Alerts:
        pass
    class _S:
        alerts = _Alerts()
    _S.alerts.min_score = min_score
    return _S()


def _seeded_repo(*, scores: list[int], is_valid: bool = True) -> InMemoryRepository:
    """Create an InMemoryRepository pre-loaded with listings at given scores."""
    repo = InMemoryRepository()
    listings = [
        _listing(str(i), score, is_valid=is_valid)
        for i, score in enumerate(scores)
    ]
    repo.upsert_listings(listings)
    return repo


# ---------------------------------------------------------------------------
# Tests: run_alerts
# ---------------------------------------------------------------------------

class TestRunAlerts:
    def test_returns_count_of_alerts_sent(self):
        repo = _seeded_repo(scores=[90, 85, 70])
        sender = FakeSender(configured=True)
        n = run_alerts(repo, sender, _settings_stub(min_score=80))
        # scores 90 and 85 qualify; 70 does not
        assert n == 2

    def test_sends_exactly_one_email(self):
        repo = _seeded_repo(scores=[90, 85])
        sender = FakeSender(configured=True)
        run_alerts(repo, sender, _settings_stub(min_score=80))
        assert len(sender.send_calls) == 1

    def test_email_subject_contains_count(self):
        repo = _seeded_repo(scores=[90, 85])
        sender = FakeSender(configured=True)
        run_alerts(repo, sender, _settings_stub(min_score=80))
        subject, _ = sender.send_calls[0]
        assert "2" in subject

    def test_second_run_returns_zero_deduped(self):
        """After first run, all alerted keys are recorded; second run returns 0."""
        repo = _seeded_repo(scores=[90, 85])
        sender = FakeSender(configured=True)
        run_alerts(repo, sender, _settings_stub(min_score=80))
        n2 = run_alerts(repo, sender, _settings_stub(min_score=80))
        assert n2 == 0

    def test_second_run_does_not_send_email(self):
        repo = _seeded_repo(scores=[90])
        sender = FakeSender(configured=True)
        run_alerts(repo, sender, _settings_stub(min_score=80))
        run_alerts(repo, sender, _settings_stub(min_score=80))
        assert len(sender.send_calls) == 1  # only once total

    def test_record_alerts_called_after_send(self):
        """After run_alerts, alerted_keys() contains the sent listings."""
        repo = _seeded_repo(scores=[90])
        sender = FakeSender(configured=True)
        run_alerts(repo, sender, _settings_stub(min_score=80))
        assert len(repo.alerted_keys()) == 1

    def test_unconfigured_sender_returns_zero(self):
        repo = _seeded_repo(scores=[90, 85])
        sender = FakeSender(configured=False)
        n = run_alerts(repo, sender, _settings_stub(min_score=80))
        assert n == 0

    def test_unconfigured_sender_does_not_record_alerts(self):
        """With unconfigured sender, backlog must be preserved (do not record)."""
        repo = _seeded_repo(scores=[90])
        sender = FakeSender(configured=False)
        run_alerts(repo, sender, _settings_stub(min_score=80))
        assert len(repo.alerted_keys()) == 0

    def test_unconfigured_sender_does_not_send(self):
        repo = _seeded_repo(scores=[90])
        sender = FakeSender(configured=False)
        run_alerts(repo, sender, _settings_stub(min_score=80))
        assert len(sender.send_calls) == 0

    def test_no_qualifying_deals_returns_zero(self):
        repo = _seeded_repo(scores=[50, 60])
        sender = FakeSender(configured=True)
        n = run_alerts(repo, sender, _settings_stub(min_score=80))
        assert n == 0

    def test_no_qualifying_deals_sends_no_email(self):
        repo = _seeded_repo(scores=[50, 60])
        sender = FakeSender(configured=True)
        run_alerts(repo, sender, _settings_stub(min_score=80))
        assert len(sender.send_calls) == 0

    def test_invalid_listings_not_alerted(self):
        """Listings with is_valid=False must not be alerted even if score qualifies."""
        repo = InMemoryRepository()
        repo.upsert_listings([_listing("x", 95, is_valid=False)])
        sender = FakeSender(configured=True)
        n = run_alerts(repo, sender, _settings_stub(min_score=80))
        assert n == 0
