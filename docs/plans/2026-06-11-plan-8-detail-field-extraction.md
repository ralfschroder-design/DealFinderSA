# DealFinderSA — Plan 8: Detail-page field extraction

**Date:** 2026-06-11 · Builds on freshness v2 (we already fetch detail pages for dating). Status: in build.

## Goal
Extract the **rich structured fields** Gumtree publishes on each listing's detail page — which we already fetch (capped) for dating — so we get: real make/model/year, **mileage**, **province + geo coordinates**, and **seller type**. This (a) tightens scoring cohorts, (b) finally enables the **100 km-from-Hartbeespoort radius** (a core original requirement), and (c) lays groundwork for condition-signal scoring and area/demand mapping (North Star).

## What's actually on the page (verified on a live page, 2026-06-11)
A single `<script type="application/ld+json">` array with three objects, **plus** an HTML attributes table:
- **`Vehicle`** → `brand`, `model` (sometimes `"Other"`), `vehicleModelDate` (year), `offers.price`, `mileageFromOdometer.value` (km), `vehicleTransmission`, `fuelType`, `bodyType`, `color`, `driveType`, `description`, `offers.availabilityStarts` (date).
- **`Place`** → `address.addressLocality` (town), `geo.latitude/longitude` (**real coordinates**).
- **`BreadcrumbList`** → first item name = **province** (e.g. "Gauteng").
- **`div.vip-general-details div.attributes`** → label/value rows, uniquely incl. **"For Sale By: Dealer"** (seller type), and a clean fallback for make/model/year/kilometres/transmission/fuel/colour.

No `__NEXT_DATA__`, no JS wall — openly served. (WeBuyCars-style anti-bot is **not** present here.)

## Method
**New pure fn** `parse_detail(html, now=None) -> dict` in `gumtree.py`:
- Primary source = JSON-LD; **fallback/supplement** = the attributes table (seller type, and any field JSON-LD omits).
- Returns only the keys it finds (all optional): `make` (via `canonical_make`), `model` (skip `"Other"/"N/A"`), `year`, `price_zar`, `mileage_km`, `province` (validated against the 9 SA provinces), `town`, `lat`, `lng`, `seller_type` (`SellerType`), `description` (HTML stripped, truncated), `posted_at` (reuses `parse_posted_at`), and `extras` = `{transmission, fuel_type, body_type, colour, drive_type}`.
- **Never raises** — returns `{}` on unparseable input (enrichment stays resilient).

**Broaden** `GumtreeAdapter.enrich_posted_at` (name kept to avoid base/pipeline/test churn — it is the "fetch detail page for undated listings" hook): for each undated listing it now applies *all* parsed fields, not just the date. Field policy:
- **Upgrade** make/model/year from the structured data (more reliable than the slug) when present.
- **Fill** mileage_km, province, town, lat, lng, seller_type, description; **fill price only when missing** (don't override the search-card price → no `price_history` churn).
- Stash `extras` into `listing.raw`.
- `posted_at` set as before. Setting `description` also gives `seller_phone` for free (the pipeline already runs `extract_phone(description)`).
- `cap` now limits **fetches** (politeness); return value stays "number dated". All four existing `enrich_posted_at` tests remain green.

Pipeline order is unchanged (scrape → **enrich** → validate → fingerprint → phone → price → upsert), so enriched make/mileage/province flow into the fingerprint and validity automatically.

## Data model
**No migration.** Every target field already exists on `Listing` and the `listings` table (`mileage_km, province, town, lat, lng, seller_type, description`). Transmission/fuel/body/colour/drive live in the existing `raw` jsonb. Promoting those to first-class columns + using them in cohorts is **deferred** (needs a migration → user-gated).

## Tasks
- **A:** `gumtree_detail.html` fixture upgraded to a realistic full page (keeps `availabilityStarts: 2026-04-24`); `parse_detail` + tests (JSON-LD path, attributes-table seller type, province validation, graceful empty). TDD.
- **B:** broaden `enrich_posted_at` to apply all fields + tests (fields land on listings; existing date/cap/skip/failure tests still pass). TDD.
- **Verify:** run `parse_detail` against a real saved page to confirm live extraction (make/mileage/geo/seller).

## Deferred (future)
Transmission/fuel as first-class cohort dimensions (+migration); distance-from-Hartbeespoort filter in validity/UI/search (geo now captured); mileage-aware condition scoring; back-fill of legacy listings (only newly-fetched details are enriched — coverage grows ~`max_detail_fetches`/run, same as dating).
