from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pandas.plotting import autocorrelation_plot, lag_plot

matplotlib.use("Agg")

PRIMARY_COLOR = "#1d4ed8"
ACCENT_COLOR = "#ea580c"
FILL_COLOR = "#bfdbfe"
GRID_COLOR = "#cbd5e1"

CHART_TITLES = {
    "line": "Biểu đồ đường: Diễn biến giá theo thời gian",
    "moving_average": "Trung bình động: Làm mượt để thấy xu hướng",
    "aggregation": "Gộp theo kỳ: Quan sát xu hướng tổng quát",
    "boxplot": "Biểu đồ hộp: Nhìn độ phân tán và ngoại lệ",
    "histogram": "Biểu đồ tần suất: Phân bố của dữ liệu",
    "density": "Mật độ phân phối (KDE): Phân bố dạng mượt",
    "autocorrelation": "Tự tương quan: Mức phụ thuộc vào quá khứ",
    "lag": "Biểu đồ trễ: Quan hệ giữa hiện tại và quá khứ",
    "combo": "Tổng hợp nhanh: Xu hướng và phân phối dữ liệu",
    "log_return": "Log return: Tốc độ thay đổi giá theo thời gian",
    "volatility": "Rolling volatility: Mức độ rủi ro theo thời gian",
    "return_volatility_combo": "Kết hợp log return và volatility",
}


def prepare_series_frame(
    frame: pd.DataFrame,
    *,
    date_column: str | None,
    value_column: str,
) -> pd.DataFrame:
    dataset = frame.copy()

    if date_column:
        if date_column not in dataset.columns:
            raise ValueError(f"Date column '{date_column}' not found in dataset.")
        dataset[date_column] = pd.to_datetime(dataset[date_column], errors="coerce")
        dataset = dataset.dropna(subset=[date_column]).sort_values(date_column).set_index(date_column)
    else:
        if not isinstance(dataset.index, pd.DatetimeIndex):
            raise ValueError("Dataset index must be DatetimeIndex when date_column is not provided.")
        dataset = dataset.sort_index()

    if value_column not in dataset.columns:
        raise ValueError(f"Value column '{value_column}' not found in dataset.")

    dataset[value_column] = pd.to_numeric(dataset[value_column], errors="coerce")
    dataset = dataset.dropna(subset=[value_column])

    if dataset.empty:
        raise ValueError("Dataset is empty after cleaning.")

    return dataset


def load_frame_from_csv(
    csv_path: Path,
    *,
    date_column: str,
    value_column: str,
) -> pd.DataFrame:
    dataset = pd.read_csv(csv_path)

    if date_column not in dataset.columns and "Unnamed: 0" in dataset.columns:
        dataset = dataset.rename(columns={"Unnamed: 0": date_column})

    return prepare_series_frame(dataset, date_column=date_column, value_column=value_column)


def _style_time_axis(ax: plt.Axes) -> None:
    locator = mdates.AutoDateLocator(minticks=5, maxticks=8)
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    ax.tick_params(axis="x", rotation=0, labelsize=9)
    ax.grid(axis="y", color=GRID_COLOR, alpha=0.7, linewidth=0.8)
    ax.grid(axis="x", color=GRID_COLOR, alpha=0.15, linewidth=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _plot_timeline(
    ax: plt.Axes,
    series: pd.Series,
    *,
    moving_average: pd.Series | None = None,
    title: str,
    value_label: str,
) -> None:
    series_min = float(series.min())
    series_max = float(series.max())
    y_padding = max((series_max - series_min) * 0.15, series_max * 0.01)

    ax.plot(
        series.index,
        series,
        color=PRIMARY_COLOR,
        linewidth=1.8,
        alpha=0.9,
        label="Dữ liệu gốc",
    )
    ax.fill_between(
        series.index,
        series.values,
        series_min - y_padding * 0.15,
        color=FILL_COLOR,
        alpha=0.12,
    )

    if moving_average is not None:
        ax.plot(
            moving_average.index,
            moving_average,
            color=ACCENT_COLOR,
            linewidth=2.2,
            alpha=0.95,
            label="Trung bình động",
        )
        ax.legend(frameon=False, loc="lower left", bbox_to_anchor=(0, 1.02), ncol=2)

    ax.set_title(title)
    ax.set_xlabel("Thời gian")
    ax.set_ylabel(value_label)
    ax.set_ylim(series_min - y_padding, series_max + y_padding)
    _style_time_axis(ax)


def _build_return_metrics(series: pd.Series, *, volatility_window: int) -> tuple[pd.Series, pd.Series]:
    positive_series = series.dropna().astype(float)
    if (positive_series <= 0).any():
        raise ValueError("Log return requires all values in the selected series to be > 0.")

    log_return = np.log(positive_series / positive_series.shift(1))
    volatility = log_return.rolling(window=volatility_window).std()
    return log_return, volatility


def save_time_series_charts(
    frame: pd.DataFrame,
    *,
    value_column: str,
    output_dir: Path,
    moving_average_window: int = 7,
    volatility_window: int = 30,
    aggregation_rule: str = "W",
    histogram_bins: int = 10,
    lag: int = 1,
) -> list[Path]:
    if moving_average_window < 2:
        raise ValueError("moving_average_window must be >= 2.")
    if volatility_window < 2:
        raise ValueError("volatility_window must be >= 2.")
    if histogram_bins < 1:
        raise ValueError("histogram_bins must be >= 1.")
    if lag < 1:
        raise ValueError("lag must be >= 1.")

    dataset = frame.copy()
    series = dataset[value_column]
    moving_average = series.rolling(window=moving_average_window).mean()
    aggregated = series.resample(aggregation_rule).mean()
    log_return, volatility = _build_return_metrics(series, volatility_window=volatility_window)

    output_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []

    def save_current_figure(filename: str) -> None:
        path = output_dir / filename
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        saved_paths.append(path)

    start_value = float(series.iloc[0])
    end_value = float(series.iloc[-1])
    pct_change = ((end_value - start_value) / start_value) * 100
    subtitle_vi = (
        f"Giai đoạn: {series.index.min():%b %Y} đến {series.index.max():%b %Y} | "
        f"Đầu kỳ: {start_value:,.2f} | Cuối kỳ: {end_value:,.2f} | Thay đổi: {pct_change:+.1f}%"
    )

    fig, ax = plt.subplots(figsize=(11, 4.5))
    _plot_timeline(ax, series, title=CHART_TITLES["line"], value_label=value_column)
    fig.suptitle(subtitle_vi, y=0.98, fontsize=10, color="#475569")
    save_current_figure("01_trend_overview_line_chart.png")

    fig, ax = plt.subplots(figsize=(11, 4.5))
    _plot_timeline(
        ax,
        series,
        moving_average=moving_average,
        title=f"{CHART_TITLES['moving_average']} (cửa sổ={moving_average_window})",
        value_label=value_column,
    )
    fig.suptitle(subtitle_vi, y=0.98, fontsize=10, color="#475569")
    save_current_figure("02_trend_smoothing_moving_average_chart.png")

    fig, ax = plt.subplots(figsize=(11, 4.5))
    _plot_timeline(
        ax,
        aggregated,
        title=f"{CHART_TITLES['aggregation']} ({aggregation_rule})",
        value_label=f"Trung bình {value_column}",
    )
    fig.suptitle(subtitle_vi, y=0.98, fontsize=10, color="#475569")
    save_current_figure(f"03_trend_zoom_aggregation_{aggregation_rule.lower()}_chart.png")

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.boxplot(series.dropna())
    ax.set_title(CHART_TITLES["boxplot"])
    ax.set_ylabel(value_column)
    ax.grid(alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save_current_figure("04_distribution_outlier_boxplot_chart.png")

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(series.dropna(), bins=histogram_bins, edgecolor="black", alpha=0.85, color=PRIMARY_COLOR)
    ax.set_title(CHART_TITLES["histogram"])
    ax.set_xlabel(value_column)
    ax.set_ylabel("Tần suất")
    ax.grid(alpha=0.2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save_current_figure("05_distribution_frequency_histogram_chart.png")

    fig, ax = plt.subplots(figsize=(8, 4))
    series.plot(kind="kde", ax=ax, color=PRIMARY_COLOR)
    ax.set_title(CHART_TITLES["density"])
    ax.set_xlabel(value_column)
    ax.grid(alpha=0.2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save_current_figure("06_distribution_density_kde_chart.png")

    fig, ax = plt.subplots(figsize=(8, 4))
    autocorrelation_plot(series.dropna(), ax=ax)
    ax.set_title(CHART_TITLES["autocorrelation"])
    ax.set_xlabel("Độ trễ")
    ax.grid(alpha=0.2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save_current_figure("07_time_dependency_autocorrelation_chart.png")

    fig, ax = plt.subplots(figsize=(5, 5))
    lag_plot(series.dropna(), lag=lag, ax=ax)
    ax.set_title(f"{CHART_TITLES['lag']} (lag={lag})")
    ax.grid(alpha=0.2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save_current_figure("08_time_dependency_lag_relationship_chart.png")

    fig = plt.figure(figsize=(12, 8))
    fig.suptitle(CHART_TITLES["combo"], fontsize=14, y=0.98)

    plt.subplot(2, 2, 1)
    _plot_timeline(plt.gca(), series, title="1. Biểu đồ đường", value_label=value_column)

    plt.subplot(2, 2, 2)
    _plot_timeline(
        plt.gca(),
        series,
        moving_average=moving_average,
        title="2. Trung bình động",
        value_label=value_column,
    )

    plt.subplot(2, 2, 3)
    plt.hist(series.dropna(), bins=histogram_bins, edgecolor="black", alpha=0.85)
    plt.title("3. Biểu đồ tần suất")
    plt.xlabel(value_column)
    plt.ylabel("Tần suất")
    plt.grid(alpha=0.2)

    plt.subplot(2, 2, 4)
    plt.boxplot(series.dropna())
    plt.title("4. Biểu đồ hộp")
    plt.ylabel(value_column)
    plt.grid(alpha=0.2)

    save_current_figure("09_analysis_summary_combo_chart.png")

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(log_return.index, log_return.values, color=PRIMARY_COLOR, linewidth=1.4, alpha=0.9)
    ax.axhline(0, color="#64748b", linewidth=1, linestyle="--", alpha=0.8)
    ax.fill_between(log_return.index, log_return.values, 0, color=FILL_COLOR, alpha=0.18)
    ax.set_title(CHART_TITLES["log_return"])
    ax.set_xlabel("Thời gian")
    ax.set_ylabel("Log return")
    _style_time_axis(ax)
    fig.suptitle(
        f"Biến động tương đối ngày-liền-kề | Số quan sát hợp lệ: {log_return.dropna().shape[0]}",
        y=0.98,
        fontsize=10,
        color="#475569",
    )
    save_current_figure("10_return_log_return_chart.png")

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(volatility.index, volatility.values, color=ACCENT_COLOR, linewidth=1.8, alpha=0.95)
    ax.fill_between(volatility.index, volatility.values, 0, color="#fed7aa", alpha=0.2)
    ax.set_title(f"{CHART_TITLES['volatility']} (cửa sổ={volatility_window})")
    ax.set_xlabel("Thời gian")
    ax.set_ylabel("Độ lệch chuẩn của log return")
    _style_time_axis(ax)
    fig.suptitle(
        "Volatility cao hơn thường đi kèm rủi ro và độ bất định lớn hơn",
        y=0.98,
        fontsize=10,
        color="#475569",
    )
    save_current_figure("11_return_rolling_volatility_chart.png")

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(
        log_return.index,
        log_return.values,
        color=PRIMARY_COLOR,
        linewidth=1.6,
        alpha=0.9,
        label="Log return",
    )
    ax.plot(
        volatility.index,
        volatility.values,
        color="#dc2626",
        linewidth=2.0,
        alpha=0.95,
        label=f"Rolling volatility ({volatility_window})",
    )
    ax.axhline(0, color="#64748b", linewidth=1, linestyle="--", alpha=0.7)
    ax.set_title(CHART_TITLES["return_volatility_combo"])
    ax.set_xlabel("Thời gian")
    ax.set_ylabel("Giá trị")
    ax.legend(frameon=True, facecolor="white", edgecolor="#cbd5e1", loc="upper right")
    _style_time_axis(ax)
    fig.suptitle(
        "Quan sát đồng thời tốc độ thay đổi giá và các cụm biến động mạnh",
        y=0.98,
        fontsize=10,
        color="#475569",
    )
    save_current_figure("12_return_volatility_combined_chart.png")

    return saved_paths


# ── Academic analysis charts (monthly series) ────────────────────────────────

def save_acf_pacf_chart(
    series: pd.Series,
    output_dir: Path,
    lags: int = 24,
) -> Path:
    """ACF + PACF plot — nhận diện tự tương quan và chọn p, q cho ARIMA."""
    from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

    output_dir.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 6))
    plot_acf(series.dropna(), lags=lags, ax=ax1, color=PRIMARY_COLOR)
    ax1.set_title("ACF — Hàm tự tương quan (nhận diện q cho ARIMA)", fontsize=11)
    ax1.set_xlabel("Độ trễ (tháng)")
    ax1.grid(axis="y", color=GRID_COLOR, alpha=0.5)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    plot_pacf(series.dropna(), lags=lags, ax=ax2, color=ACCENT_COLOR, method="ywm")
    ax2.set_title("PACF — Hàm tự tương quan riêng phần (nhận diện p cho ARIMA)", fontsize=11)
    ax2.set_xlabel("Độ trễ (tháng)")
    ax2.grid(axis="y", color=GRID_COLOR, alpha=0.5)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    fig.suptitle("Phân tích tự tương quan chuỗi giá bạc (monthly)", fontsize=13, y=1.01)
    out_path = output_dir / "10_acf_pacf_chart.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    return out_path


def save_stationarity_chart(
    series: pd.Series,
    stationarity_report: dict,
    output_dir: Path,
) -> Path:
    """Vẽ 3 panel: giá gốc, sai phân bậc 1, sai phân bậc 2 — mỗi panel annotate kết quả ADF."""
    output_dir.mkdir(parents=True, exist_ok=True)

    levels = series.dropna()
    diff1 = levels.diff().dropna()
    diff2 = levels.diff().diff().dropna()

    tests = {t["label"]: t for t in stationarity_report.get("tests", [])}

    panels = [
        ("Giá gốc (Levels)", levels, PRIMARY_COLOR),
        ("Sai phân bậc 1 (Δ price)", diff1, ACCENT_COLOR),
        ("Sai phân bậc 2 (Δ² price)", diff2, "#16a34a"),
    ]

    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=False)

    for ax, (label, data, color) in zip(axes, panels):
        ax.plot(data.index, data.values, color=color, linewidth=1.3, alpha=0.9)
        ax.grid(axis="y", color=GRID_COLOR, alpha=0.5)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        test_result = tests.get(label, {})
        if test_result and "p_value" in test_result:
            p = test_result["p_value"]
            stat = test_result["test_statistic"]
            is_stationary = test_result.get("is_stationary", False)
            verdict_color = "#16a34a" if is_stationary else "#dc2626"
            verdict_text = "DỪNG ✓" if is_stationary else "KHÔNG DỪNG ✗"
            annotation = f"ADF = {stat:.3f} | p = {p:.4f} → {verdict_text}"
            ax.set_title(f"{label}", fontsize=10, loc="left", fontweight="bold")
            ax.text(
                0.99, 0.92, annotation,
                transform=ax.transAxes,
                ha="right", va="top", fontsize=9,
                color=verdict_color,
                bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": verdict_color, "alpha": 0.8},
            )
        else:
            ax.set_title(label, fontsize=10, loc="left", fontweight="bold")

    d_rec = stationarity_report.get("conclusion", {}).get("d_recommended", "?")
    fig.suptitle(
        f"Kiểm định tính dừng ADF — Tham số d đề xuất cho ARIMA: d = {d_rec}",
        fontsize=12, y=1.01,
    )
    plt.tight_layout()
    out_path = output_dir / "11_stationarity_adf_chart.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    return out_path


def save_decomposition_charts(
    series: pd.Series,
    output_dir: Path,
    period: int = 12,
) -> list[Path]:
    """Phân rã cộng và nhân — vẽ observed, trend, seasonal, residual."""
    from statsmodels.tsa.seasonal import seasonal_decompose

    output_dir.mkdir(parents=True, exist_ok=True)
    clean = series.dropna()
    saved: list[Path] = []

    for model in ("additive", "multiplicative"):
        result = seasonal_decompose(clean, model=model, period=period)
        fig, axes = plt.subplots(4, 1, figsize=(11, 10), sharex=True)
        components = [
            ("Dữ liệu gốc (Observed)", result.observed, PRIMARY_COLOR),
            ("Xu hướng (Trend)", result.trend, ACCENT_COLOR),
            ("Thời vụ (Seasonal)", result.seasonal, "#16a34a"),
            ("Phần dư (Residual)", result.resid, "#9333ea"),
        ]
        for ax, (title, comp, color) in zip(axes, components):
            ax.plot(comp.index, comp, color=color, linewidth=1.5)
            ax.set_title(title, fontsize=10, loc="left")
            ax.grid(axis="y", color=GRID_COLOR, alpha=0.4)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

        model_vn = "Cộng (Additive)" if model == "additive" else "Nhân (Multiplicative)"
        fig.suptitle(
            f"Phân rã chuỗi thời gian — Mô hình {model_vn} | period={period}",
            fontsize=13,
        )
        num = "12" if model == "additive" else "13"
        filename = f"{num}_decomposition_{model}_chart.png"
        out_path = output_dir / filename
        plt.tight_layout()
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close()
        saved.append(out_path)

    return saved


def save_forecast_comparison_chart(
    series: pd.Series,
    results_dicts: list[dict],
    output_dir: Path,
) -> Path:
    """Biểu đồ so sánh dự báo của tất cả mô hình trên tập test vs actual."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(13, 5))

    colors = ["#1d4ed8", "#ea580c", "#16a34a", "#9333ea", "#dc2626", "#0891b2"]
    for result, color in zip(results_dicts, colors):
        preds = result.get("predictions", [])
        if not preds:
            continue
        dates = pd.to_datetime([p["date"] for p in preds])
        predicted = [p["predicted"] for p in preds]
        ax.plot(dates, predicted, color=color, linewidth=1.8,
                linestyle="--", label=result["model_name"], alpha=0.85)

    # Vẽ actual từ result đầu tiên có predictions
    for result in results_dicts:
        preds = result.get("predictions", [])
        if preds:
            dates = pd.to_datetime([p["date"] for p in preds])
            actual = [p["actual"] for p in preds]
            ax.plot(dates, actual, color="black", linewidth=2.5, label="Actual", zorder=10)
            break

    ax.set_title("So sánh dự báo các mô hình vs Thực tế (tập Test)", fontsize=12)
    ax.set_xlabel("Thời gian")
    ax.set_ylabel("Giá bạc (USD/ounce)")
    ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=3)
    ax.grid(axis="y", color=GRID_COLOR, alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _style_time_axis(ax)

    out_path = output_dir / "14_forecast_comparison_chart.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    return out_path


def save_future_forecast_chart(
    series: pd.Series,
    future_forecast: dict,
    output_dir: Path,
) -> Path:
    """Biểu đồ dự báo tương lai từ mô hình tốt nhất (6–12 tháng)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    forecast_list = future_forecast.get("forecast", [])
    model_name = future_forecast.get("model", "Model")
    n_months = future_forecast.get("n_months", len(forecast_list))

    if not forecast_list:
        raise ValueError("future_forecast không có dữ liệu forecast.")

    fut_dates = pd.to_datetime([f["date"] for f in forecast_list])
    fut_preds = [f["predicted"] for f in forecast_list]
    has_ci = "lower_95" in forecast_list[0]

    fig, ax = plt.subplots(figsize=(13, 5))

    # Lịch sử (12 tháng cuối)
    tail = series.dropna().tail(36)
    ax.plot(tail.index, tail.values, color=PRIMARY_COLOR, linewidth=2, label="Lịch sử")

    # Forecast
    ax.plot(fut_dates, fut_preds, color=ACCENT_COLOR, linewidth=2.5,
            linestyle="--", marker="o", markersize=4, label=f"Dự báo ({model_name})")

    if has_ci:
        lower = [f["lower_95"] for f in forecast_list]
        upper = [f["upper_95"] for f in forecast_list]
        ax.fill_between(fut_dates, lower, upper, color=ACCENT_COLOR, alpha=0.15,
                        label="Khoảng tin cậy 95%")

    ax.axvline(x=series.dropna().index.max(), color="gray", linewidth=1, linestyle=":")
    ax.set_title(
        f"Dự báo {n_months} tháng tới — Mô hình tốt nhất: {model_name}",
        fontsize=12,
    )
    ax.set_xlabel("Thời gian")
    ax.set_ylabel("Giá bạc (USD/ounce)")
    ax.legend(frameon=False)
    ax.grid(axis="y", color=GRID_COLOR, alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _style_time_axis(ax)

    out_path = output_dir / "15_future_forecast_chart.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    return out_path
