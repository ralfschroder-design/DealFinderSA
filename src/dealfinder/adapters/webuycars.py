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
