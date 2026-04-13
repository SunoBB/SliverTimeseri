from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MarketDataProvider(ABC):
    @abstractmethod
    def fetch_silver_history(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        timeframe: str = "1d",
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Return raw market price records for the primary metal series."""
