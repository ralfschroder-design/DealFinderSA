from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

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

    def enrich_posted_at(
        self,
        fetcher,
        listings: list[Listing],
        *,
        cap: int | None = None,
        now: datetime | None = None,
    ) -> int:
        """Populate ``posted_at`` from detail pages.  No-op by default; adapters
        that support detail-page dating should override this method.

        Returns the number of listings that were dated.
        """
        return 0
