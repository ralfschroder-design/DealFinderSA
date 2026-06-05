from __future__ import annotations

import re

# Candidate SA number: optional +27/27/0 prefix then 9 national digits,
# allowing spaces/dashes between groups.
_CANDIDATE = re.compile(r"(?:\+?27|0)[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{4}")


def normalize_phone(raw: str) -> str | None:
    """Return a SA number as 0XXXXXXXXX (10 digits), or None if not plausible."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0027") and len(digits) == 13:
        digits = "0" + digits[4:]
    elif digits.startswith("27") and len(digits) == 11:
        digits = "0" + digits[2:]
    if len(digits) == 10 and digits.startswith("0"):
        return digits
    return None


def extract_phone(text: str | None) -> str | None:
    """First plausible SA phone number found in free text, normalised to 0XXXXXXXXX."""
    if not text:
        return None
    for match in _CANDIDATE.finditer(text):
        normalised = normalize_phone(match.group(0))
        if normalised:
            return normalised
    return None
