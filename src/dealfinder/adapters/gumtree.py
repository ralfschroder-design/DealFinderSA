"""Gumtree South Africa adapter — cars, bikes, boats, jetskis."""
from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from dealfinder.adapters.base import Adapter
from dealfinder.config import Settings
from dealfinder.fetch import Fetcher
from dealfinder.models import Category, Listing

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

    # Parse title-slug tokens (replace - and + with spaces)
    tokens = re.split(r"[-+]", title_slug)

    year: int | None = None
    make: str | None = None
    model: str | None = None
    year_idx = -1

    for i, token in enumerate(tokens):
        if re.match(r"^(19|20)\d{2}$", token):
            year = int(token)
            year_idx = i
            break

    if year_idx >= 0:
        remaining = tokens[year_idx + 1:]
    else:
        remaining = tokens

    if remaining:
        make = remaining[0].title() if remaining[0] else None
    if len(remaining) >= 2:
        model = remaining[1].title() if remaining[1] else None

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
                html = fetcher.get_text(url)
                page_listings = self.parse_page(html, category)
                if not page_listings:
                    break  # stop early if empty page
                for listing in page_listings:
                    if listing.source_listing_id not in seen_ids:
                        seen_ids.add(listing.source_listing_id)
                        all_listings.append(listing)

        return all_listings


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
