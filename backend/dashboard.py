from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

from silver_timeseri.analysis.visualization import CHART_TITLES, save_time_series_charts


API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_CHARTS_OUTPUT_DIR = Path("outputs/charts")
CLI_CHART_FILES = [
    ("01_line_plot.png", CHART_TITLES["line"]),
    ("02_moving_average.png", CHART_TITLES["moving_average"]),
    ("03_aggregation.png", CHART_TITLES["aggregation"]),
    ("04_boxplot.png", CHART_TITLES["boxplot"]),
    ("05_histogram.png", CHART_TITLES["histogram"]),
    ("06_density.png", CHART_TITLES["density"]),
    ("07_autocorrelation.png", CHART_TITLES["autocorrelation"]),
    ("08_lag_plot.png", CHART_TITLES["lag"]),
    ("09_full_combo.png", CHART_TITLES["combo"]),
]


def build_timeline_chart(frame: pd.DataFrame, *, value_column: str, title: str, yaxis_title: str) -> go.Figure:
    chart_frame = frame[["price_timestamp", value_column]].copy()
    chart_frame["ma_7"] = chart_frame[value_column].rolling(window=7).mean()
    start_value = float(chart_frame[value_column].iloc[0])
    end_value = float(chart_frame[value_column].iloc[-1])
    pct_change = ((end_value - start_value) / start_value) * 100
    subtitle = (
        f"{chart_frame['price_timestamp'].min():%b %Y} to {chart_frame['price_timestamp'].max():%b %Y}"
        f" | Start: {start_value:,.2f} | End: {end_value:,.2f} | {pct_change:+.1f}%"
    )

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=chart_frame["price_timestamp"],
            y=chart_frame[value_column],
            mode="lines",
            name="Original",
            line={"color": "#1d4ed8", "width": 2},
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:,.2f}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=chart_frame["price_timestamp"],
            y=chart_frame["ma_7"],
            mode="lines",
            name="MA 7",
            line={"color": "#ea580c", "width": 2.5},
            hovertemplate="%{x|%d/%m/%Y}<br>MA 7: %{y:,.2f}<extra></extra>",
        )
    )
    figure.update_layout(
        title={"text": f"{title}<br><sup>{subtitle}</sup>", "x": 0},
        yaxis_title=yaxis_title,
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.14, "x": 0},
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
    )
    figure.update_xaxes(
        title=None,
        rangeslider_visible=True,
        showgrid=False,
        tickformat="%b %Y",
    )
    figure.update_yaxes(showgrid=True, gridcolor="rgba(148, 163, 184, 0.25)")
    return figure


def prepare_cli_chart_frame(frame: pd.DataFrame) -> pd.DataFrame:
    chart_frame = frame.rename(columns={"price_timestamp": "date"}).copy()
    chart_frame["date"] = pd.to_datetime(chart_frame["date"], errors="coerce")
    chart_frame = chart_frame.dropna(subset=["date"]).set_index("date").sort_index()
    return chart_frame


def render_cli_chart_gallery(output_dir: Path) -> None:
    existing_files = [(filename, title) for filename, title in CLI_CHART_FILES if (output_dir / filename).exists()]
    if not existing_files:
        st.info("Chua co anh chart CLI trong thu muc da chon.")
        return

    for filename, title in existing_files:
        image_path = output_dir / filename
        st.markdown(f"**{title}**")
        st.caption(str(image_path))
        st.image(str(image_path), use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="Silver Dashboard", layout="wide")
    st.title("Silver Time Series Dashboard")

    with st.sidebar:
        st.header("Bo loc")
        start_date = st.date_input("Start date", value=date.today() - timedelta(days=365))
        end_date = st.date_input("End date", value=date.today())
        api_base_url = st.text_input("API base URL", value=API_BASE_URL)
        charts_output_dir = Path(
            st.text_input("CLI charts output dir", value=str(DEFAULT_CHARTS_OUTPUT_DIR))
        )
        ma_window = st.number_input("MA window", min_value=2, value=7, step=1)
        aggregation_rule = st.text_input("Aggregation rule", value="W")
        bins = st.number_input("Histogram bins", min_value=1, value=10, step=1)
        lag = st.number_input("Lag", min_value=1, value=1, step=1)

        if st.button("Sync du lieu"):
            sync_result = call_api(
                api_base_url,
                "/silver/sync",
                params={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "timeframe": "1d",
                },
                method="POST",
            )
            st.json(sync_result)

    summary = call_api(
        api_base_url,
        "/silver/summary",
        params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timeframe": "1d",
        },
    )
    history = call_api(
        api_base_url,
        "/silver/history",
        params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timeframe": "1d",
        },
    )

    if not history["data"]:
        st.warning("Chua co du lieu trong database. Hay bam 'Sync du lieu' truoc.")
        return

    frame = pd.DataFrame(history["data"])
    frame["price_timestamp"] = pd.to_datetime(frame["price_timestamp"])

    col1, col2, col3 = st.columns(3)
    col1.metric("Rows", summary.get("rows", 0))
    col2.metric("Gia bac USD", f'{summary.get("end_price_usd", 0):,.2f}')
    col3.metric("Gia bac VND/luong", f'{summary.get("end_price_vnd", 0):,.0f}')

    st.subheader("Tong quan")
    st.json(summary)

    st.subheader("Bieu do gia bac")
    silver_usd_chart = build_timeline_chart(
        frame,
        value_column="price_usd",
        title="Gia bac theo USD/ounce",
        yaxis_title="USD/ounce",
    )
    st.plotly_chart(silver_usd_chart, use_container_width=True)

    silver_vnd_chart = build_timeline_chart(
        frame,
        value_column="price_vnd",
        title="Gia bac theo VND/luong",
        yaxis_title="VND/luong",
    )
    st.plotly_chart(silver_vnd_chart, use_container_width=True)

    st.subheader("Anh chart khop voi CLI")
    st.caption(
        "Khu nay dung chung logic voi lenh `PYTHONPATH=backend/src python3 -m silver_timeseri.cli charts`."
    )

    cli_chart_frame = prepare_cli_chart_frame(frame)
    if st.button("Tao / cap nhat anh chart CLI"):
        try:
            saved_paths = save_time_series_charts(
                cli_chart_frame,
                value_column="price_usd",
                output_dir=charts_output_dir,
                moving_average_window=int(ma_window),
                aggregation_rule=aggregation_rule,
                histogram_bins=int(bins),
                lag=int(lag),
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success(f"Da tao {len(saved_paths)} file trong {charts_output_dir}.")

    render_cli_chart_gallery(charts_output_dir)

    st.subheader("Bang du lieu")
    st.dataframe(frame, use_container_width=True)


def call_api(
    base_url: str,
    path: str,
    params: dict[str, str],
    method: str = "GET",
) -> dict[str, object]:
    response = requests.request(method, f"{base_url}{path}", params=params, timeout=60)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    main()
