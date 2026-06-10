"""Tests for EmailSender (Plan 4, Task B)."""
from __future__ import annotations

import pytest

from dealfinder.config import Settings
from dealfinder.email import EmailSender


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _smtp_settings(**overrides) -> Settings:
    """Build a minimal Settings with all SMTP fields populated."""
    base = {
        "home": {"name": "Home", "lat": -26.0, "lng": 28.0, "radius_km": 50},
        "fetch": {"min_interval_seconds": 0, "max_retries": 1, "user_agent": "test"},
        "validity": {"min_price_zar": 1000, "max_price_zar": 5000000},
        "sources": {},
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_user": "sender@example.com",
        "smtp_pass": "secret",
        "alert_email_to": "recipient@example.com",
    }
    base.update(overrides)
    return Settings(**base)


class FakeSMTP:
    """A minimal fake SMTP context-manager that records interactions."""

    _instances: list["FakeSMTP"] = []

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.starttls_called = False
        self.login_calls: list[tuple[str, str]] = []
        self.sent_messages: list = []
        FakeSMTP._instances.append(self)

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *args) -> bool:
        return False

    def starttls(self) -> None:
        self.starttls_called = True

    def login(self, user: str, password: str) -> None:
        self.login_calls.append((user, password))

    def send_message(self, msg) -> None:
        self.sent_messages.append(msg)


@pytest.fixture(autouse=True)
def clear_fake_smtp():
    """Reset FakeSMTP instance list before each test."""
    FakeSMTP._instances.clear()
    yield
    FakeSMTP._instances.clear()


# ---------------------------------------------------------------------------
# Tests: is_configured
# ---------------------------------------------------------------------------

class TestIsConfigured:
    def test_all_fields_set_returns_true(self):
        sender = EmailSender(_smtp_settings())
        assert sender.is_configured is True

    def test_missing_smtp_host_returns_false(self):
        sender = EmailSender(_smtp_settings(smtp_host=None))
        assert sender.is_configured is False

    def test_missing_smtp_user_returns_false(self):
        sender = EmailSender(_smtp_settings(smtp_user=None))
        assert sender.is_configured is False

    def test_missing_smtp_pass_returns_false(self):
        sender = EmailSender(_smtp_settings(smtp_pass=None))
        assert sender.is_configured is False

    def test_missing_alert_email_to_returns_false(self):
        sender = EmailSender(_smtp_settings(alert_email_to=None))
        assert sender.is_configured is False


# ---------------------------------------------------------------------------
# Tests: send()
# ---------------------------------------------------------------------------

class TestSend:
    def test_send_returns_true_when_configured(self):
        sender = EmailSender(_smtp_settings(), smtp_factory=FakeSMTP)
        result = sender.send("Test Subject", "Test body")
        assert result is True

    def test_send_calls_starttls(self):
        sender = EmailSender(_smtp_settings(), smtp_factory=FakeSMTP)
        sender.send("subj", "body")
        smtp = FakeSMTP._instances[0]
        assert smtp.starttls_called is True

    def test_send_logs_in_with_correct_credentials(self):
        settings = _smtp_settings()
        sender = EmailSender(settings, smtp_factory=FakeSMTP)
        sender.send("subj", "body")
        smtp = FakeSMTP._instances[0]
        assert len(smtp.login_calls) == 1
        assert smtp.login_calls[0] == ("sender@example.com", "secret")

    def test_send_message_has_correct_to_and_subject(self):
        settings = _smtp_settings()
        sender = EmailSender(settings, smtp_factory=FakeSMTP)
        sender.send("Deal Alert!", "Some body text")
        smtp = FakeSMTP._instances[0]
        assert len(smtp.sent_messages) == 1
        msg = smtp.sent_messages[0]
        assert msg["To"] == "recipient@example.com"
        assert msg["Subject"] == "Deal Alert!"

    def test_send_message_has_correct_from(self):
        settings = _smtp_settings()
        sender = EmailSender(settings, smtp_factory=FakeSMTP)
        sender.send("subj", "body")
        smtp = FakeSMTP._instances[0]
        msg = smtp.sent_messages[0]
        assert msg["From"] == "sender@example.com"

    def test_send_creates_smtp_with_correct_host_and_port(self):
        settings = _smtp_settings(smtp_host="mail.myhost.co.za", smtp_port=465)
        sender = EmailSender(settings, smtp_factory=FakeSMTP)
        sender.send("subj", "body")
        smtp = FakeSMTP._instances[0]
        assert smtp.host == "mail.myhost.co.za"
        assert smtp.port == 465

    def test_send_returns_false_when_not_configured(self):
        sender = EmailSender(_smtp_settings(smtp_host=None), smtp_factory=FakeSMTP)
        result = sender.send("subj", "body")
        assert result is False

    def test_send_does_not_call_factory_when_not_configured(self):
        sender = EmailSender(_smtp_settings(smtp_host=None), smtp_factory=FakeSMTP)
        sender.send("subj", "body")
        assert len(FakeSMTP._instances) == 0
