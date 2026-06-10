"""SMTP email sender for DealFinderSA alerts (Plan 4, Task B)."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage


class EmailSender:
    def __init__(self, settings, smtp_factory=smtplib.SMTP):
        self._s = settings
        self._smtp_factory = smtp_factory  # injectable for tests

    @property
    def is_configured(self) -> bool:
        s = self._s
        return bool(s.smtp_host and s.smtp_user and s.smtp_pass and s.alert_email_to)

    def send(self, subject: str, body: str) -> bool:
        """Send a plain-text email. Returns True on success, False if not configured."""
        if not self.is_configured:
            return False
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._s.smtp_user
        msg["To"] = self._s.alert_email_to
        msg.set_content(body)
        with self._smtp_factory(self._s.smtp_host, self._s.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(self._s.smtp_user, self._s.smtp_pass)
            smtp.send_message(msg)
        return True
