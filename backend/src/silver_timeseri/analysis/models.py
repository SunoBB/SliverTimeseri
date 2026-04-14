from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tools.sm_exceptions import ConvergenceWarning

from silver_timeseri.analysis.features import DEFAULT_INDICATORS, add_lag_features, add_technical_indicators


@dataclass
class ModelRunResult:
    model_name: str
    train_size: int
    test_size: int
    metrics: dict[str, float | None]
    parameters: dict[str, Any]
    predictions: list[dict[str, Any]]
    direction_backtest: dict[str, Any] | None = None
    next_forecast: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "train_size": self.train_size,
            "test_size": self.test_size,
            "metrics": self.metrics,
            "parameters": self.parameters,
            "predictions": self.predictions,
            "direction_backtest": self.direction_backtest,
            "next_forecast": self.next_forecast,
        }


def split_train_test(frame: pd.DataFrame, test_size: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    if len(frame) <= test_size:
        raise ValueError("Dataset is too small for the requested test_size.")
    train = frame.iloc[:-test_size].copy()
    test = frame.iloc[-test_size:].copy()
    return train, test


def evaluate_predictions(actual: pd.Series, predicted: pd.Series) -> dict[str, float | None]:
    aligned = pd.concat([actual, predicted], axis=1, keys=["actual", "predicted"]).dropna()
    if aligned.empty:
        return {"mae": None, "rmse": None, "mape": None}

    error = aligned["actual"] - aligned["predicted"]
    absolute_percentage = (error.abs() / aligned["actual"].replace(0, np.nan)).dropna()
    return {
        "mae": round(float(error.abs().mean()), 6),
        "rmse": round(float(np.sqrt((error**2).mean())), 6),
        "mape": round(float(absolute_percentage.mean() * 100), 6) if not absolute_percentage.empty else None,
    }


def train_arx_model(
    frame: pd.DataFrame,
    ar_order: int,
    test_size: int,
    indicator_columns: list[str] | None = None,
) -> ModelRunResult:
    indicators = indicator_columns or DEFAULT_INDICATORS
    dataset = add_technical_indicators(frame)
    dataset = add_lag_features(dataset, order=ar_order, column="price_usd")

    feature_columns = [f"price_usd_lag_{lag}" for lag in range(1, ar_order + 1)] + indicators
    dataset = dataset.dropna(subset=feature_columns + ["price_usd"])
    if dataset.empty:
        raise ValueError("Not enough rows to train ARX after creating indicators and lags.")
    train, test = split_train_test(dataset, test_size=test_size)

    x_train = train[feature_columns].to_numpy(dtype=float)
    y_train = train["price_usd"].to_numpy(dtype=float)
    x_test = test[feature_columns].to_numpy(dtype=float)

    x_train_design = np.column_stack([np.ones(len(x_train)), x_train])
    x_test_design = np.column_stack([np.ones(len(x_test)), x_test])

    coefficients, _, _, _ = np.linalg.lstsq(x_train_design, y_train, rcond=None)
    predictions = pd.Series(x_test_design @ coefficients, index=test.index, name="predicted")
    metrics = evaluate_predictions(test["price_usd"], predictions)

    coefficient_map = {"intercept": round(float(coefficients[0]), 6)}
    for index, feature_name in enumerate(feature_columns, start=1):
        coefficient_map[feature_name] = round(float(coefficients[index]), 6)

    next_forecast = forecast_next_day_arx(
        frame=frame,
        ar_order=ar_order,
        indicator_columns=indicators,
    )

    return ModelRunResult(
        model_name="ARX",
        train_size=len(train),
        test_size=len(test),
        metrics=metrics,
        parameters={
            "ar_order": ar_order,
            "indicators": indicators,
            "coefficients": coefficient_map,
        },
        predictions=_format_predictions(test["price_usd"], predictions),
        direction_backtest=_summarize_direction_backtest(frame, test["price_usd"], predictions),
        next_forecast=next_forecast,
    )


def train_ma_model(frame: pd.DataFrame, ma_order: int, test_size: int) -> ModelRunResult:
    dataset = frame[["price_usd"]].dropna()
    if len(dataset) <= ma_order + test_size:
        raise ValueError("Not enough rows to train MA with the requested order and test_size.")
    train, test = split_train_test(dataset, test_size=test_size)
    train_series = train["price_usd"].reset_index(drop=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        warnings.simplefilter("ignore", category=ConvergenceWarning)
        fitted = ARIMA(train_series, order=(0, 0, ma_order)).fit()
    predictions = fitted.forecast(steps=len(test))
    predictions.index = test.index
    next_forecast = forecast_next_day_ma(frame=frame, ma_order=ma_order)

    return ModelRunResult(
        model_name="MA",
        train_size=len(train),
        test_size=len(test),
        metrics=evaluate_predictions(test["price_usd"], predictions),
        parameters={
            "ma_order": ma_order,
            "aic": round(float(fitted.aic), 6),
            "bic": round(float(fitted.bic), 6),
            "params": _round_mapping(fitted.params.to_dict()),
        },
        predictions=_format_predictions(test["price_usd"], predictions),
        direction_backtest=_summarize_direction_backtest(frame, test["price_usd"], predictions),
        next_forecast=next_forecast,
    )


def train_arma_model(
    frame: pd.DataFrame,
    ar_order: int,
    ma_order: int,
    test_size: int,
) -> ModelRunResult:
    dataset = frame[["price_usd"]].dropna()
    if len(dataset) <= ar_order + ma_order + test_size:
        raise ValueError("Not enough rows to train ARMA with the requested orders and test_size.")
    train, test = split_train_test(dataset, test_size=test_size)
    train_series = train["price_usd"].reset_index(drop=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        warnings.simplefilter("ignore", category=ConvergenceWarning)
        fitted = ARIMA(train_series, order=(ar_order, 0, ma_order)).fit()
    predictions = fitted.forecast(steps=len(test))
    predictions.index = test.index
    next_forecast = forecast_next_day_arma(frame=frame, ar_order=ar_order, ma_order=ma_order)

    return ModelRunResult(
        model_name="ARMA",
        train_size=len(train),
        test_size=len(test),
        metrics=evaluate_predictions(test["price_usd"], predictions),
        parameters={
            "ar_order": ar_order,
            "ma_order": ma_order,
            "aic": round(float(fitted.aic), 6),
            "bic": round(float(fitted.bic), 6),
            "params": _round_mapping(fitted.params.to_dict()),
        },
        predictions=_format_predictions(test["price_usd"], predictions),
        direction_backtest=_summarize_direction_backtest(frame, test["price_usd"], predictions),
        next_forecast=next_forecast,
    )


def run_model_suite(
    frame: pd.DataFrame,
    ar_order: int,
    ma_order: int,
    test_size: int,
) -> list[ModelRunResult]:
    return [
        train_arx_model(frame=frame, ar_order=ar_order, test_size=test_size),
        train_ma_model(frame=frame, ma_order=ma_order, test_size=test_size),
        train_arma_model(
            frame=frame,
            ar_order=ar_order,
            ma_order=ma_order,
            test_size=test_size,
        ),
    ]


def forecast_next_day_arx(
    frame: pd.DataFrame,
    ar_order: int,
    indicator_columns: list[str] | None = None,
) -> dict[str, Any]:
    indicators = indicator_columns or DEFAULT_INDICATORS
    dataset = add_technical_indicators(frame)
    dataset = add_lag_features(dataset, order=ar_order, column="price_usd")
    feature_columns = [f"price_usd_lag_{lag}" for lag in range(1, ar_order + 1)] + indicators
    dataset = dataset.dropna(subset=feature_columns + ["price_usd"])
    if dataset.empty:
        raise ValueError("Not enough rows to forecast next day with ARX.")

    x_train = dataset[feature_columns].to_numpy(dtype=float)
    y_train = dataset["price_usd"].to_numpy(dtype=float)
    x_train_design = np.column_stack([np.ones(len(x_train)), x_train])
    coefficients, _, _, _ = np.linalg.lstsq(x_train_design, y_train, rcond=None)

    future_row = _build_next_day_arx_features(frame=frame, ar_order=ar_order, indicators=indicators)
    x_future = np.array([1.0] + [float(future_row[column]) for column in feature_columns], dtype=float)
    predicted = float(x_future @ coefficients)
    next_date = (frame.index.max() + pd.Timedelta(days=1)).date().isoformat()

    return {
        "date": next_date,
        "predicted": round(predicted, 6),
        "predicted_direction": _direction_label(predicted - float(frame["price_usd"].iloc[-1])),
    }


def forecast_next_day_ma(frame: pd.DataFrame, ma_order: int) -> dict[str, Any]:
    dataset = frame[["price_usd"]].dropna()
    if len(dataset) <= ma_order + 1:
        raise ValueError("Not enough rows to forecast next day with MA.")
    price_series = dataset["price_usd"].reset_index(drop=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        warnings.simplefilter("ignore", category=ConvergenceWarning)
        fitted = ARIMA(price_series, order=(0, 0, ma_order)).fit()
    forecast_result = fitted.get_forecast(steps=1)
    next_date = (dataset.index.max() + pd.Timedelta(days=1)).date().isoformat()
    conf_int = forecast_result.conf_int(alpha=0.05)
    return {
        "date": next_date,
        "predicted": round(float(forecast_result.predicted_mean.iloc[0]), 6),
        "lower_95": round(float(conf_int.iloc[0, 0]), 6),
        "upper_95": round(float(conf_int.iloc[0, 1]), 6),
        "predicted_direction": _direction_label(
            float(forecast_result.predicted_mean.iloc[0]) - float(dataset["price_usd"].iloc[-1])
        ),
    }


def forecast_next_day_arma(frame: pd.DataFrame, ar_order: int, ma_order: int) -> dict[str, Any]:
    dataset = frame[["price_usd"]].dropna()
    if len(dataset) <= ar_order + ma_order + 1:
        raise ValueError("Not enough rows to forecast next day with ARMA.")
    price_series = dataset["price_usd"].reset_index(drop=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        warnings.simplefilter("ignore", category=ConvergenceWarning)
        fitted = ARIMA(price_series, order=(ar_order, 0, ma_order)).fit()
    forecast_result = fitted.get_forecast(steps=1)
    next_date = (dataset.index.max() + pd.Timedelta(days=1)).date().isoformat()
    conf_int = forecast_result.conf_int(alpha=0.05)
    return {
        "date": next_date,
        "predicted": round(float(forecast_result.predicted_mean.iloc[0]), 6),
        "lower_95": round(float(conf_int.iloc[0, 0]), 6),
        "upper_95": round(float(conf_int.iloc[0, 1]), 6),
        "predicted_direction": _direction_label(
            float(forecast_result.predicted_mean.iloc[0]) - float(dataset["price_usd"].iloc[-1])
        ),
    }


def _build_next_day_arx_features(
    frame: pd.DataFrame,
    ar_order: int,
    indicators: list[str],
) -> dict[str, float]:
    clean = frame.sort_index().copy()
    if len(clean) < max(ar_order, 20) + 1:
        raise ValueError("Not enough rows to build ARX next-day features.")

    prices = clean["price_usd"].astype(float)
    returns = prices.pct_change()

    values: dict[str, float] = {}
    for lag in range(1, ar_order + 1):
        values[f"price_usd_lag_{lag}"] = float(prices.iloc[-lag])

    if "return_1d" in indicators:
        values["return_1d"] = float(returns.iloc[-1])
    if "ma_5" in indicators:
        values["ma_5"] = float(prices.tail(5).mean())
    if "ma_10" in indicators:
        values["ma_10"] = float(prices.tail(10).mean())
    if "ma_20" in indicators:
        values["ma_20"] = float(prices.tail(20).mean())
    if "volatility_5" in indicators:
        values["volatility_5"] = float(returns.tail(5).std())
    if "volatility_10" in indicators:
        values["volatility_10"] = float(returns.tail(10).std())
    if "momentum_5" in indicators:
        values["momentum_5"] = float(prices.iloc[-1] - prices.iloc[-6])
    return values


def _format_predictions(actual: pd.Series, predicted: pd.Series) -> list[dict[str, Any]]:
    rows = []
    for index, actual_value in actual.items():
        predicted_value = predicted.loc[index]
        rows.append(
            {
                "date": index.date().isoformat(),
                "actual": round(float(actual_value), 6),
                "predicted": round(float(predicted_value), 6),
                "error": round(float(actual_value - predicted_value), 6),
            }
        )
    return rows


def _summarize_direction_backtest(
    frame: pd.DataFrame,
    actual: pd.Series,
    predicted: pd.Series,
) -> dict[str, Any]:
    clean_prices = frame["price_usd"].dropna().astype(float)
    aligned = pd.concat([actual.astype(float), predicted.astype(float)], axis=1, keys=["actual", "predicted"]).dropna()

    rows: list[dict[str, Any]] = []
    for index, row in aligned.iterrows():
        location = clean_prices.index.get_loc(index)
        if not isinstance(location, int) or location == 0:
            continue
        previous_actual = float(clean_prices.iloc[location - 1])
        actual_delta = float(row["actual"] - previous_actual)
        predicted_delta = float(row["predicted"] - previous_actual)
        actual_direction = _direction_label(actual_delta)
        predicted_direction = _direction_label(predicted_delta)
        rows.append(
            {
                "date": index.date().isoformat(),
                "previous_actual": round(previous_actual, 6),
                "actual_direction": actual_direction,
                "predicted_direction": predicted_direction,
                "is_correct": actual_direction == predicted_direction,
                "actual_delta": round(actual_delta, 6),
                "predicted_delta": round(predicted_delta, 6),
            }
        )

    if not rows:
        return {
            "samples": 0,
            "correct": 0,
            "accuracy": None,
            "actual_up": 0,
            "actual_down": 0,
            "predicted_up": 0,
            "predicted_down": 0,
            "recent_hits": [],
        }

    samples = len(rows)
    correct = sum(1 for row in rows if row["is_correct"])
    actual_up = sum(1 for row in rows if row["actual_direction"] == "up")
    actual_down = sum(1 for row in rows if row["actual_direction"] == "down")
    predicted_up = sum(1 for row in rows if row["predicted_direction"] == "up")
    predicted_down = sum(1 for row in rows if row["predicted_direction"] == "down")

    return {
        "samples": samples,
        "correct": correct,
        "accuracy": round((correct / samples) * 100, 6),
        "actual_up": actual_up,
        "actual_down": actual_down,
        "predicted_up": predicted_up,
        "predicted_down": predicted_down,
        "recent_hits": rows[-10:],
    }


def _direction_label(delta: float, tolerance: float = 1e-9) -> str:
    if delta > tolerance:
        return "up"
    if delta < -tolerance:
        return "down"
    return "flat"


def _round_mapping(values: dict[str, Any]) -> dict[str, Any]:
    rounded: dict[str, Any] = {}
    for key, value in values.items():
        if isinstance(value, (float, int, np.floating, np.integer)):
            rounded[key] = round(float(value), 6)
        else:
            rounded[key] = value
    return rounded


# ── Academic models (monthly series, period=12) ──────────────────────────────

def _split_monthly(monthly: pd.DataFrame, test_size: int) -> tuple[pd.Series, pd.Series]:
    series = monthly["price_usd"].dropna()
    if len(series) <= test_size:
        raise ValueError("Không đủ dữ liệu monthly cho test_size yêu cầu.")
    return series.iloc[:-test_size], series.iloc[-test_size:]


def train_ses_model(monthly: pd.DataFrame, test_size: int) -> ModelRunResult:
    """Simple Exponential Smoothing — không có trend, không có seasonal."""
    from statsmodels.tsa.holtwinters import SimpleExpSmoothing

    train, test = _split_monthly(monthly, test_size)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = SimpleExpSmoothing(train, initialization_method="estimated").fit(optimized=True)
    preds = fitted.forecast(len(test))
    preds.index = test.index
    next_date = (test.index.max() + pd.DateOffset(months=1)).date().isoformat()

    return ModelRunResult(
        model_name="SES",
        train_size=len(train),
        test_size=len(test),
        metrics=evaluate_predictions(test, preds),
        parameters={
            "smoothing_level": round(float(fitted.params["smoothing_level"]), 6),
            "aic": round(float(fitted.aic), 6),
        },
        predictions=_format_predictions(test, preds),
        next_forecast={
            "date": next_date,
            "predicted": round(float(fitted.forecast(1).iloc[0]), 6),
        },
    )


def train_holt_model(monthly: pd.DataFrame, test_size: int, damped: bool = False) -> ModelRunResult:
    """Holt's Linear (hoặc Damped) Trend — có trend tuyến tính."""
    from statsmodels.tsa.holtwinters import Holt

    train, test = _split_monthly(monthly, test_size)
    model_name = "Holt Damped" if damped else "Holt Linear"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = Holt(train, damped_trend=damped, initialization_method="estimated").fit(optimized=True)
    preds = fitted.forecast(len(test))
    preds.index = test.index
    next_date = (test.index.max() + pd.DateOffset(months=1)).date().isoformat()

    return ModelRunResult(
        model_name=model_name,
        train_size=len(train),
        test_size=len(test),
        metrics=evaluate_predictions(test, preds),
        parameters={
            "smoothing_level": round(float(fitted.params["smoothing_level"]), 6),
            "smoothing_trend": round(float(fitted.params["smoothing_trend"]), 6),
            "damped": damped,
            "aic": round(float(fitted.aic), 6),
        },
        predictions=_format_predictions(test, preds),
        next_forecast={
            "date": next_date,
            "predicted": round(float(fitted.forecast(1).iloc[0]), 6),
        },
    )


def train_hw_model(monthly: pd.DataFrame, test_size: int, seasonal: str = "add") -> ModelRunResult:
    """Holt-Winters — có trend và seasonal (cộng hoặc nhân), period=12."""
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    train, test = _split_monthly(monthly, test_size)
    if len(train) < 24:
        raise ValueError("Holt-Winters cần ít nhất 24 quan sát monthly để khởi tạo seasonal.")
    model_name = "HW Additive" if seasonal == "add" else "HW Multiplicative"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = ExponentialSmoothing(
            train,
            trend="add",
            seasonal=seasonal,
            seasonal_periods=12,
            initialization_method="estimated",
        ).fit(optimized=True)
    preds = fitted.forecast(len(test))
    preds.index = test.index
    next_date = (test.index.max() + pd.DateOffset(months=1)).date().isoformat()

    return ModelRunResult(
        model_name=model_name,
        train_size=len(train),
        test_size=len(test),
        metrics=evaluate_predictions(test, preds),
        parameters={
            "smoothing_level": round(float(fitted.params["smoothing_level"]), 6),
            "smoothing_trend": round(float(fitted.params["smoothing_trend"]), 6),
            "smoothing_seasonal": round(float(fitted.params["smoothing_seasonal"]), 6),
            "seasonal_type": seasonal,
            "aic": round(float(fitted.aic), 6),
        },
        predictions=_format_predictions(test, preds),
        next_forecast={
            "date": next_date,
            "predicted": round(float(fitted.forecast(1).iloc[0]), 6),
        },
    )


def train_arima_monthly_model(
    monthly: pd.DataFrame,
    order: tuple[int, int, int] = (1, 1, 1),
    test_size: int = 12,
) -> ModelRunResult:
    """ARIMA(p,d,q) trên chuỗi monthly — d xác định từ ADF test."""
    train, test = _split_monthly(monthly, test_size)
    train_reset = train.reset_index(drop=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        warnings.simplefilter("ignore", category=ConvergenceWarning)
        fitted = ARIMA(train_reset, order=order).fit()
    forecast_result = fitted.get_forecast(steps=len(test))
    preds = pd.Series(forecast_result.predicted_mean.values, index=test.index)
    conf_int = forecast_result.conf_int(alpha=0.05)
    next_date = (test.index.max() + pd.DateOffset(months=1)).date().isoformat()

    next_fc = fitted.get_forecast(steps=len(test) + 1)
    next_pred = float(next_fc.predicted_mean.iloc[-1])
    next_ci = next_fc.conf_int(alpha=0.05)

    return ModelRunResult(
        model_name=f"ARIMA{order}",
        train_size=len(train),
        test_size=len(test),
        metrics=evaluate_predictions(test, preds),
        parameters={
            "order": list(order),
            "aic": round(float(fitted.aic), 6),
            "bic": round(float(fitted.bic), 6),
        },
        predictions=[
            {
                "date": idx.date().isoformat(),
                "actual": round(float(act), 6),
                "predicted": round(float(pred), 6),
                "lower_95": round(float(conf_int.iloc[i, 0]), 6),
                "upper_95": round(float(conf_int.iloc[i, 1]), 6),
                "error": round(float(act - pred), 6),
            }
            for i, (idx, act, pred) in enumerate(
                zip(test.index, test.values, preds.values)
            )
        ],
        next_forecast={
            "date": next_date,
            "predicted": round(next_pred, 6),
            "lower_95": round(float(next_ci.iloc[-1, 0]), 6),
            "upper_95": round(float(next_ci.iloc[-1, 1]), 6),
        },
    )


def run_academic_suite(
    monthly: pd.DataFrame,
    test_size: int = 12,
    arima_order: tuple[int, int, int] = (1, 1, 1),
) -> list[ModelRunResult]:
    """Chạy đủ 6 mô hình academic trên chuỗi monthly theo slide giảng viên."""
    trainers = [
        ("SES", lambda: train_ses_model(monthly, test_size)),
        ("Holt Linear", lambda: train_holt_model(monthly, test_size, damped=False)),
        ("Holt Damped", lambda: train_holt_model(monthly, test_size, damped=True)),
        ("HW Additive", lambda: train_hw_model(monthly, test_size, seasonal="add")),
        ("HW Multiplicative", lambda: train_hw_model(monthly, test_size, seasonal="mul")),
        (f"ARIMA{arima_order}", lambda: train_arima_monthly_model(monthly, order=arima_order, test_size=test_size)),
    ]
    results = []
    for name, trainer in trainers:
        try:
            results.append(trainer())
        except Exception as exc:  # noqa: BLE001
            results.append(
                ModelRunResult(
                    model_name=name,
                    train_size=0,
                    test_size=0,
                    metrics={"mae": None, "rmse": None, "mape": None},
                    parameters={"error": str(exc)},
                    predictions=[],
                )
            )
    return results


def forecast_future_months(
    monthly: pd.DataFrame,
    model_name: str,
    n_months: int = 12,
    arima_order: tuple[int, int, int] = (1, 1, 1),
) -> dict[str, Any]:
    """Retrain best model trên toàn bộ data, dự báo n_months tháng tiếp theo."""
    from statsmodels.tsa.holtwinters import ExponentialSmoothing, Holt, SimpleExpSmoothing

    series = monthly["price_usd"].dropna()
    last_date = series.index.max()
    future_dates = [
        (last_date + pd.DateOffset(months=i + 1)).date().isoformat()
        for i in range(n_months)
    ]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        if model_name == "SES":
            fitted = SimpleExpSmoothing(series, initialization_method="estimated").fit(optimized=True)
            preds = fitted.forecast(n_months).values

        elif model_name == "Holt Linear":
            fitted = Holt(series, damped_trend=False, initialization_method="estimated").fit(optimized=True)
            preds = fitted.forecast(n_months).values

        elif model_name == "Holt Damped":
            fitted = Holt(series, damped_trend=True, initialization_method="estimated").fit(optimized=True)
            preds = fitted.forecast(n_months).values

        elif model_name == "HW Additive":
            fitted = ExponentialSmoothing(
                series, trend="add", seasonal="add", seasonal_periods=12,
                initialization_method="estimated",
            ).fit(optimized=True)
            preds = fitted.forecast(n_months).values

        elif model_name == "HW Multiplicative":
            fitted = ExponentialSmoothing(
                series, trend="add", seasonal="mul", seasonal_periods=12,
                initialization_method="estimated",
            ).fit(optimized=True)
            preds = fitted.forecast(n_months).values

        else:
            # Default: ARIMA
            series_reset = series.reset_index(drop=True)
            fitted_arima = ARIMA(series_reset, order=arima_order).fit()
            fc = fitted_arima.get_forecast(steps=n_months)
            ci = fc.conf_int(alpha=0.05)
            return {
                "model": model_name,
                "n_months": n_months,
                "forecast": [
                    {
                        "date": future_dates[i],
                        "predicted": round(float(fc.predicted_mean.iloc[i]), 6),
                        "lower_95": round(float(ci.iloc[i, 0]), 6),
                        "upper_95": round(float(ci.iloc[i, 1]), 6),
                    }
                    for i in range(n_months)
                ],
            }

    return {
        "model": model_name,
        "n_months": n_months,
        "forecast": [
            {"date": future_dates[i], "predicted": round(float(preds[i]), 6)}
            for i in range(n_months)
        ],
    }
