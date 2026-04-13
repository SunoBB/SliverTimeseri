from __future__ import annotations

import unittest

import pandas as pd

from silver_timeseri.analysis.features import add_technical_indicators
from silver_timeseri.providers.base import MarketDataProvider
from silver_timeseri.services.pipeline import CURATED_LAYER, RAW_LAYER, SilverTimeSeriesPipeline


class StubMarketDataProvider(MarketDataProvider):
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def fetch_silver_history(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        timeframe: str = "1d",
        force_refresh: bool = False,
    ) -> list[dict[str, object]]:
        filtered: list[dict[str, object]] = []
        for row in self.rows:
            item_date = str(row["date"])
            if start_date and item_date < start_date:
                continue
            if end_date and item_date > end_date:
                continue
            filtered.append(dict(row))
        return filtered


class CuratedPipelineTests(unittest.TestCase):
    def test_raw_and_curated_layers_are_separated(self) -> None:
        pipeline = SilverTimeSeriesPipeline(
            StubMarketDataProvider(
                [
                    {"date": "2024-01-01", "price_usd": 100.0, "price_silver_usd": 100.0},
                    {"date": "2024-01-03", "price_usd": 105.0, "price_silver_usd": 105.0},
                ]
            )
        )

        raw = pipeline.load(series_layer=RAW_LAYER)
        curated = pipeline.load(series_layer=CURATED_LAYER)

        self.assertEqual(list(raw.index.strftime("%Y-%m-%d")), ["2024-01-01", "2024-01-03"])
        self.assertEqual(
            list(curated.index.strftime("%Y-%m-%d")),
            ["2024-01-01", "2024-01-02", "2024-01-03"],
        )
        self.assertFalse(raw["is_imputed"].any())
        self.assertTrue(bool(curated.loc["2024-01-02", "is_imputed"]))

    def test_missing_holiday_is_forward_filled_with_audit_flags(self) -> None:
        pipeline = SilverTimeSeriesPipeline(
            StubMarketDataProvider(
                [
                    {"date": "2024-01-01", "price_usd": 100.0, "price_silver_usd": 100.0},
                    {"date": "2024-01-03", "price_usd": 105.0, "price_silver_usd": 105.0},
                ]
            )
        )

        curated = pipeline.load_curated()
        holiday_row = curated.loc["2024-01-02"]

        self.assertEqual(float(holiday_row["price_usd"]), 100.0)
        self.assertTrue(bool(holiday_row["is_missing_from_source"]))
        self.assertTrue(bool(holiday_row["is_imputed"]))
        self.assertFalse(bool(holiday_row["is_weekend"]))
        self.assertEqual(holiday_row["source_date"].date().isoformat(), "2024-01-01")

    def test_missing_weekend_days_are_flagged_as_weekend(self) -> None:
        pipeline = SilverTimeSeriesPipeline(
            StubMarketDataProvider(
                [
                    {"date": "2024-01-05", "price_usd": 100.0, "price_silver_usd": 100.0},
                    {"date": "2024-01-08", "price_usd": 110.0, "price_silver_usd": 110.0},
                ]
            )
        )

        curated = pipeline.load_curated()

        for missing_day in ["2024-01-06", "2024-01-07"]:
            row = curated.loc[missing_day]
            self.assertTrue(bool(row["is_weekend"]))
            self.assertTrue(bool(row["is_missing_from_source"]))
            self.assertTrue(bool(row["is_imputed"]))
            self.assertEqual(float(row["price_usd"]), 100.0)

    def test_curated_skips_days_before_first_observation(self) -> None:
        pipeline = SilverTimeSeriesPipeline(
            StubMarketDataProvider(
                [
                    {"date": "2024-01-03", "price_usd": 100.0, "price_silver_usd": 100.0},
                ]
            )
        )

        curated = pipeline.load_curated(start_date="2024-01-01", end_date="2024-01-04")

        self.assertEqual(list(curated.index.strftime("%Y-%m-%d")), ["2024-01-03", "2024-01-04"])
        self.assertEqual(float(curated.loc["2024-01-04", "price_usd"]), 100.0)
        self.assertTrue(bool(curated.loc["2024-01-04", "is_imputed"]))
        self.assertEqual(curated.index.min().date().isoformat(), "2024-01-03")

    def test_return_1d_uses_calendar_day_after_clean(self) -> None:
        pipeline = SilverTimeSeriesPipeline(
            StubMarketDataProvider(
                [
                    {"date": "2024-01-05", "price_usd": 100.0, "price_silver_usd": 100.0},
                    {"date": "2024-01-08", "price_usd": 110.0, "price_silver_usd": 110.0},
                    {"date": "2024-01-09", "price_usd": 121.0, "price_silver_usd": 121.0},
                ]
            )
        )

        curated = pipeline.load_curated()
        with_features = add_technical_indicators(curated)

        self.assertAlmostEqual(float(with_features.loc["2024-01-08", "return_1d"]), 0.0, places=8)
        self.assertAlmostEqual(float(with_features.loc["2024-01-09", "return_1d"]), 0.1, places=8)


if __name__ == "__main__":
    unittest.main()
