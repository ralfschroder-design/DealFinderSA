"""Gumtree South Africa adapter — cars, bikes, boats, jetskis."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup

from dealfinder.adapters.base import Adapter
from dealfinder.config import Settings
from dealfinder.fetch import Fetcher
from dealfinder.models import Category, Listing
from dealfinder.vehicles import split_make_model

BASE = "https://www.gumtree.co.za"

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
