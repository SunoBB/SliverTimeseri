from __future__ import annotations

import numpy as np
import pandas as pd


DEFAULT_INDICATORS = [
    "return_1d",
    "ma_5",
    "ma_10",
    "ma_20",
    "volatility_5",
    "volatility_10",
    "momentum_5",
]


def add_technical_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    dataset = frame.copy()
    dataset["return_1d"] = dataset["price_usd"].pct_change().shift(1)
    dataset["ma_5"] = dataset["price_usd"].rolling(window=5).mean().shift(1)
    dataset["ma_10"] = dataset["price_usd"].rolling(window=10).mean().shift(1)
    dataset["ma_20"] = dataset["price_usd"].rolling(window=20).mean().shift(1)
    dataset["volatility_5"] = dataset["price_usd"].pct_change().rolling(window=5).std().shift(1)
    dataset["volatility_10"] = dataset["price_usd"].pct_change().rolling(window=10).std().shift(1)
    dataset["momentum_5"] = dataset["price_usd"].diff(periods=5).shift(1)
    dataset = dataset.replace([np.inf, -np.inf], np.nan)
    return dataset


def add_lag_features(frame: pd.DataFrame, order: int, column: str = "price_usd") -> pd.DataFrame:
    dataset = frame.copy()
    for lag in range(1, order + 1):
        dataset[f"{column}_lag_{lag}"] = dataset[column].shift(lag)
    return dataset
