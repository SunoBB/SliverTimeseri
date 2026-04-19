from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from silver_timeseri.analysis.models import run_model_suite


class ModelForecastBandTests(unittest.TestCase):
    def test_run_model_suite_returns_forecast_bands_for_all_daily_models(self) -> None:
        index = pd.date_range("2024-01-01", periods=90, freq="D")
        base = np.linspace(22.0, 30.0, len(index))
        seasonal = np.sin(np.arange(len(index)) / 5.0) * 0.8
        frame = pd.DataFrame(
            {
                "price_usd": base + seasonal,
                "price_vnd": (base + seasonal) * 25000.0,
            },
            index=index,
        )

        results = run_model_suite(frame=frame, ar_order=5, ma_order=3, test_ratio=0.2)

        self.assertEqual(len(results), 3)
        for result in results:
            self.assertTrue(result.predictions)
            effective_rows = result.train_size + result.test_size
            self.assertEqual(result.test_size, int(effective_rows * 0.2))
            first_prediction = result.predictions[0]
            self.assertIn("lower_bound", first_prediction)
            self.assertIn("upper_bound", first_prediction)
            self.assertIn("band_width", first_prediction)
            self.assertIn("interval_level", first_prediction)
            self.assertLessEqual(first_prediction["lower_bound"], first_prediction["upper_bound"])

            self.assertIsNotNone(result.next_forecast)
            assert result.next_forecast is not None
            self.assertIn("lower_bound", result.next_forecast)
            self.assertIn("upper_bound", result.next_forecast)
            self.assertIn("band_width", result.next_forecast)
            self.assertEqual(result.next_forecast["interval_level"], 0.95)
            self.assertLessEqual(
                result.next_forecast["lower_bound"],
                result.next_forecast["upper_bound"],
            )


if __name__ == "__main__":
    unittest.main()
