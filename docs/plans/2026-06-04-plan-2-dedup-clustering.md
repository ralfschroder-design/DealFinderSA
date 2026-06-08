# DealFinderSA — Plan 2: Dedup & Clustering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Group listings that are the same physical vehicle into one cluster (so the same car cross-posted on several sites is seen once), extract seller phone numbers as a same-seller signal, and track each listing's price over time.

**Architecture:** Add a deterministic `fingerprint` (a hash of the vehicle's identifying attributes — make/model/variant/year/mileage-band/province, deliberately **excluding price** so price differences don't split a cluster) computed for every listing; extract SA phone numbers from descriptions; record a `price_history` observation whenever a valid listing's price changes; and expose a `vehicle_clusters` SQL view that groups listings by fingerprint. The pipeline (from Plan 1) is extended to do all this inline.

**Tech Stack:** Same as Plan 1 — Python 3.12+, pydantic v2, Supabase (Postgres), pytest. No new dependencies (uses stdlib `hashlib` + `re`).

**Builds on:** Plan 1 (`docs/plans/2026-06-02-plan-1-walking-skeleton.md`). All Plan 1 modules exist and 19 tests pass.

**Deferred (NOT in this plan):** image perceptual-hash (pHash) dedup — needs image downloads + an image library; will be its own slice once image-fetch infra exists. Phone is stored and extracted here but used as a *display/secondary* signal; transitive phone-based merging (and dealer-phone handling) is also deferred. v1 clustering = group-by-fingerprint.

---

## Conventions
- Windows / PowerShell. Run Python via the venv interpreter directly: `.\.venv\Scripts\python.exe -m pytest ...`.
- TDD per task: write failing test → see it fail → implement → see it pass → commit.
- Commit messages as shown. Branch `master`.

## File Structure (this plan)

| File | Change | Responsibility |
|---|---|---|
| `src/dealfinder/models.py` | Modify | Add `fingerprint` to `Listing`; add `price_points` to `RunStats` |
| `migrations/002_clustering.sql` | Create | Add `fingerprint` column + indexes to `listings`; create `price_history` table + `vehicle_clusters` view |
| `src/dealfinder/fingerprint.py` | Create | `compute_fingerprint(listing) -> str` |
| `src/dealfinder/phone.py` | Create | `extract_phone(text) -> str | None`, `normalize_phone` |
| `src/dealfinder/db.py` | Modify | Add `record_price_if_changed` to Protocol + `InMemoryRepository` + `SupabaseRepository` |
| `src/dealfinder/pipeline.py` | Modify | Compute fingerprint, fill phone, record price changes |
| `tests/test_fingerprint.py` | Create | fingerprint behaviour |
| `tests/test_phone.py` | Create | phone extraction |
| `tests/test_db.py` | Modify | price-history repo behaviour |
| `tests/test_pipeline.py` | Modify | pipeline now clusters + records price |
| `README.md`, `PROJECT.md` | Modify | Status + migration-apply note |

---

## Task 1: Model fields + migration 002

**Files:** Modify `src/dealfinder/models.py`; Create `migrations/002_clustering.sql`; Modify `tests/test_models.py`.

- [ ] **Step 1: Add a failing test to `tests/test_models.py`** (append at end of file)

```python
def test_listing_has_fingerprint_field_default_none():
    from dealfinder.models import Category, Listing, RunStats

    listing = Listing(
        source_key="s", source_listing_id="1", url="u", category=Category.CAR
    )
    assert listing.fingerprint is None
    assert RunStats().price_points == 0
```

- [ ] **Step 2: Run it, watch it fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_models.py::test_listing_has_fingerprint_field_default_none -v`
Expected: FAIL (`AttributeError`/validation — no `fingerprint` / `price_points`).

- [ ] **Step 3: Edit `src/dealfinder/models.py`** — add one field to `Listing` (place it just after `quality_flags`):

```python
    fingerprint: str | None = None
```

And add one field to `RunStats` (after `invalid`):

```python
    price_points: int = 0
```

- [ ] **Step 4: Run the test, watch it pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_models.py -v`
Expected: PASS (all model tests).

- [ ] **Step 5: Create `migrations/002_clustering.sql`**

```sql
-- DealFinderSA clustering schema (Plan 2). Run in Supabase SQL editor AFTER 001.

alter table listings add column if not exists fingerprint text;
create index if not exists listings_fingerprint_idx on listings (fingerprint);

create table if not exists price_history (
    id                uuid primary key default gen_random_uuid(),
    source_key        text not null,
    source_listing_id text not null,
    fingerprint       text,
    price_zar         bigint,
    observed_at       timestamptz not null default now()
);
create index if not exists price_history_key_idx on price_history (source_key, source_listing_id);
create index if not exists price_history_fp_idx on price_history (fingerprint);

-- Same-vehicle view: groups valid listings by fingerprint, shows price spread + sources.
create or replace view vehicle_clusters as
select
    fingerprint,
    count(*)                       as listing_count,
    min(price_zar)                 as min_price_zar,
    max(price_zar)                 as max_price_zar,
    array_agg(distinct source_key) as sources,
    max(make)                      as make,
    max(model)                     as model,
    max(year)                      as year
from listings
where is_valid = true and fingerprint is not null
group by fingerprint;
```

- [ ] **Step 6: Run the full suite** (no regressions from the model change)

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: all pass (20 now — the 19 from Plan 1 + the new model test).

- [ ] **Step 7: Commit**

```powershell
git add src/dealfinder/models.py migrations/002_clustering.sql tests/test_models.py
git commit -m "feat: add fingerprint field + price_history schema (plan 2 task 1)"
```

---

## Task 2: Fingerprint function

**Files:** Create `src/dealfinder/fingerprint.py`, `tests/test_fingerprint.py`.

- [ ] **Step 1: Write the failing test `tests/test_fingerprint.py`**

```python
from dealfinder.fingerprint import compute_fingerprint
from dealfinder.models import Category, Listing


def _car(**over):
    base = dict(
        source_key="webuycars",
        source_listing_id="1",
        url="https://x/1",
        category=Category.CAR,
        make="Toyota",
        model="Hilux",
        variant="2.4 GD-6 SRX",
        year=2019,
        mileage_km=145000,
        price_zar=339900,
        province="Gauteng",
    )
    base.update(over)
    return Listing(**base)


def test_same_vehicle_same_fingerprint_regardless_of_price():
    # Same car cross-posted at different prices must share a fingerprint.
    a = _car(source_listing_id="1", price_zar=339900)
    b = _car(source_listing_id="2", price_zar=345000)
    assert compute_fingerprint(a) == compute_fingerprint(b)


def test_mileage_within_band_matches_across_band_differs():
    a = _car(mileage_km=145000)
    b = _car(mileage_km=148000)  # same 10k band (14)
    c = _car(mileage_km=152000)  # next band (15)
    assert compute_fingerprint(a) == compute_fingerprint(b)
    assert compute_fingerprint(a) != compute_fingerprint(c)


def test_different_model_differs():
    a = _car(model="Hilux")
    b = _car(model="Ranger")
    assert compute_fingerprint(a) != compute_fingerprint(b)


def test_variant_normalised():
    a = _car(variant="2.4 GD-6 SRX")
    b = _car(variant="2.4 GD6 SRX")  # punctuation/spacing differences normalise away
    assert compute_fingerprint(a) == compute_fingerprint(b)


def test_fingerprint_is_stable_hex_string():
    fp = compute_fingerprint(_car())
    assert isinstance(fp, str) and len(fp) == 16
```

- [ ] **Step 2: Run, watch it fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_fingerprint.py -v`
Expected: FAIL (`ModuleNotFoundError: dealfinder.fingerprint`).

- [ ] **Step 3: Implement `src/dealfinder/fingerprint.py`**

```python
from __future__ import annotations

import hashlib
import re

from dealfinder.models import Listing


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _alnum(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _mileage_band(km: int | None) -> str:
    return "na" if km is None else str(km // 10000)  # 10,000 km bands


def compute_fingerprint(listing: Listing) -> str:
    """Deterministic same-vehicle key. Excludes price on purpose, so the same
    car listed at different prices clusters together."""
    parts = [
        listing.category.value,
        _norm(listing.make),
        _norm(listing.model),
        _alnum(listing.variant),
        str(listing.year or ""),
        _mileage_band(listing.mileage_km),
        _norm(listing.province),
    ]
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
```

- [ ] **Step 4: Run, watch it pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_fingerprint.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```powershell
git add src/dealfinder/fingerprint.py tests/test_fingerprint.py
git commit -m "feat: deterministic vehicle fingerprint (plan 2 task 2)"
```

---

## Task 3: SA phone extraction

**Files:** Create `src/dealfinder/phone.py`, `tests/test_phone.py`.

- [ ] **Step 1: Write the failing test `tests/test_phone.py`**

```python
from dealfinder.phone import extract_phone, normalize_phone


def test_normalize_local_format():
    assert normalize_phone("082 123 4567") == "0821234567"


def test_normalize_plus_27():
    assert normalize_phone("+27 82 123 4567") == "0821234567"


def test_normalize_rejects_too_short():
    assert normalize_phone("123") is None


def test_extract_from_description():
    assert extract_phone("Please call me on 082-123-4567 after 5pm") == "0821234567"


def test_extract_plus27_in_text():
    assert extract_phone("WhatsApp +27821234567 for viewing") == "0821234567"


def test_extract_none_when_absent():
    assert extract_phone("No number here, email only") is None


def test_extract_handles_empty():
    assert extract_phone(None) is None
    assert extract_phone("") is None
```

- [ ] **Step 2: Run, watch it fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_phone.py -v`
Expected: FAIL (`ModuleNotFoundError: dealfinder.phone`).

- [ ] **Step 3: Implement `src/dealfinder/phone.py`**

```python
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
```

- [ ] **Step 4: Run, watch it pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_phone.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```powershell
git add src/dealfinder/phone.py tests/test_phone.py
git commit -m "feat: SA phone-number extraction (plan 2 task 3)"
```

---

## Task 4: Price-history repository method

**Files:** Modify `src/dealfinder/db.py`; Modify `tests/test_db.py`.

- [ ] **Step 1: Add a failing test to `tests/test_db.py`** (append)

```python
def test_record_price_if_changed(sample_listing):
    from dealfinder.db import InMemoryRepository

    repo = InMemoryRepository()
    # first observation is always recorded
    assert repo.record_price_if_changed(sample_listing) is True
    # same price again → not recorded
    assert repo.record_price_if_changed(sample_listing) is False
    # changed price → recorded
    sample_listing.price_zar = 329900
    assert repo.record_price_if_changed(sample_listing) is True
    assert len(repo.prices) == 2


def test_record_price_ignores_missing_price(sample_listing):
    from dealfinder.db import InMemoryRepository

    sample_listing.price_zar = None
    repo = InMemoryRepository()
    assert repo.record_price_if_changed(sample_listing) is False
    assert repo.prices == []
```

- [ ] **Step 2: Run, watch it fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_db.py -k record_price -v`
Expected: FAIL (`AttributeError: 'InMemoryRepository' object has no attribute 'record_price_if_changed'` / no `prices`).

- [ ] **Step 3: Edit `src/dealfinder/db.py`**

(a) Add to the `ListingRepository` Protocol (a new method line):

```python
    def record_price_if_changed(self, listing: Listing) -> bool: ...
```

(b) In `InMemoryRepository.__init__`, add two attributes (after `self.runs`):

```python
        self.prices: list[dict] = []
        self._last_price: dict[tuple[str, str], int] = {}
```

(c) Add this method to `InMemoryRepository`:

```python
    def record_price_if_changed(self, listing: Listing) -> bool:
        if listing.price_zar is None:
            return False
        key = (listing.source_key, listing.source_listing_id)
        if self._last_price.get(key) == listing.price_zar:
            return False
        self._last_price[key] = listing.price_zar
        self.prices.append(
            {
                "source_key": listing.source_key,
                "source_listing_id": listing.source_listing_id,
                "fingerprint": listing.fingerprint,
                "price_zar": listing.price_zar,
            }
        )
        return True
```

(d) Add this method to `SupabaseRepository`:

```python
    def record_price_if_changed(self, listing: Listing) -> bool:
        if listing.price_zar is None:
            return False
        resp = (
            self._client.table("price_history")
            .select("price_zar")
            .eq("source_key", listing.source_key)
            .eq("source_listing_id", listing.source_listing_id)
            .order("observed_at", desc=True)
            .limit(1)
            .execute()
        )
        last = resp.data[0]["price_zar"] if resp.data else None
        if last == listing.price_zar:
            return False
        self._client.table("price_history").insert(
            {
                "source_key": listing.source_key,
                "source_listing_id": listing.source_listing_id,
                "fingerprint": listing.fingerprint,
                "price_zar": listing.price_zar,
            }
        ).execute()
        return True
```

- [ ] **Step 4: Run, watch it pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_db.py -v`
Expected: PASS (all db tests — the 3 originals + 2 new).

- [ ] **Step 5: Commit**

```powershell
git add src/dealfinder/db.py tests/test_db.py
git commit -m "feat: record price history on change (plan 2 task 4)"
```

---

## Task 5: Pipeline integration

**Files:** Modify `src/dealfinder/pipeline.py`; Modify `tests/test_pipeline.py`.

- [ ] **Step 1: Add a failing test to `tests/test_pipeline.py`** (append; reuse the existing `FakeAdapter` and `_listing` helper in that file)

```python
def test_pipeline_fingerprints_extracts_phone_records_price(settings):
    from dealfinder.db import InMemoryRepository
    from dealfinder.pipeline import run_pipeline

    listing = _listing("1", 339900)
    listing.description = "Mint condition. Call 082 123 4567 to view."
    listing.seller_phone = None
    repo = InMemoryRepository()

    stats = run_pipeline(adapters=[FakeAdapter([listing])], fetcher=None, repo=repo, settings=settings)

    stored = repo.get("fake", "1")
    assert stored.fingerprint is not None and len(stored.fingerprint) == 16
    assert stored.seller_phone == "0821234567"
    assert stats.price_points == 1
    assert len(repo.prices) == 1


def test_pipeline_same_vehicle_shares_fingerprint(settings):
    from dealfinder.db import InMemoryRepository
    from dealfinder.pipeline import run_pipeline

    a = _listing("1", 339900)
    b = _listing("2", 351000)  # same car attrs, different id + price
    repo = InMemoryRepository()

    run_pipeline(adapters=[FakeAdapter([a, b])], fetcher=None, repo=repo, settings=settings)

    assert repo.get("fake", "1").fingerprint == repo.get("fake", "2").fingerprint
```

- [ ] **Step 2: Run, watch it fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py -k "fingerprint or phone" -v`
Expected: FAIL (`fingerprint` is None / `price_points` missing / phone not set).

- [ ] **Step 3: Edit `src/dealfinder/pipeline.py`**

(a) Add two imports at the top (with the other `dealfinder` imports):

```python
from dealfinder.fingerprint import compute_fingerprint
from dealfinder.phone import extract_phone
```

(b) Replace the inner `for listing in listings:` loop body so it computes the fingerprint, fills the phone, then validates and records price. The full updated loop:

```python
        for listing in listings:
            stats.fetched += 1
            listing.fingerprint = compute_fingerprint(listing)
            if not listing.seller_phone:
                listing.seller_phone = extract_phone(listing.description)
            result = evaluate_validity(listing, settings)
            listing.is_valid = result.is_valid
            listing.quality_flags = result.flags
            if not result.is_valid:
                stats.invalid += 1
            elif repo.record_price_if_changed(listing):
                stats.price_points += 1

        stats.upserted += repo.upsert_listings(listings)
```

(Only valid listings get a price-history entry; invalid ones are still stored by the existing `upsert_listings` call.)

- [ ] **Step 4: Run, watch it pass — then the full suite**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py -v`
Then: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: all pass (the two new pipeline tests + the two originals still green; full suite ~24 total).

- [ ] **Step 5: Commit**

```powershell
git add src/dealfinder/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline computes fingerprint, fills phone, records price (plan 2 task 5)"
```

---

## Task 6: Docs + finalize (migration apply is user-gated)

**Files:** Modify `README.md`, `PROJECT.md`.

- [ ] **Step 1: Update `README.md`** — under the "Go-live checklist" add a step:

```
5. After pulling Plan 2, apply `migrations/002_clustering.sql` in the Supabase SQL editor
   (adds the `fingerprint` column, the `price_history` table, and the `vehicle_clusters` view).
```

And change the Status line to: `Plan 1 + Plan 2 (dedup, phone, price history). NN tests passing.` (use the real count from `pytest -q`).

- [ ] **Step 2: Update `PROJECT.md`** — add a Progress Log row dated `2026-06-04`:

```
| 2026-06-04 | Implemented **Plan 2 — dedup & clustering**: vehicle `fingerprint` (price-independent), SA phone extraction, `price_history` (record-on-change) + `vehicle_clusters` view, wired into the pipeline. TDD; full suite green. Image pHash + transitive phone-merge deferred. New migration `002_clustering.sql` is user-gated (apply in Supabase). |
```

Update Next Steps so item 2 becomes **Plan 3 — scoring** and add a note that `002_clustering.sql` must be applied during go-live.

- [ ] **Step 3: Confirm suite + commit**

Run: `.\.venv\Scripts\python.exe -m pytest -q` (confirm count, update README if needed)

```powershell
git add README.md PROJECT.md
git commit -m "docs: Plan 2 status + migration note"
```

---

## Self-Review (plan author)

**Spec coverage (spec §4.3 dedup/clustering + data model):**
- Fingerprint of vehicle attributes → Task 2 ✅ (price excluded by design — sounder for dedup; noted)
- Phone extracted as a same-seller signal → Task 3, stored via pipeline Task 5 ✅
- Price history → Tasks 1 (table) + 4 (record-on-change) + 5 (pipeline) ✅
- Cluster grouping → `vehicle_clusters` view (Task 1) + shared fingerprint (Tasks 2/5) ✅
- Deferred & documented: image pHash, transitive phone-merge, dedup of dealer phones.

**Placeholder scan:** No TBD/TODO. Every step has exact code/commands.

**Type consistency:** `compute_fingerprint(listing) -> str` used identically in fingerprint.py (T2), pipeline (T5), tests. `record_price_if_changed(self, listing) -> bool` identical in Protocol, InMemoryRepository, SupabaseRepository (T4) and pipeline call (T5). New model fields `Listing.fingerprint` / `RunStats.price_points` (T1) are referenced by T4/T5 tests and pipeline. `price_history` columns (T1 SQL) match the dict keys inserted by `SupabaseRepository.record_price_if_changed` (T4): source_key, source_listing_id, fingerprint, price_zar (+ server-default id/observed_at).

**Regression check:** Existing Plan 1 pipeline tests pass unchanged — the new pipeline logic adds fields and price recording without altering `fetched`/`upserted`/`invalid` semantics; the bad (price 0) listing is invalid so it skips price recording (the `elif`).
