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
