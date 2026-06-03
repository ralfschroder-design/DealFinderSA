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
