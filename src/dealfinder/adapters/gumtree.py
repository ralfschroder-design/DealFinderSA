"""Gumtree South Africa adapter — cars, bikes, boats, jetskis."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from bs4 import BeautifulSoup

from dealfinder.adapters.base import Adapter
from dealfinder.config import Settings
from dealfinder.fetch import Fetcher
from dealfinder.models import Category, Listing, SellerType
from dealfinder.vehicles import canonical_make, split_make_model

BASE = "https://www.gumtree.co.za"

# --- Detail-page date patterns ---
# Primary: structured ISO date in JSON-LD / inline script
_AVAIL_STARTS_RE = re.compile(r'"availabilityStarts"\s*:\s*"(\d{4}-\d{2}-\d{2})"')
# Fallback: relative text  "N day(s)|week(s)|month(s)|year(s) ago"
_RELATIVE_AGE_RE = re.compile(r"(\d+)\s+(day|week|month|year)s?\s+ago", re.IGNORECASE)

_RELATIVE_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}

# The 9 South African provinces (normalised lower-case) — used to validate the
# province pulled from the detail-page breadcrumb so a city name is never
# mistaken for a province.
_SA_PROVINCES = {
    "gauteng", "western cape", "eastern cape", "kwazulu-natal", "kwazulu natal",
    "free state", "limpopo", "mpumalanga", "north west", "northern cape",
}
# Gumtree's `model` field is sometimes a placeholder rather than a real model.
_MODEL_PLACEHOLDERS = {"", "other", "n/a", "na", "unknown", "none"}

CATEGORY_PATHS: dict[Category, str] = {
    Category.CAR:    "/s-cars-bakkies/v1c9077",
    Category.BIKE:   "/s-motorcycles-scooters/v1c9027",
    Category.BOAT:   "/s-boats-watercraft/v1c9101",
    Category.JETSKI: "/s-boats-jet-skis/v1c9102",
}

# Matches hrefs like /a-cars-bakkies/durbanville/2011-toyota-rav4-2-0/100135...
_AD_HREF_RE = re.compile(r"^/a-[^/]+/[^/]+/[^/]+/(\d+)$")
# Price extraction: R followed by digits, spaces and commas
_PRICE_RE = re.compile(r"R\s?[\d\s,]+")


def _parse_price(text: str) -> int | None:
    """Extract an integer ZAR price from a text string like 'R 149 900' or 'R149,900'."""
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if not m:
        return None
    digits = re.sub(r"[^\d]", "", m.group())
    if not digits:
        return None
    value = int(digits)
    return value if value > 0 else None


def _from_href(href: str) -> dict[str, Any]:
    """Decompose a Gumtree ad href into structured fields.

    href format: /a-<cat-slug>/<town>/<title-slug>/<numeric-id>
    """
    parts = href.strip("/").split("/")
    # parts[0] = "a-cars-bakkies", parts[1] = town, parts[2] = title-slug, parts[3] = id
    listing_id = parts[3] if len(parts) >= 4 else parts[-1]
    town_slug = parts[1] if len(parts) >= 4 else ""
    title_slug = parts[2] if len(parts) >= 4 else ""

    town = title_slug_to_readable(town_slug) if town_slug and town_slug != "other" else None

    # Extract year from the title slug (first 4-digit year token)
    year: int | None = None
    for token in re.split(r"[-+]", title_slug):
        if re.match(r"^(19|20)\d{2}$", token):
            year = int(token)
            break

    # Use known-makes dictionary for clean make/model/variant parsing
    make, model, _variant = split_make_model(title_slug)

    # Build human-readable title from slug
    title = re.sub(r"[-+]", " ", title_slug).strip()

    return {
        "source_listing_id": listing_id,
        "url": BASE + href,
        "town": town,
        "year": year,
        "make": make,
        "model": model,
        "title": title if title else None,
    }


def title_slug_to_readable(slug: str) -> str | None:
    """Convert a town slug like 'durbanville' to a readable string 'Durbanville'."""
    if not slug:
        return None
    return slug.replace("-", " ").title()


def parse_posted_at(detail_html: str, now: datetime | None = None) -> datetime | None:
    """Extract the listing's posted date from a Gumtree detail-page HTML string.

    Primary path: ``"availabilityStarts":"YYYY-MM-DD"`` in the page source.
    Returns a UTC-midnight :class:`datetime` when found.

    Fallback: relative text such as ``N days/weeks/months/years ago`` found in
    a ``creation-date`` span or a ``creationDate`` JSON field.  Resolved
    against ``now`` (UTC) so callers can inject a fixed reference for tests.

    Returns ``None`` when neither signal is present.
    """
    # --- Primary: structured ISO date ---
    m = _AVAIL_STARTS_RE.search(detail_html)
    if m:
        try:
            y, mo, d = map(int, m.group(1).split("-"))
            return datetime(y, mo, d, tzinfo=timezone.utc)
        except ValueError:
            pass  # fall through to relative

    # --- Fallback: relative age text ---
    m2 = _RELATIVE_AGE_RE.search(detail_html)
    if m2:
        n = int(m2.group(1))
        unit = m2.group(2).lower()
        days = n * _RELATIVE_DAYS.get(unit, 1)
        base = now if now is not None else datetime.now(timezone.utc)
        return base - timedelta(days=days)

    return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_text(text: str | None, *, limit: int = 2000) -> str | None:
    """Strip HTML tags/entities from a description string and bound its length."""
    if not text:
        return None
    stripped = BeautifulSoup(text, "html.parser").get_text(" ")
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return stripped[:limit] or None


def _seller_type_from_text(text: str | None) -> SellerType | None:
    if not text:
        return None
    t = text.strip().lower()
    if "dealer" in t:
        return SellerType.DEALER
    if "private" in t or "owner" in t:
        return SellerType.PRIVATE
    return None


def _parse_attributes_table(soup: BeautifulSoup) -> dict[str, str]:
    """Read Gumtree's ``div.attribute`` rows into a {label: value} dict (labels
    lower-cased, trailing colon stripped)."""
    attrs: dict[str, str] = {}
    for block in soup.find_all("div", class_="attribute"):
        name_el = block.find("span", class_="name")
        val_el = block.find("span", class_="value")
        if not name_el or not val_el:
            continue
        name = name_el.get_text(" ", strip=True).rstrip(":").strip().lower()
        value = val_el.get_text(" ", strip=True)
        if name and value:
            attrs[name] = value
    return attrs


def parse_detail(html: str, now: datetime | None = None) -> dict[str, Any]:
    """Parse a Gumtree detail page into a dict of enrichment fields.

    Primary source is the JSON-LD (``Vehicle`` / ``Place`` / ``BreadcrumbList``);
    the HTML attributes table supplements it — notably ``For Sale By`` → seller
    type, and a fallback for any field the JSON-LD omits.  Every key is optional:
    only the fields actually found are returned.  Never raises — returns ``{}``
    on empty or unparseable input.

    Possible keys: ``make``, ``model``, ``year``, ``price_zar``, ``mileage_km``,
    ``province``, ``town``, ``lat``, ``lng``, ``seller_type`` (:class:`SellerType`),
    ``description``, ``posted_at``, and ``extras`` =
    ``{transmission, fuel_type, body_type, colour, drive_type}``.
    """
    out: dict[str, Any] = {}
    if not html:
        return out
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:  # noqa: BLE001 — parsing must never abort enrichment
        return out

    # --- JSON-LD objects, indexed by @type (first of each type wins) ---
    by_type: dict[str, dict] = {}
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        for obj in (data if isinstance(data, list) else [data]):
            if isinstance(obj, dict):
                t = obj.get("@type")
                if isinstance(t, str) and t not in by_type:
                    by_type[t] = obj

    veh = by_type.get("Vehicle", {})
    place = by_type.get("Place", {})
    crumbs = by_type.get("BreadcrumbList", {})

    # make (brand/manufacturer) → canonical
    brand = veh.get("brand") or veh.get("manufacturer")
    if isinstance(brand, dict):
        brand = brand.get("name")
    if brand:
        out["make"] = canonical_make(str(brand).strip())

    # model (skip placeholders such as "Other")
    model = veh.get("model")
    if isinstance(model, dict):
        model = model.get("name")
    if model and str(model).strip().lower() not in _MODEL_PLACEHOLDERS:
        out["model"] = str(model).strip()

    year = _coerce_int(veh.get("vehicleModelDate"))
    if year:
        out["year"] = year

    offers = veh.get("offers")
    if isinstance(offers, dict):
        price = _coerce_int(offers.get("price"))
        if price:
            out["price_zar"] = price

    mfo = veh.get("mileageFromOdometer")
    mileage = _coerce_int(mfo.get("value") if isinstance(mfo, dict) else mfo)
    if mileage is not None:
        out["mileage_km"] = mileage

    # town + real geo from Place
    address = place.get("address") if isinstance(place, dict) else None
    if isinstance(address, dict) and address.get("addressLocality"):
        out["town"] = str(address["addressLocality"]).strip()
    geo = place.get("geo") if isinstance(place, dict) else None
    if isinstance(geo, dict):
        lat = _coerce_float(geo.get("latitude"))
        lng = _coerce_float(geo.get("longitude"))
        if lat is not None and lng is not None:
            out["lat"] = lat
            out["lng"] = lng

    # province = first breadcrumb whose name is a real SA province
    items = crumbs.get("itemListElement") if isinstance(crumbs, dict) else None
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            if name.lower() in _SA_PROVINCES:
                out["province"] = name
                break

    desc = _clean_text(veh.get("description"))
    if desc:
        out["description"] = desc

    extras: dict[str, str] = {}
    for src_key, dst_key in (
        ("vehicleTransmission", "transmission"),
        ("fuelType", "fuel_type"),
        ("bodyType", "body_type"),
        ("color", "colour"),
        ("driveType", "drive_type"),
    ):
        v = veh.get(src_key)
        if v:
            extras[dst_key] = str(v).strip()

    # --- attributes table: seller type + fallback for missing fields ---
    attrs = _parse_attributes_table(soup)
    seller_type = _seller_type_from_text(attrs.get("for sale by"))
    if seller_type is not None:
        out["seller_type"] = seller_type

    if "make" not in out and attrs.get("make"):
        out["make"] = canonical_make(attrs["make"])
    if "model" not in out and attrs.get("model") and attrs["model"].strip().lower() not in _MODEL_PLACEHOLDERS:
        out["model"] = attrs["model"].strip()
    if "year" not in out:
        yr = _coerce_int(attrs.get("year"))
        if yr:
            out["year"] = yr
    if "mileage_km" not in out and attrs.get("kilometers"):
        km = _coerce_int(re.sub(r"[^\d]", "", attrs["kilometers"]))
        if km is not None:
            out["mileage_km"] = km
    if "town" not in out and attrs.get("location"):
        town = attrs["location"].split(",")[0].strip()
        if town:
            out["town"] = town
    for label, dst_key in (
        ("transmission", "transmission"), ("fuel type", "fuel_type"),
        ("body type", "body_type"), ("colour", "colour"), ("drive type", "drive_type"),
    ):
        if dst_key not in extras and attrs.get(label):
            extras[dst_key] = attrs[label].strip()

    if extras:
        out["extras"] = extras

    posted = parse_posted_at(html, now)
    if posted is not None:
        out["posted_at"] = posted

    return out


def _apply_detail_fields(listing: Listing, fields: dict[str, Any]) -> None:
    """Apply a :func:`parse_detail` result onto a listing in place.

    Identity (make/model/year) is *upgraded* from the structured data (more
    reliable than the slug); mileage/province/town/geo/seller/description are
    *filled*; price is filled only when missing (so the search-card price — and
    thus price-history — is never churned). Transmission/fuel/etc. go into ``raw``.
    """
    if fields.get("posted_at") is not None and listing.posted_at is None:
        listing.posted_at = fields["posted_at"]
    if fields.get("make"):
        listing.make = fields["make"]
    if fields.get("model"):
        listing.model = fields["model"]
    if fields.get("year"):
        listing.year = fields["year"]
    if listing.mileage_km is None and fields.get("mileage_km") is not None:
        listing.mileage_km = fields["mileage_km"]
    if listing.price_zar is None and fields.get("price_zar") is not None:
        listing.price_zar = fields["price_zar"]
    if fields.get("province"):
        listing.province = fields["province"]
    if fields.get("town"):
        listing.town = fields["town"]
    if fields.get("lat") is not None and fields.get("lng") is not None:
        listing.lat = fields["lat"]
        listing.lng = fields["lng"]
    seller_type = fields.get("seller_type")
    if seller_type is not None and seller_type != SellerType.UNKNOWN:
        listing.seller_type = seller_type
    if fields.get("description") and not listing.description:
        listing.description = fields["description"]
    extras = fields.get("extras")
    if extras:
        listing.raw = {**(listing.raw or {}), **extras}


class GumtreeAdapter(Adapter):
    """Gumtree South Africa listing adapter."""

    key = "gumtree"
    name = "Gumtree SA"
    tier = 1

    def parse_page(self, html: str, category: Category) -> list[Listing]:
        """Parse a Gumtree search results HTML page and return Listing objects."""
        soup = BeautifulSoup(html, "html.parser")
        anchors = soup.find_all("a", href=_AD_HREF_RE)

        # Build creationDate lookup once per page from the embedded gallery JSON.
        creation_date_map = _build_creation_date_map(html)

        seen_ids: set[str] = set()
        listings: list[Listing] = []

        for a in anchors:
            href = a.get("href", "")
            m = _AD_HREF_RE.match(href)
            if not m:
                continue
            listing_id = m.group(1)
            if listing_id in seen_ids:
                continue
            seen_ids.add(listing_id)

            fields = _from_href(href)

            # Walk up to find the card container (tile-item or related-item)
            card = _find_card(a)

            price_zar: int | None = None
            image_urls: list[str] = []

            if card:
                price_el = card.find("span", class_="ad-price")
                if price_el:
                    price_zar = _parse_price(price_el.get_text(strip=True))

                img = card.find("img")
                if img:
                    img_url = img.get("data-src") or img.get("src") or ""
                    # Skip base64 placeholder images
                    if img_url and "base64" not in img_url:
                        image_urls.append(img_url)

            # Set posted_at from creationDate map; leave None when absent (graceful).
            posted_at: datetime | None = None
            creation_ms = creation_date_map.get(listing_id)
            if creation_ms is not None:
                posted_at = datetime.fromtimestamp(creation_ms / 1000, tz=timezone.utc)

            listings.append(
                Listing(
                    source_key="gumtree",
                    source_listing_id=fields["source_listing_id"],
                    url=fields["url"],
                    category=category,
                    title=fields.get("title"),
                    make=fields.get("make"),
                    model=fields.get("model"),
                    year=fields.get("year"),
                    town=fields.get("town"),
                    price_zar=price_zar,
                    image_urls=image_urls,
                    posted_at=posted_at,
                    raw={"href": href},
                )
            )

        return listings

    def fetch_listings(self, fetcher: Fetcher, settings: Settings) -> list[Listing]:
        """Fetch listings from Gumtree across all categories and configured pages."""
        src_cfg = settings.sources.get(self.key)
        max_pages = src_cfg.max_pages if src_cfg else 1

        all_listings: list[Listing] = []
        seen_ids: set[str] = set()

        for category, path in CATEGORY_PATHS.items():
            for page in range(1, max_pages + 1):
                url = BASE + path + f"p{page}"
                try:
                    html = fetcher.get_text(url)
                    page_listings = self.parse_page(html, category)
                except Exception:
                    continue  # skip this page; keep going with other pages/categories
                if not page_listings:
                    break  # stop early if empty page (genuine end of results)
                for listing in page_listings:
                    if listing.source_listing_id not in seen_ids:
                        seen_ids.add(listing.source_listing_id)
                        all_listings.append(listing)

        return all_listings

    def enrich_posted_at(
        self,
        fetcher,
        listings: list,
        *,
        cap: int | None = None,
        now: datetime | None = None,
    ) -> int:
        """Fetch each undated listing's detail page and enrich it.

        Despite the name (kept as the pipeline's detail-fetch hook), this now
        applies **all** available structured fields via :func:`parse_detail` —
        make, model, year, mileage, province, geo, seller type, description, and
        transmission/fuel/etc. into ``raw`` — not just ``posted_at``.

        Args:
            fetcher: Object with a ``get_text(url)`` method.
            listings: Listings to enrich (only those with ``posted_at is None``
                      are processed).
            cap: Maximum number of detail **fetches** to perform (politeness).
                 ``None`` means no limit.
            now: Reference time for relative-date parsing (injected for tests).

        Returns:
            The number of listings that were successfully dated.
        """
        fetches = 0
        dated = 0
        for listing in listings:
            if listing.posted_at is not None:
                continue
            if cap is not None and fetches >= cap:
                break
            fetches += 1
            try:
                html = fetcher.get_text(listing.url)
            except Exception:
                continue  # one bad page must not abort the loop
            fields = parse_detail(html, now)
            if not fields:
                continue
            _apply_detail_fields(listing, fields)
            if fields.get("posted_at") is not None:
                dated += 1
        return dated


def _build_creation_date_map(html: str) -> dict[str, int]:
    """Extract a {source_listing_id: creationDate_ms} map from the inline gallery JSON.

    Gumtree embeds listing metadata in a JS assignment::

        var galleryAdList_searchGallery = [{...}, ...];

    Each entry has a ``viewSeoUrl`` whose last path segment matches the
    ``source_listing_id`` used by the adapter (the last segment of the anchor
    href), and a ``creationDate`` field (Unix timestamp in milliseconds).

    Returns an empty dict if the block is absent or cannot be parsed.
    """
    m = re.search(r"var galleryAdList_searchGallery\s*=\s*(\[.*?\]);", html, re.DOTALL)
    if not m:
        return {}
    try:
        entries = json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        return {}

    result: dict[str, int] = {}
    for entry in entries:
        creation_ms = entry.get("creationDate")
        if creation_ms is None:
            continue
        seo_url = entry.get("viewSeoUrl", "")
        parts = seo_url.strip("/").split("/")
        if parts:
            listing_id = parts[-1]
            result[listing_id] = int(creation_ms)
    return result


def _find_card(anchor) -> object | None:
    """Walk up the DOM from an anchor to find its card container element."""
    el = anchor
    for _ in range(12):
        if not el.parent:
            return None
        el = el.parent
        classes = el.get("class", []) if hasattr(el, "get") else []
        if "tile-item" in classes or "related-item" in classes:
            return el
    return None
