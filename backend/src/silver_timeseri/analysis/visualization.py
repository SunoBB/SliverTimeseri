from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
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


def save_time_series_charts(
    frame: pd.DataFrame,
    *,
    value_column: str,
    output_dir: Path,
    moving_average_window: int = 7,
    aggregation_rule: str = "W",
    histogram_bins: int = 10,
    lag: int = 1,
) -> list[Path]:
    if moving_average_window < 2:
        raise ValueError("moving_average_window must be >= 2.")
    if histogram_bins < 1:
        raise ValueError("histogram_bins must be >= 1.")
    if lag < 1:
        raise ValueError("lag must be >= 1.")

    dataset = frame.copy()
    series = dataset[value_column]
    moving_average = series.rolling(window=moving_average_window).mean()
    aggregated = series.resample(aggregation_rule).mean()

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
    subtitle = (
        f"{series.index.min():%b %Y} to {series.index.max():%b %Y} | "
        f"Start: {start_value:,.2f} | End: {end_value:,.2f} | {pct_change:+.1f}%"
    )
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

    plt.figure(figsize=(6, 4))
    plt.boxplot(series.dropna())
    plt.title(CHART_TITLES["boxplot"])
    plt.ylabel(value_column)
    plt.grid(alpha=0.25)
    save_current_figure("04_distribution_outlier_boxplot_chart.png")

    plt.figure(figsize=(8, 4))
    plt.hist(series.dropna(), bins=histogram_bins, edgecolor="black", alpha=0.85)
    plt.title(CHART_TITLES["histogram"])
    plt.xlabel(value_column)
    plt.ylabel("Tần suất")
    plt.grid(alpha=0.2)
    save_current_figure("05_distribution_frequency_histogram_chart.png")

    plt.figure(figsize=(8, 4))
    series.plot(kind="kde", title=CHART_TITLES["density"])
    plt.xlabel(value_column)
    plt.grid(alpha=0.2)
    save_current_figure("06_distribution_density_kde_chart.png")

    plt.figure(figsize=(8, 4))
    autocorrelation_plot(series.dropna())
    plt.title(CHART_TITLES["autocorrelation"])
    plt.xlabel("Độ trễ")
    plt.grid(alpha=0.2)
    save_current_figure("07_time_dependency_autocorrelation_chart.png")

    plt.figure(figsize=(5, 5))
    lag_plot(series.dropna(), lag=lag)
    plt.title(f"{CHART_TITLES['lag']} (lag={lag})")
    plt.grid(alpha=0.2)
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
    return saved_paths
