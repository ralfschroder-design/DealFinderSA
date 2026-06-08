"""Vehicle make/model parsing utilities for DealFinderSA.

``split_make_model`` turns a raw slug or title string into a clean
(make, model, variant) triple using a curated known-makes dictionary with
longest-match so that multi-word makes like "Land Rover", "Harley-Davidson",
and "Mercedes-Benz" are kept intact rather than being split at the first token.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Known-makes dictionary
# ---------------------------------------------------------------------------
# Keys are the *canonical display form* (used as the make output).
# Values are lists of normalised lookup strings (lower-case, hyphens→spaces).
# The lookup strings may have different lengths — the matching loop tries the
# longest (most tokens) first so "Range Rover" beats a hypothetical "Range".
#
# Normalisation used for lookup: lower-case, replace [-+] with space, collapse
# whitespace.  The same normalisation is applied to the slug before matching.

_DISPLAY_LOOKUP: list[tuple[str, list[str]]] = [
    # ---- Cars ---------------------------------------------------------------
    ("Toyota",           ["toyota"]),
    ("Volkswagen",       ["volkswagen"]),
    ("VW",               ["vw"]),
    ("Ford",             ["ford"]),
    ("Hyundai",          ["hyundai"]),
    ("Kia",              ["kia"]),
    ("Nissan",           ["nissan"]),
    ("Renault",          ["renault"]),
    ("Mercedes-Benz",    ["mercedes benz", "mercedes-benz"]),
    ("Mercedes",         ["mercedes"]),
    ("BMW",              ["bmw"]),
    ("Audi",             ["audi"]),
    ("Mazda",            ["mazda"]),
    ("Honda",            ["honda"]),
    ("Suzuki",           ["suzuki"]),
    ("Isuzu",            ["isuzu"]),
    ("Mitsubishi",       ["mitsubishi"]),
    ("Chevrolet",        ["chevrolet"]),
    ("Opel",             ["opel"]),
    ("Peugeot",          ["peugeot"]),
    ("Citroen",          ["citroen"]),
    ("Fiat",             ["fiat"]),
    ("Alfa Romeo",       ["alfa romeo"]),
    ("Land Rover",       ["land rover"]),
    ("Range Rover",      ["range rover"]),
    ("Jeep",             ["jeep"]),
    ("Mini",             ["mini"]),
    ("Volvo",            ["volvo"]),
    ("Jaguar",           ["jaguar"]),
    ("Porsche",          ["porsche"]),
    ("Subaru",           ["subaru"]),
    ("Datsun",           ["datsun"]),
    ("Haval",            ["haval"]),
    ("GWM",              ["gwm"]),
    ("Great Wall",       ["great wall"]),
    ("Chery",            ["chery"]),
    ("Mahindra",         ["mahindra"]),
    ("Tata",             ["tata"]),
    ("Lexus",            ["lexus"]),
    ("Dodge",            ["dodge"]),
    ("SsangYong",        ["ssangyong"]),
    ("Daihatsu",         ["daihatsu"]),
    # ---- Bikes --------------------------------------------------------------
    ("Harley-Davidson",  ["harley davidson", "harley-davidson"]),
    ("Harley",           ["harley"]),
    ("Yamaha",           ["yamaha"]),
    ("Kawasaki",         ["kawasaki"]),
    ("Ducati",           ["ducati"]),
    ("KTM",              ["ktm"]),
    ("Triumph",          ["triumph"]),
    ("Aprilia",          ["aprilia"]),
    ("Vespa",            ["vespa"]),
    ("Royal Enfield",    ["royal enfield"]),
    ("Husqvarna",        ["husqvarna"]),
]

# Build a fast lookup structure: maps normalised_lookup_string → display_form
# Organised by token count so we can try longest-match first.
_LOOKUP_BY_LEN: dict[int, dict[str, str]] = {}

for _display, _aliases in _DISPLAY_LOOKUP:
    for _alias in _aliases:
        _tokens = _alias.split()
        _n = len(_tokens)
        if _n not in _LOOKUP_BY_LEN:
            _LOOKUP_BY_LEN[_n] = {}
        # Only insert the first occurrence (order in _DISPLAY_LOOKUP is priority)
        if _alias not in _LOOKUP_BY_LEN[_n]:
            _LOOKUP_BY_LEN[_n][_alias] = _display

_MAX_MAKE_TOKENS = max(_LOOKUP_BY_LEN.keys()) if _LOOKUP_BY_LEN else 1

# Regex for a leading 4-digit year (1900–2099)
_YEAR_RE = re.compile(r"^(19|20)\d{2}$")


def _normalise(text: str) -> str:
    """Lower-case, replace hyphens/plusses with spaces, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[-+]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_make_model(text: str) -> tuple[str | None, str | None, str | None]:
    """Split a raw vehicle slug or title into (make, model, variant).

    Algorithm
    ---------
    1. Normalise *text*: lower-case, hyphens/plusses → spaces, collapse WS.
    2. Tokenise on whitespace.
    3. Drop a leading 4-digit year token (1900–2099) if present.
    4. Try the longest known-make prefix (up to ``_MAX_MAKE_TOKENS`` tokens),
       walking down to 1 token.  First match wins.
    5. ``make`` = display form of the matched make (Title-cased canonical string
       defined in ``_DISPLAY_LOOKUP``).
    6. ``model`` = next token, Title-cased.
    7. ``variant`` = remainder joined by spaces, Title-cased; ``None`` if empty.
    8. If no known make matched, fall back: make = tokens[0].title(),
       model = tokens[1].title() (if present), variant = rest.

    Parameters
    ----------
    text:
        Raw slug string, e.g. ``"2019-toyota-hilux-2-4-gd6-srx"`` or
        ``"land-rover-discovery-sport"``.

    Returns
    -------
    (make, model, variant) — any part may be ``None`` when absent.
    """
    if not text:
        return (None, None, None)

    normalised = _normalise(text)
    tokens = normalised.split()

    if not tokens:
        return (None, None, None)

    # Strip leading year token
    if _YEAR_RE.match(tokens[0]):
        tokens = tokens[1:]

    if not tokens:
        return (None, None, None)

    # Longest-match lookup
    matched_display: str | None = None
    matched_len: int = 0

    for n in range(min(_MAX_MAKE_TOKENS, len(tokens)), 0, -1):
        candidate = " ".join(tokens[:n])
        if n in _LOOKUP_BY_LEN and candidate in _LOOKUP_BY_LEN[n]:
            matched_display = _LOOKUP_BY_LEN[n][candidate]
            matched_len = n
            break

    if matched_display is not None:
        make: str | None = matched_display
        remaining = tokens[matched_len:]
    else:
        # Fallback: first token as make
        make = tokens[0].title() if tokens else None
        remaining = tokens[1:]

    model: str | None = remaining[0].title() if remaining else None
    variant_tokens = remaining[1:]
    variant: str | None = " ".join(t.title() for t in variant_tokens) if variant_tokens else None

    return (make, model, variant)
