from __future__ import annotations

from typing import Any

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


# ── Academic analysis helpers (monthly series) ──────────────────────────────

def build_monthly_series(frame: pd.DataFrame, price_col: str = "price_usd") -> pd.DataFrame:
    """Resample daily → monthly (period-end) and interpolate missing values."""
    series = frame[[price_col]].copy()
    series[price_col] = pd.to_numeric(series[price_col], errors="coerce")
    monthly = series.resample("ME").mean()
    monthly[price_col] = monthly[price_col].interpolate(method="linear")
    monthly = monthly.dropna(subset=[price_col])
    return monthly


def build_decomposition_report(
    monthly: pd.DataFrame,
    price_col: str = "price_usd",
    period: int = 12,
) -> dict[str, Any]:
    """Run additive and multiplicative seasonal decompose; recommend the one with
    more stable (lower std) seasonal component."""
    from statsmodels.tsa.seasonal import seasonal_decompose

    series = monthly[price_col].dropna()
    if len(series) < 2 * period:
        return {"error": f"Cần ít nhất {2 * period} quan sát để phân rã (hiện có {len(series)})."}

    add_res = seasonal_decompose(series, model="additive", period=period)
    mul_res = seasonal_decompose(series, model="multiplicative", period=period)

    add_seasonal_std = float(add_res.seasonal.std())
    mul_seasonal_std = float(mul_res.seasonal.std())
    add_resid_std = float(add_res.resid.dropna().std())
    mul_resid_std = float(mul_res.resid.dropna().std())

    recommended = "additive" if add_seasonal_std <= mul_seasonal_std else "multiplicative"

    return {
        "n_obs": int(len(series)),
        "period": period,
        "additive": {
            "seasonal_std": round(add_seasonal_std, 6),
            "residual_std": round(add_resid_std, 6),
        },
        "multiplicative": {
            "seasonal_std": round(mul_seasonal_std, 6),
            "residual_std": round(mul_resid_std, 6),
        },
        "recommended_model": recommended,
        "conclusion": (
            f"Mô hình {recommended} phù hợp hơn — "
            f"seasonal.std(): additive={add_seasonal_std:.4f}, multiplicative={mul_seasonal_std:.4f}. "
            f"Mô hình có seasonal.std() nhỏ hơn thì biên độ thời vụ ổn định hơn."
        ),
    }
