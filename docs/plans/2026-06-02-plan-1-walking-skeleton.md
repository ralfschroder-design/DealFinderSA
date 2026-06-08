# DealFinderSA — Plan 1: Walking Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run one command and have *valid* car listings scraped from WeBuyCars land in a Supabase table.

**Architecture:** A small Python package (`dealfinder`) with focused modules — config, models, a polite HTTP fetch layer, a plug-in source adapter (WeBuyCars), a basic validity engine, a Supabase repository, and a pipeline that wires them together behind a `dealfinder` CLI. Everything runs locally; the only external service is Supabase, referenced via `.env`.

**Tech Stack:** Python 3.12, `httpx` (HTTP), `pydantic` v2 (models/validation), `pyyaml` + `python-dotenv` (config), `supabase` (supabase-py v2, Postgres access), `pytest` + `respx` (tests), `ruff` (lint/format).

**Source for this plan:** WeBuyCars (`https://www.webuycars.co.za/`) — cars/bakkies only, consumed via its JSON inventory API. Bikes/boats/jetskis arrive in a later plan via Gumtree.

---

## Conventions

- **Package layout:** `src/` layout, installed editable (`pip install -e ".[dev]"`). Import root is `dealfinder`.
- **Run tests:** from the project root with the venv active: `pytest -q`.
- **Windows shell:** PowerShell. Create/activate venv with `python -m venv .venv` then `.\.venv\Scripts\Activate.ps1`.
- **Commits:** small and frequent, one per task step group as shown. (Git is initialised in Task 1; if you prefer not to use git, skip the commit steps — everything else is unaffected.)
- **No secrets in git:** real values live in `.env` (git-ignored); `.env.example` documents the keys.

---

## File Structure (created across this plan)

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, deps, dev extras, console script `dealfinder`, pytest/ruff config |
| `.gitignore` | Ignore venv, caches, `.env`, build artefacts |
| `.env.example` | Documents required env vars (Supabase keys) |
| `config/default.yaml` | Non-secret tunables: home location, radius, fetch politeness, price-sanity bounds, enabled sources |
| `src/dealfinder/__init__.py` | Package marker + version |
| `src/dealfinder/config.py` | Load YAML + `.env` into a typed `Settings` object |
| `src/dealfinder/models.py` | Enums + the normalised `Listing` model + `ValidityResult` + `RunStats` |
| `src/dealfinder/fetch.py` | `Fetcher`: polite httpx wrapper (rate limit, retry/backoff, UA) |
| `src/dealfinder/adapters/__init__.py` | Adapter registry (`build_enabled_adapters`) |
| `src/dealfinder/adapters/base.py` | `Adapter` abstract base class |
| `src/dealfinder/adapters/webuycars.py` | WeBuyCars adapter (search + parse JSON → `Listing`) |
| `src/dealfinder/validity.py` | `evaluate_validity(listing, settings) → ValidityResult` |
| `src/dealfinder/db.py` | `ListingRepository` protocol, `SupabaseRepository`, `InMemoryRepository`, `listing_to_row` |
| `src/dealfinder/pipeline.py` | `run_pipeline(...)` — fetch → validate → upsert → record run |
| `src/dealfinder/cli.py` | `dealfinder` CLI: `init-db`, `run-scrape` |
| `migrations/001_core.sql` | Supabase schema: `sources`, `listings`, `runs`, `sources_health` |
| `tests/conftest.py` | Shared fixtures (sample `Listing`, settings) |
| `tests/test_config.py` | Config loading tests |
| `tests/test_models.py` | Listing model tests |
| `tests/test_fetch.py` | Fetch layer tests (respx) |
| `tests/test_webuycars.py` | WeBuyCars parse tests (golden-file fixture) |
| `tests/test_validity.py` | Validity engine tests |
| `tests/test_db.py` | `listing_to_row` + `InMemoryRepository` tests |
| `tests/test_pipeline.py` | Pipeline integration test (fake adapter + in-memory repo) |
| `tests/fixtures/webuycars_search.json` | Saved sample WeBuyCars API response (replace with a real capture) |

---

## Task 1: Project scaffolding & tooling

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `src/dealfinder/__init__.py`, `tests/__init__.py`, `tests/test_smoke.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "dealfinder"
version = "0.1.0"
description = "DealFinderSA - vehicle-flipping deal radar"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.7",
    "pyyaml>=6.0",
    "python-dotenv>=1.0",
    "supabase>=2.5",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "respx>=0.21",
    "ruff>=0.5",
]

[project.scripts]
dealfinder = "dealfinder.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
src = ["src", "tests"]
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
.ruff_cache/
build/
dist/
*.egg-info/
.cache/
```

- [ ] **Step 3: Create `.env.example`**

```dotenv
# Supabase (Project Settings -> API). Use the service_role key for the local scraper.
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_KEY=YOUR-SERVICE-ROLE-KEY
```

- [ ] **Step 4: Create `src/dealfinder/__init__.py`**

```python
"""DealFinderSA - vehicle-flipping deal radar."""

__version__ = "0.1.0"
```

- [ ] **Step 5: Create `tests/__init__.py`** (empty file)

```python
```

- [ ] **Step 6: Write the smoke test `tests/test_smoke.py`**

```python
import dealfinder


def test_package_imports():
    assert dealfinder.__version__ == "0.1.0"
```

- [ ] **Step 7: Create venv, install, run smoke test**

Run:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest tests/test_smoke.py -v
```
Expected: `test_package_imports PASSED`.

- [ ] **Step 8: Initialise git and commit**

```powershell
git init
git add .
git commit -m "chore: scaffold dealfinder package + tooling"
```

---

## Task 2: Config & Settings

**Files:**
- Create: `config/default.yaml`, `src/dealfinder/config.py`, `tests/test_config.py`

- [ ] **Step 1: Create `config/default.yaml`**

```yaml
# Non-secret tunables. Secrets live in .env
home:
  name: "Hartbeespoort"
  lat: -25.7457
  lng: 27.8540
  radius_km: 100

fetch:
  min_interval_seconds: 2.5   # polite delay between requests to a host
  max_retries: 3
  user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DealFinderSA/0.1 (personal use)"

validity:
  min_price_zar: 5000
  max_price_zar: 15000000

sources:
  webuycars:
    enabled: true
    max_pages: 2   # keep small while building
```

- [ ] **Step 2: Write the failing test `tests/test_config.py`**

```python
from pathlib import Path

from dealfinder.config import load_settings


def test_load_settings_reads_yaml_and_env(tmp_path, monkeypatch):
    cfg = tmp_path / "default.yaml"
    cfg.write_text(
        "home:\n  name: Test\n  lat: -25.0\n  lng: 28.0\n  radius_km: 50\n"
        "fetch:\n  min_interval_seconds: 1.0\n  max_retries: 2\n  user_agent: UA\n"
        "validity:\n  min_price_zar: 1000\n  max_price_zar: 2000000\n"
        "sources:\n  webuycars:\n    enabled: true\n    max_pages: 1\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "key123")

    s = load_settings(config_path=cfg)

    assert s.home.radius_km == 50
    assert s.fetch.max_retries == 2
    assert s.validity.max_price_zar == 2000000
    assert s.supabase_url == "https://x.supabase.co"
    assert s.supabase_key == "key123"
    assert s.sources["webuycars"].enabled is True
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: dealfinder.config`).

- [ ] **Step 4: Implement `src/dealfinder/config.py`**

```python
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


class Home(BaseModel):
    name: str
    lat: float
    lng: float
    radius_km: int


class FetchCfg(BaseModel):
    min_interval_seconds: float
    max_retries: int
    user_agent: str


class ValidityCfg(BaseModel):
    min_price_zar: int
    max_price_zar: int


class SourceCfg(BaseModel):
    enabled: bool = False
    max_pages: int = 1


class Settings(BaseModel):
    home: Home
    fetch: FetchCfg
    validity: ValidityCfg
    sources: dict[str, SourceCfg]
    supabase_url: str | None = None
    supabase_key: str | None = None


def load_settings(config_path: Path | None = None) -> Settings:
    load_dotenv()
    path = config_path or DEFAULT_CONFIG
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Settings(
        **data,
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_key=os.getenv("SUPABASE_KEY"),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add config/default.yaml src/dealfinder/config.py tests/test_config.py
git commit -m "feat: typed settings from yaml + .env"
```

---

## Task 3: Domain models

**Files:**
- Create: `src/dealfinder/models.py`, `tests/test_models.py`, `tests/conftest.py`

- [ ] **Step 1: Write the failing test `tests/test_models.py`**

```python
from dealfinder.models import Category, Listing, ListingStatus


def test_listing_minimal_valid():
    listing = Listing(
        source_key="webuycars",
        source_listing_id="123",
        url="https://example.com/123",
        category=Category.CAR,
        title="2019 Toyota Hilux",
        make="Toyota",
        model="Hilux",
        year=2019,
        price_zar=339900,
    )
    assert listing.status == ListingStatus.ACTIVE
    assert listing.image_urls == []
    assert listing.price_zar == 339900


def test_listing_rejects_bad_year():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Listing(
            source_key="webuycars",
            source_listing_id="1",
            url="u",
            category=Category.CAR,
            year=1800,  # below minimum
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL (`ModuleNotFoundError: dealfinder.models`).

- [ ] **Step 3: Implement `src/dealfinder/models.py`**

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Category(str, Enum):
    CAR = "car"
    BIKE = "bike"
    BOAT = "boat"
    JETSKI = "jetski"


class SellerType(str, Enum):
    DEALER = "dealer"
    PRIVATE = "private"
    UNKNOWN = "unknown"


class ListingStatus(str, Enum):
    ACTIVE = "active"
    SOLD = "sold"
    REMOVED = "removed"


class Listing(BaseModel):
    source_key: str
    source_listing_id: str
    url: str
    category: Category
    title: str | None = None
    make: str | None = None
    model: str | None = None
    variant: str | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)
    price_zar: int | None = Field(default=None, ge=0)
    mileage_km: int | None = Field(default=None, ge=0)
    engine_hours: int | None = Field(default=None, ge=0)
    province: str | None = None
    town: str | None = None
    lat: float | None = None
    lng: float | None = None
    seller_type: SellerType = SellerType.UNKNOWN
    seller_name: str | None = None
    seller_phone: str | None = None
    description: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    posted_at: datetime | None = None
    status: ListingStatus = ListingStatus.ACTIVE
    is_valid: bool = True
    quality_flags: list[str] = Field(default_factory=list)
    raw: dict | None = None


class ValidityResult(BaseModel):
    is_valid: bool
    flags: list[str] = Field(default_factory=list)


class RunStats(BaseModel):
    source_keys: list[str] = Field(default_factory=list)
    fetched: int = 0
    upserted: int = 0
    invalid: int = 0
    errors: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Create shared fixtures `tests/conftest.py`**

```python
import pytest

from dealfinder.config import Settings, Home, FetchCfg, ValidityCfg, SourceCfg
from dealfinder.models import Category, Listing


@pytest.fixture
def settings() -> Settings:
    return Settings(
        home=Home(name="Test", lat=-25.0, lng=28.0, radius_km=100),
        fetch=FetchCfg(min_interval_seconds=0.0, max_retries=2, user_agent="UA"),
        validity=ValidityCfg(min_price_zar=5000, max_price_zar=15000000),
        sources={"webuycars": SourceCfg(enabled=True, max_pages=1)},
        supabase_url="https://x.supabase.co",
        supabase_key="key",
    )


@pytest.fixture
def sample_listing() -> Listing:
    return Listing(
        source_key="webuycars",
        source_listing_id="123",
        url="https://www.webuycars.co.za/buy-a-car/123",
        category=Category.CAR,
        title="2019 Toyota Hilux 2.4 GD-6 SRX",
        make="Toyota",
        model="Hilux",
        variant="2.4 GD-6 SRX",
        year=2019,
        price_zar=339900,
        mileage_km=145000,
        province="Gauteng",
        town="Pretoria",
        image_urls=["https://img/1.jpg"],
    )
```

- [ ] **Step 6: Commit**

```powershell
git add src/dealfinder/models.py tests/test_models.py tests/conftest.py
git commit -m "feat: normalised Listing model + enums + test fixtures"
```

---

## Task 4: Polite fetch layer

**Files:**
- Create: `src/dealfinder/fetch.py`, `tests/test_fetch.py`

- [ ] **Step 1: Write the failing test `tests/test_fetch.py`**

```python
import httpx
import respx

from dealfinder.fetch import Fetcher


@respx.mock
def test_get_json_returns_parsed_body():
    respx.get("https://api.test/stock").mock(
        return_value=httpx.Response(200, json={"results": [1, 2]})
    )
    fetcher = Fetcher(min_interval=0.0, max_retries=1, user_agent="UA", sleep=lambda _: None)
    body = fetcher.get_json("https://api.test/stock")
    assert body == {"results": [1, 2]}


@respx.mock
def test_get_json_retries_then_succeeds():
    route = respx.get("https://api.test/stock")
    route.side_effect = [
        httpx.Response(429),
        httpx.Response(200, json={"ok": True}),
    ]
    fetcher = Fetcher(min_interval=0.0, max_retries=3, user_agent="UA", sleep=lambda _: None)
    body = fetcher.get_json("https://api.test/stock")
    assert body == {"ok": True}
    assert route.call_count == 2


@respx.mock
def test_get_json_sets_user_agent():
    captured = {}

    def handler(request):
        captured["ua"] = request.headers.get("user-agent")
        return httpx.Response(200, json={})

    respx.get("https://api.test/x").mock(side_effect=handler)
    Fetcher(min_interval=0.0, max_retries=1, user_agent="DF/0.1", sleep=lambda _: None).get_json(
        "https://api.test/x"
    )
    assert captured["ua"] == "DF/0.1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fetch.py -v`
Expected: FAIL (`ModuleNotFoundError: dealfinder.fetch`).

- [ ] **Step 3: Implement `src/dealfinder/fetch.py`**

```python
from __future__ import annotations

import time
from typing import Any, Callable

import httpx

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class Fetcher:
    """Polite HTTP client: rate-limited, retrying, identifiable."""

    def __init__(
        self,
        *,
        min_interval: float = 2.5,
        max_retries: int = 3,
        user_agent: str = "DealFinderSA/0.1",
        sleep: Callable[[float], None] = time.sleep,
        client: httpx.Client | None = None,
    ) -> None:
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._sleep = sleep
        self._last_request_at = 0.0
        self._client = client or httpx.Client(
            headers={"User-Agent": user_agent}, timeout=30.0
        )

    def _throttle(self) -> None:
        if self._min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        wait = self._min_interval - elapsed
        if wait > 0:
            self._sleep(wait)

    def _request(self, url: str, params: dict | None, headers: dict | None) -> httpx.Response:
        attempt = 0
        while True:
            attempt += 1
            self._throttle()
            self._last_request_at = time.monotonic()
            try:
                resp = self._client.get(url, params=params, headers=headers)
            except httpx.TransportError:
                if attempt > self._max_retries:
                    raise
                self._sleep(min(2 ** attempt, 30))
                continue
            if resp.status_code in RETRYABLE_STATUS and attempt <= self._max_retries:
                self._sleep(min(2 ** attempt, 30))
                continue
            resp.raise_for_status()
            return resp

    def get_json(self, url: str, params: dict | None = None, headers: dict | None = None) -> Any:
        return self._request(url, params, headers).json()

    def get_text(self, url: str, params: dict | None = None, headers: dict | None = None) -> str:
        return self._request(url, params, headers).text

    def close(self) -> None:
        self._client.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fetch.py -v`
Expected: PASS (all three tests).

- [ ] **Step 5: Commit**

```powershell
git add src/dealfinder/fetch.py tests/test_fetch.py
git commit -m "feat: polite httpx fetch layer with retry + rate limit"
```

---

## Task 5: Adapter base + WeBuyCars adapter

> **Build-time note (important):** The sample fixture below is *illustrative*. Before relying on real data, open `https://www.webuycars.co.za/buy-a-car` in a browser, open DevTools → Network → filter `Fetch/XHR`, and find the request that returns the vehicle stock as JSON. **Save a real response** over `tests/fixtures/webuycars_search.json`, note the exact request URL/params/headers, and set `SEARCH_URL` + the key names in `_map_record` to match. The parser uses `.get()` with fallback keys so reconciliation is a single, localised edit. If the stock is only reachable by rendering the page (no clean JSON endpoint), defer this adapter and switch to Gumtree — record that decision in PROJECT.md.

**Files:**
- Create: `src/dealfinder/adapters/__init__.py`, `src/dealfinder/adapters/base.py`, `src/dealfinder/adapters/webuycars.py`, `tests/fixtures/webuycars_search.json`, `tests/test_webuycars.py`

- [ ] **Step 1: Create the adapter base `src/dealfinder/adapters/base.py`**

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from dealfinder.config import Settings
from dealfinder.fetch import Fetcher
from dealfinder.models import Listing


class Adapter(ABC):
    """A source plug-in. One per site."""

    key: str
    name: str
    tier: int

    @abstractmethod
    def fetch_listings(self, fetcher: Fetcher, settings: Settings) -> list[Listing]:
        """Return normalised listings for this source."""
        raise NotImplementedError
```

- [ ] **Step 2: Create the sample fixture `tests/fixtures/webuycars_search.json`**

```json
{
  "totalResults": 2,
  "results": [
    {
      "Id": 1001,
      "StockNumber": "WBC1001",
      "Make": "Toyota",
      "Model": "Hilux",
      "Variant": "2.4 GD-6 SRX",
      "Year": 2019,
      "Price": 339900,
      "Mileage": 145000,
      "Province": "Gauteng",
      "City": "Pretoria",
      "Images": ["https://img.webuycars.co.za/1001/a.jpg", "https://img.webuycars.co.za/1001/b.jpg"],
      "Url": "https://www.webuycars.co.za/buy-a-car/toyota-hilux/1001"
    },
    {
      "Id": 1002,
      "StockNumber": "WBC1002",
      "Make": "Volkswagen",
      "Model": "Polo",
      "Variant": "1.0 TSI Comfortline",
      "Year": 2021,
      "Price": 0,
      "Mileage": 32000,
      "Province": "Gauteng",
      "City": "Centurion",
      "Images": [],
      "Url": "https://www.webuycars.co.za/buy-a-car/vw-polo/1002"
    }
  ]
}
```

- [ ] **Step 3: Write the failing test `tests/test_webuycars.py`**

```python
import json
from pathlib import Path

from dealfinder.adapters.webuycars import WeBuyCarsAdapter
from dealfinder.models import Category

FIXTURE = Path(__file__).parent / "fixtures" / "webuycars_search.json"


def test_parse_maps_records_to_listings():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    adapter = WeBuyCarsAdapter()

    listings = adapter.parse_page(payload)

    assert len(listings) == 2
    first = listings[0]
    assert first.source_key == "webuycars"
    assert first.source_listing_id == "1001"
    assert first.category == Category.CAR
    assert first.make == "Toyota"
    assert first.model == "Hilux"
    assert first.year == 2019
    assert first.price_zar == 339900
    assert first.mileage_km == 145000
    assert first.town == "Pretoria"
    assert first.province == "Gauteng"
    assert first.image_urls[0].endswith("a.jpg")
    assert first.url.endswith("/1001")
    assert first.raw["StockNumber"] == "WBC1001"


def test_parse_keeps_zero_price_record_for_validity_layer():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    listings = WeBuyCarsAdapter().parse_page(payload)
    second = listings[1]
    # Parsing does not judge validity; price 0 is passed through as-is.
    assert second.price_zar == 0
    assert second.image_urls == []
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_webuycars.py -v`
Expected: FAIL (`ModuleNotFoundError: dealfinder.adapters.webuycars`).

- [ ] **Step 5: Implement `src/dealfinder/adapters/webuycars.py`**

```python
from __future__ import annotations

from typing import Any

from dealfinder.adapters.base import Adapter
from dealfinder.config import Settings
from dealfinder.fetch import Fetcher
from dealfinder.models import Category, Listing

# Reconcile with the real captured request at build time (see Task 5 build-time note).
SEARCH_URL = "https://www.webuycars.co.za/api/vehicles/search"


def _first(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


class WeBuyCarsAdapter(Adapter):
    key = "webuycars"
    name = "WeBuyCars"
    tier = 1

    def parse_page(self, payload: dict[str, Any]) -> list[Listing]:
        records = payload.get("results") or payload.get("Results") or []
        return [self._map_record(r) for r in records]

    def _map_record(self, r: dict[str, Any]) -> Listing:
        rid = str(_first(r, "Id", "id", "StockNumber"))
        return Listing(
            source_key=self.key,
            source_listing_id=rid,
            url=_first(r, "Url", "url") or f"https://www.webuycars.co.za/buy-a-car/{rid}",
            category=Category.CAR,
            title=_first(r, "Title")
            or " ".join(
                str(x)
                for x in (_first(r, "Year"), _first(r, "Make"), _first(r, "Model"), _first(r, "Variant"))
                if x is not None
            ).strip()
            or None,
            make=_first(r, "Make", "make"),
            model=_first(r, "Model", "model"),
            variant=_first(r, "Variant", "variant"),
            year=_first(r, "Year", "year"),
            price_zar=_first(r, "Price", "price"),
            mileage_km=_first(r, "Mileage", "mileage", "Kilometers"),
            province=_first(r, "Province", "province"),
            town=_first(r, "City", "city", "Town"),
            image_urls=list(_first(r, "Images", "images") or []),
            raw=r,
        )

    def fetch_listings(self, fetcher: Fetcher, settings: Settings) -> list[Listing]:
        max_pages = settings.sources["webuycars"].max_pages
        out: list[Listing] = []
        for page in range(1, max_pages + 1):
            payload = fetcher.get_json(SEARCH_URL, params={"page": page})
            page_listings = self.parse_page(payload)
            if not page_listings:
                break
            out.extend(page_listings)
        return out
```

- [ ] **Step 6: Create the adapter registry `src/dealfinder/adapters/__init__.py`**

```python
from __future__ import annotations

from dealfinder.adapters.base import Adapter
from dealfinder.adapters.webuycars import WeBuyCarsAdapter
from dealfinder.config import Settings

_ALL: dict[str, type[Adapter]] = {
    WeBuyCarsAdapter.key: WeBuyCarsAdapter,
}


def build_enabled_adapters(settings: Settings) -> list[Adapter]:
    return [
        cls()
        for key, cls in _ALL.items()
        if settings.sources.get(key) and settings.sources[key].enabled
    ]
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_webuycars.py -v`
Expected: PASS (both tests).

- [ ] **Step 8: Commit**

```powershell
git add src/dealfinder/adapters tests/test_webuycars.py tests/fixtures/webuycars_search.json
git commit -m "feat: adapter base + WeBuyCars adapter (fixture-driven parse)"
```

---

## Task 6: Validity engine (basic)

**Files:**
- Create: `src/dealfinder/validity.py`, `tests/test_validity.py`

- [ ] **Step 1: Write the failing test `tests/test_validity.py`**

```python
from dealfinder.models import Category, Listing
from dealfinder.validity import evaluate_validity


def _listing(**over):
    base = dict(
        source_key="webuycars",
        source_listing_id="1",
        url="https://x/1",
        category=Category.CAR,
        title="2019 Toyota Hilux",
        make="Toyota",
        model="Hilux",
        year=2019,
        price_zar=339900,
        town="Pretoria",
        image_urls=["https://img/1.jpg"],
    )
    base.update(over)
    return Listing(**base)


def test_complete_listing_is_valid(settings):
    result = evaluate_validity(_listing(), settings)
    assert result.is_valid is True
    assert result.flags == []


def test_missing_price_is_invalid(settings):
    result = evaluate_validity(_listing(price_zar=None), settings)
    assert result.is_valid is False
    assert "missing_price" in result.flags


def test_zero_price_flagged_as_implausible(settings):
    result = evaluate_validity(_listing(price_zar=0), settings)
    assert result.is_valid is False
    assert "price_implausible" in result.flags


def test_no_images_flagged_but_not_fatal(settings):
    result = evaluate_validity(_listing(image_urls=[]), settings)
    assert "missing_images" in result.flags
    # missing images is a quality warning, not fatal on its own
    assert result.is_valid is True


def test_missing_identity_is_invalid(settings):
    result = evaluate_validity(_listing(make=None, model=None, title=None), settings)
    assert result.is_valid is False
    assert "missing_identity" in result.flags
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validity.py -v`
Expected: FAIL (`ModuleNotFoundError: dealfinder.validity`).

- [ ] **Step 3: Implement `src/dealfinder/validity.py`**

```python
from __future__ import annotations

from dealfinder.config import Settings
from dealfinder.models import Listing, ValidityResult

# Flags that make a listing unusable (not alertable).
FATAL_FLAGS = {"missing_price", "price_implausible", "missing_identity", "missing_location"}


def evaluate_validity(listing: Listing, settings: Settings) -> ValidityResult:
    flags: list[str] = []

    if listing.price_zar is None:
        flags.append("missing_price")
    elif (
        listing.price_zar < settings.validity.min_price_zar
        or listing.price_zar > settings.validity.max_price_zar
    ):
        flags.append("price_implausible")

    if not (listing.make or listing.model or listing.title):
        flags.append("missing_identity")

    if not (listing.town or listing.province):
        flags.append("missing_location")

    if not listing.image_urls:
        flags.append("missing_images")

    is_valid = not (set(flags) & FATAL_FLAGS)
    return ValidityResult(is_valid=is_valid, flags=flags)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_validity.py -v`
Expected: PASS (all five tests).

- [ ] **Step 5: Commit**

```powershell
git add src/dealfinder/validity.py tests/test_validity.py
git commit -m "feat: basic validity engine (completeness + price sanity)"
```

---

## Task 7: Supabase schema + repository

**Files:**
- Create: `migrations/001_core.sql`, `src/dealfinder/db.py`, `tests/test_db.py`

- [ ] **Step 1: Create the schema `migrations/001_core.sql`**

```sql
-- DealFinderSA core schema (Plan 1). Run in Supabase SQL editor.

create table if not exists sources (
    key        text primary key,
    name       text not null,
    tier       int  not null default 1,
    enabled    boolean not null default true,
    base_url   text
);

create table if not exists listings (
    id                uuid primary key default gen_random_uuid(),
    source_key        text not null,
    source_listing_id text not null,
    url               text not null,
    category          text not null,
    title             text,
    make              text,
    model             text,
    variant           text,
    year              int,
    price_zar         bigint,
    mileage_km        int,
    engine_hours      int,
    province          text,
    town              text,
    lat               double precision,
    lng               double precision,
    seller_type       text default 'unknown',
    seller_name       text,
    seller_phone      text,
    description       text,
    image_urls        jsonb default '[]'::jsonb,
    posted_at         timestamptz,
    first_seen_at     timestamptz not null default now(),
    last_seen_at      timestamptz not null default now(),
    status            text not null default 'active',
    is_valid          boolean not null default true,
    quality_flags     jsonb default '[]'::jsonb,
    raw               jsonb,
    unique (source_key, source_listing_id)
);

create index if not exists listings_category_idx on listings (category);
create index if not exists listings_valid_idx on listings (is_valid);

create table if not exists runs (
    id            uuid primary key default gen_random_uuid(),
    started_at    timestamptz not null default now(),
    finished_at   timestamptz,
    source_keys   jsonb default '[]'::jsonb,
    fetched       int default 0,
    upserted      int default 0,
    invalid       int default 0,
    errors        jsonb default '[]'::jsonb
);

create table if not exists sources_health (
    source_key      text primary key,
    last_run_at     timestamptz,
    last_success_at timestamptz,
    listings_found  int default 0,
    errors          text,
    status          text
);

insert into sources (key, name, tier, enabled, base_url)
values ('webuycars', 'WeBuyCars', 1, true, 'https://www.webuycars.co.za')
on conflict (key) do nothing;
```

- [ ] **Step 2: Write the failing test `tests/test_db.py`**

```python
from datetime import datetime

from dealfinder.db import InMemoryRepository, listing_to_row
from dealfinder.models import RunStats


def test_listing_to_row_serialises_enums_and_lists(sample_listing):
    sample_listing.quality_flags = ["missing_images"]
    row = listing_to_row(sample_listing)
    assert row["source_key"] == "webuycars"
    assert row["source_listing_id"] == "123"
    assert row["category"] == "car"           # enum -> value
    assert row["status"] == "active"
    assert row["image_urls"] == ["https://img/1.jpg"]
    assert row["quality_flags"] == ["missing_images"]
    assert "last_seen_at" in row              # refreshed each upsert
    assert "first_seen_at" not in row         # preserved by DB default/on insert


def test_inmemory_repo_upserts_by_natural_key(sample_listing):
    repo = InMemoryRepository()
    assert repo.upsert_listings([sample_listing]) == 1
    # second upsert of same natural key updates, not duplicates
    sample_listing.price_zar = 320000
    assert repo.upsert_listings([sample_listing]) == 1
    stored = repo.get("webuycars", "123")
    assert stored.price_zar == 320000
    assert len(repo.all()) == 1


def test_inmemory_repo_records_run():
    repo = InMemoryRepository()
    repo.record_run(RunStats(source_keys=["webuycars"], fetched=2, upserted=1, invalid=1))
    assert repo.runs[-1].fetched == 2
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL (`ModuleNotFoundError: dealfinder.db`).

- [ ] **Step 4: Implement `src/dealfinder/db.py`**

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from dealfinder.models import Listing, RunStats


def listing_to_row(listing: Listing) -> dict:
    """Map a Listing to a Supabase row. Omits first_seen_at so it is preserved on update."""
    data = listing.model_dump(mode="json", exclude={"raw"})
    data["raw"] = listing.raw
    data["last_seen_at"] = datetime.now(timezone.utc).isoformat()
    return data


class ListingRepository(Protocol):
    def upsert_listings(self, listings: list[Listing]) -> int: ...
    def record_run(self, run: RunStats) -> None: ...


class InMemoryRepository:
    """Test/dev repository. Keyed by (source_key, source_listing_id)."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], Listing] = {}
        self.runs: list[RunStats] = []

    def upsert_listings(self, listings: list[Listing]) -> int:
        for listing in listings:
            self._store[(listing.source_key, listing.source_listing_id)] = listing
        return len(listings)

    def record_run(self, run: RunStats) -> None:
        self.runs.append(run)

    def get(self, source_key: str, source_listing_id: str) -> Listing | None:
        return self._store.get((source_key, source_listing_id))

    def all(self) -> list[Listing]:
        return list(self._store.values())


class SupabaseRepository:
    """Real repository backed by Supabase (PostgREST)."""

    def __init__(self, url: str, key: str) -> None:
        from supabase import create_client

        self._client = create_client(url, key)

    def upsert_listings(self, listings: list[Listing]) -> int:
        if not listings:
            return 0
        rows = [listing_to_row(item) for item in listings]
        self._client.table("listings").upsert(
            rows, on_conflict="source_key,source_listing_id"
        ).execute()
        return len(rows)

    def record_run(self, run: RunStats) -> None:
        self._client.table("runs").insert(
            {
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "source_keys": run.source_keys,
                "fetched": run.fetched,
                "upserted": run.upserted,
                "invalid": run.invalid,
                "errors": run.errors,
            }
        ).execute()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_db.py -v`
Expected: PASS (all three tests).

- [ ] **Step 6: Apply the schema to Supabase (manual, one-time)**

1. Create a Supabase project at https://supabase.com (free tier).
2. Copy Project URL + `service_role` key into `.env` (use `.env.example` as the template).
3. Open Supabase → SQL Editor → paste the contents of `migrations/001_core.sql` → Run.
4. Confirm tables `sources`, `listings`, `runs`, `sources_health` exist under Table Editor.

- [ ] **Step 7: Commit**

```powershell
git add migrations/001_core.sql src/dealfinder/db.py tests/test_db.py
git commit -m "feat: supabase schema + repository (in-memory + supabase impls)"
```

---

## Task 8: Pipeline + CLI

**Files:**
- Create: `src/dealfinder/pipeline.py`, `src/dealfinder/cli.py`, `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test `tests/test_pipeline.py`**

```python
from dealfinder.adapters.base import Adapter
from dealfinder.db import InMemoryRepository
from dealfinder.models import Category, Listing
from dealfinder.pipeline import run_pipeline


class FakeAdapter(Adapter):
    key = "fake"
    name = "Fake"
    tier = 1

    def __init__(self, listings):
        self._listings = listings

    def fetch_listings(self, fetcher, settings):
        return self._listings


def _listing(lid, price, town="Pretoria", images=("https://img/1.jpg")):
    return Listing(
        source_key="fake",
        source_listing_id=lid,
        url=f"https://x/{lid}",
        category=Category.CAR,
        title="2019 Toyota Hilux",
        make="Toyota",
        model="Hilux",
        year=2019,
        price_zar=price,
        town=town,
        image_urls=list(images) if isinstance(images, (list, tuple)) else [images],
    )


def test_pipeline_upserts_valid_marks_invalid(settings):
    good = _listing("1", 339900)
    bad = _listing("2", 0)  # implausible price -> invalid
    repo = InMemoryRepository()

    stats = run_pipeline(
        adapters=[FakeAdapter([good, bad])], fetcher=None, repo=repo, settings=settings
    )

    assert stats.fetched == 2
    assert stats.upserted == 2          # both stored
    assert stats.invalid == 1           # one marked invalid
    stored_bad = repo.get("fake", "2")
    assert stored_bad.is_valid is False
    assert "price_implausible" in stored_bad.quality_flags
    stored_good = repo.get("fake", "1")
    assert stored_good.is_valid is True
    assert len(repo.runs) == 1


def test_pipeline_isolates_failing_adapter(settings):
    class BoomAdapter(FakeAdapter):
        key = "boom"

        def fetch_listings(self, fetcher, settings):
            raise RuntimeError("source down")

    repo = InMemoryRepository()
    stats = run_pipeline(
        adapters=[BoomAdapter([]), FakeAdapter([_listing("1", 339900)])],
        fetcher=None,
        repo=repo,
        settings=settings,
    )
    # one adapter blew up, the other still produced a listing
    assert stats.upserted == 1
    assert any("boom" in e for e in stats.errors)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL (`ModuleNotFoundError: dealfinder.pipeline`).

- [ ] **Step 3: Implement `src/dealfinder/pipeline.py`**

```python
from __future__ import annotations

from dealfinder.adapters.base import Adapter
from dealfinder.config import Settings
from dealfinder.db import ListingRepository
from dealfinder.fetch import Fetcher
from dealfinder.models import RunStats
from dealfinder.validity import evaluate_validity


def run_pipeline(
    *,
    adapters: list[Adapter],
    fetcher: Fetcher | None,
    repo: ListingRepository,
    settings: Settings,
) -> RunStats:
    stats = RunStats(source_keys=[a.key for a in adapters])

    for adapter in adapters:
        try:
            listings = adapter.fetch_listings(fetcher, settings)
        except Exception as exc:  # isolate per-source failures
            stats.errors.append(f"{adapter.key}: {exc}")
            continue

        for listing in listings:
            stats.fetched += 1
            result = evaluate_validity(listing, settings)
            listing.is_valid = result.is_valid
            listing.quality_flags = result.flags
            if not result.is_valid:
                stats.invalid += 1

        stats.upserted += repo.upsert_listings(listings)

    repo.record_run(stats)
    return stats
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Implement the CLI `src/dealfinder/cli.py`**

```python
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
    sql = (Path(__file__).resolve().parents[2] / "migrations" / "001_core.sql").read_text("utf-8")
    print("Run the following SQL in the Supabase SQL editor:\n")
    print(sql)


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
        f"upserted={stats.upserted} invalid={stats.invalid} errors={stats.errors}"
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
```

- [ ] **Step 6: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```powershell
git add src/dealfinder/pipeline.py src/dealfinder/cli.py tests/test_pipeline.py
git commit -m "feat: pipeline + dealfinder CLI (init-db, run-scrape)"
```

---

## Task 9: End-to-end verification + README

**Files:**
- Create: `README.md`
- Modify: `PROJECT.md` (progress log + next steps)

- [ ] **Step 1: Reconcile the WeBuyCars adapter with the live API**

Follow the build-time note in Task 5: capture a real response into `tests/fixtures/webuycars_search.json`, set `SEARCH_URL` and confirm `_map_record` key names. Re-run `pytest tests/test_webuycars.py -v` — adjust key names until green against the real shape.

- [ ] **Step 2: Run a real scrape end-to-end**

Run (venv active, `.env` filled, schema applied):
```powershell
dealfinder run-scrape
```
Expected: a line like `Done. sources=['webuycars'] fetched=NN upserted=NN invalid=N errors=[]`.

- [ ] **Step 3: Verify rows in Supabase**

In Supabase → Table Editor → `listings`: confirm rows exist with `is_valid=true` for sensible cars and `is_valid=false` (with `quality_flags`) for any zero-price/incomplete ones. Confirm a row appeared in `runs`.

- [ ] **Step 4: Write `README.md`**

````markdown
# DealFinderSA

Personal vehicle-flipping deal radar. Scrapes SA vehicle sources, validates and (later)
scores listings, and surfaces underpriced deals near Hartbeespoort.

## Setup (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env   # then fill in SUPABASE_URL + SUPABASE_KEY
```

Apply the database schema: run `dealfinder init-db` and paste the printed SQL into the
Supabase SQL editor (one-time).

## Use

```powershell
dealfinder run-scrape   # scrape enabled sources into Supabase
pytest -q               # run the test suite
```

Configuration (home location, radius, politeness, enabled sources) lives in
`config/default.yaml`. Secrets live in `.env` (never committed).

## Status

Plan 1 (walking skeleton) — WeBuyCars → validate → Supabase. See `docs/plans/` and
`docs/specs/` for the roadmap.
````

- [ ] **Step 5: Update `PROJECT.md`**

Add a Progress Log row dated today: "Plan 1 (walking skeleton) implemented: package scaffold, config, Listing model, polite fetch layer, WeBuyCars adapter, validity engine, Supabase schema + repository, pipeline + CLI. End-to-end `run-scrape` verified into Supabase." Update Next Steps to point at Plan 2 (dedup & clustering).

- [ ] **Step 6: Commit**

```powershell
git add README.md PROJECT.md tests/fixtures/webuycars_search.json src/dealfinder/adapters/webuycars.py
git commit -m "docs: README + project status; reconcile WeBuyCars live API"
```

---

## Self-Review (completed by plan author)

**Spec coverage (Plan 1 scope = spec §12 steps 1–4 + foundation):**
- DB schema + Supabase client + init-db → Task 7 ✅
- Polite fetch layer → Task 4 ✅
- First Tier-1 adapter (WeBuyCars, JSON API, golden-file tests) → Task 5 ✅
- Normalisation → `Listing` model (Task 3) + adapter mapping (Task 5) ✅
- Validity engine (completeness + price sanity) → Task 6 ✅
- Pipeline + per-source isolation + run logging + CLI → Task 8 ✅
- Portability (all in-folder, `.env` for secrets) → Tasks 1–2 ✅
- Deferred to later plans (correctly out of Plan 1 scope): dedup/clustering, price history, scoring, watches, email alerts, UI, scheduling, Tier-2 social, live-status revalidation, image caching, scam heuristics.

**Placeholder scan:** No "TBD/TODO/handle edge cases" steps. The single build-time reconciliation (WeBuyCars live keys) is an explicit, actionable task (Task 5 note + Task 9 step 1), not a vague placeholder — inherent to any third-party scrape.

**Type consistency:** `Adapter.fetch_listings(fetcher, settings)` signature is identical in base (Task 5), WeBuyCars (Task 5), FakeAdapter (Task 8) and pipeline call (Task 8). `Listing`, `ValidityResult`, `RunStats` fields used in tests match `models.py` (Task 3). `ListingRepository.upsert_listings`/`record_run` match both `InMemoryRepository` and `SupabaseRepository` (Task 7) and the pipeline (Task 8). `listing_to_row` excludes `first_seen_at` and sets `last_seen_at`, consistent with the schema defaults (Task 7).
