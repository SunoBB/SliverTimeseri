from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from silver_timeseri.analysis.visualization import save_time_series_charts


class VisualizationTests(unittest.TestCase):
    def test_save_time_series_charts_includes_return_and_volatility_outputs(self) -> None:
        frame = pd.DataFrame(
            {
                "price_usd": [100.0, 101.0, 103.0, 102.0, 104.0, 107.0, 109.0, 108.0, 110.0, 112.0],
            },
            index=pd.date_range("2024-01-01", periods=10, freq="D"),
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            saved_paths = save_time_series_charts(
                frame,
                value_column="price_usd",
                output_dir=Path(tmp_dir),
                moving_average_window=3,
                volatility_window=3,
                histogram_bins=5,
                lag=1,
            )

            saved_names = {path.name for path in saved_paths}

            self.assertIn("10_return_log_return_chart.png", saved_names)
            self.assertIn("11_return_rolling_volatility_chart.png", saved_names)
            self.assertIn("12_return_volatility_combined_chart.png", saved_names)
            self.assertEqual(len(saved_paths), 12)


if __name__ == "__main__":
    unittest.main()
