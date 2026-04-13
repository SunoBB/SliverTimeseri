from __future__ import annotations

from typing import Any

import pandas as pd
from statsmodels.tsa.stattools import adfuller


def build_summary_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"rows": 0}

    numeric_columns = [
        "price_usd",
        "price_vnd",
        "price_silver_usd",
        "price_silver_vnd",
        "usd_vnd_rate",
    ]
    dataset = frame.copy()
    for column in numeric_columns:
        if column in dataset.columns:
            dataset[column] = pd.to_numeric(dataset[column], errors="coerce")
    valid_prices = dataset.dropna(subset=["price_usd"]).copy()
    if valid_prices.empty:
        return {"rows": int(len(dataset)), "valid_rows": 0}

    returns = valid_prices["price_usd"].pct_change().dropna()
    running_peak = valid_prices["price_usd"].cummax()
    drawdown = (valid_prices["price_usd"] / running_peak) - 1

    summary = {
        "rows": int(len(dataset)),
        "valid_rows": int(len(valid_prices)),
        "symbol": str(valid_prices["symbol"].iloc[0]) if "symbol" in valid_prices else None,
        "timeframe": str(valid_prices["timeframe"].iloc[0]) if "timeframe" in valid_prices else None,
        "series_layer": str(valid_prices["series_layer"].iloc[0]) if "series_layer" in valid_prices else None,
        "start_date": valid_prices.index.min().date().isoformat(),
        "end_date": valid_prices.index.max().date().isoformat(),
        "start_price_usd": round(float(valid_prices["price_usd"].iloc[0]), 4),
        "end_price_usd": round(float(valid_prices["price_usd"].iloc[-1]), 4),
        "mean_price_usd": round(float(valid_prices["price_usd"].mean()), 4),
        "median_price_usd": round(float(valid_prices["price_usd"].median()), 4),
        "min_price_usd": round(float(valid_prices["price_usd"].min()), 4),
        "max_price_usd": round(float(valid_prices["price_usd"].max()), 4),
        "start_price_vnd": round(float(valid_prices["price_vnd"].iloc[0]), 4) if "price_vnd" in valid_prices else None,
        "end_price_vnd": round(float(valid_prices["price_vnd"].iloc[-1]), 4) if "price_vnd" in valid_prices else None,
        "mean_price_vnd": round(float(valid_prices["price_vnd"].mean()), 4) if "price_vnd" in valid_prices else None,
        "daily_return_mean": round(float(returns.mean()), 6) if not returns.empty else None,
        "daily_return_std": round(float(returns.std()), 6) if not returns.empty else None,
        "max_drawdown": round(float(drawdown.min()), 6),
        "imputed_rows": int(valid_prices["is_imputed"].sum()) if "is_imputed" in valid_prices else 0,
    }
    return summary


def _run_adf(series: pd.Series, label: str) -> dict[str, Any]:
    """Run ADF test on a single series and return a structured result dict."""
    clean = series.dropna()
    if len(clean) < 20:
        return {"label": label, "error": "Không đủ dữ liệu (cần ≥ 20 quan sát)."}

    stat, p_value, lags, n_obs, crit, _ = adfuller(clean, autolag="AIC")
    is_stationary = bool(p_value < 0.05)
    significance = (
        "***" if p_value < 0.01
        else "**" if p_value < 0.05
        else "*" if p_value < 0.10
        else ""
    )
    return {
        "label": label,
        "test_statistic": round(float(stat), 6),
        "p_value": round(float(p_value), 6),
        "significance": significance,
        "lags_used": int(lags),
        "n_obs": int(n_obs),
        "critical_values": {k: round(float(v), 6) for k, v in crit.items()},
        "is_stationary": is_stationary,
        "verdict": "Dừng (p < 0.05)" if is_stationary else "Không dừng (p ≥ 0.05)",
    }


def build_stationarity_report(
    frame: pd.DataFrame,
    price_col: str = "price_usd",
) -> dict[str, Any]:
    """Run ADF on levels, diff-1, diff-2 and conclude recommended d."""
    series = frame[price_col].dropna()
    if series.empty:
        return {"error": "Không có dữ liệu giá để kiểm định."}

    levels = _run_adf(series, "Giá gốc (levels)")
    diff1  = _run_adf(series.diff().dropna(), "Sai phân bậc 1 (Δ price)")
    diff2  = _run_adf(series.diff().diff().dropna(), "Sai phân bậc 2 (Δ² price)")

    if levels["is_stationary"]:
        d_recommended = 0
        conclusion = "Chuỗi gốc đã dừng — không cần lấy sai phân (d = 0)."
        needs_diff = False
    elif diff1.get("is_stationary"):
        d_recommended = 1
        conclusion = "Chuỗi gốc không dừng, sai phân bậc 1 đã dừng — dùng d = 1."
        needs_diff = True
    elif diff2.get("is_stationary"):
        d_recommended = 2
        conclusion = "Cần lấy sai phân bậc 2 để đạt dừng — dùng d = 2."
        needs_diff = True
    else:
        d_recommended = 2
        conclusion = "Chuỗi vẫn không dừng sau bậc 2 — kiểm tra lại dữ liệu hoặc thử transformation."
        needs_diff = True

    return {
        "n_obs": int(len(series)),
        "price_col": price_col,
        "tests": [levels, diff1, diff2],
        "conclusion": {
            "d_recommended": d_recommended,
            "needs_differencing": needs_diff,
            "summary": conclusion,
        },
    }
