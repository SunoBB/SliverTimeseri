from __future__ import annotations

import argparse
import json
from pathlib import Path

from silver_timeseri.analysis.metrics import build_summary_metrics
from silver_timeseri.analysis.models import train_arma_model, train_arx_model, train_ma_model
from silver_timeseri.services.pipeline import CURATED_LAYER, RAW_LAYER
from silver_timeseri.services.app_service import build_pipeline, sync_incremental, sync_market_data
from tqdm import tqdm

_DEFAULT_ARIMA_ORDER = (1, 1, 1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze silver time series from Alpha Vantage.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--start-date", type=str, default=None)
    common.add_argument("--end-date", type=str, default=None)
    common.add_argument(
        "--timeframe",
        type=str,
        choices=["1d"],
        default="1d",
        help="Ban free hien tai chi ho tro du lieu daily (1d).",
    )
    common.add_argument(
        "--force-refresh",
        action="store_true",
        help="Bo qua cache local va goi lai provider truc tiep.",
    )
    common.add_argument(
        "--series-layer",
        type=str,
        choices=[RAW_LAYER, CURATED_LAYER],
        default=CURATED_LAYER,
        help="Chon lop du lieu: raw trading series hoac curated daily series.",
    )

    subparsers.add_parser("summarize", parents=[common])

    export_parser = subparsers.add_parser("export", parents=[common])
    export_parser.add_argument("--output", type=Path, required=True)

    subparsers.add_parser("sync-db", parents=[common])

    sync_inc_parser = subparsers.add_parser(
        "sync-incremental",
        help="Sync from the latest raw date in DB up to yesterday (today - 1).",
    )
    sync_inc_parser.add_argument(
        "--timeframe",
        type=str,
        choices=["1d"],
        default="1d",
    )
    sync_inc_parser.add_argument(
        "--force-refresh",
        action="store_true",
        default=True,
    )

    charts_parser = subparsers.add_parser("charts", parents=[common])
    charts_parser.add_argument("--input-csv", type=Path, default=None)
    charts_parser.add_argument("--output-dir", type=Path, default=Path("outputs/charts"))
    charts_parser.add_argument("--date-column", type=str, default="date")
    charts_parser.add_argument("--value-column", type=str, default="price_usd")
    charts_parser.add_argument("--ma-window", type=int, default=7)
    charts_parser.add_argument("--volatility-window", type=int, default=30)
    charts_parser.add_argument("--aggregation-rule", type=str, default="W")
    charts_parser.add_argument("--bins", type=int, default=10)
    charts_parser.add_argument("--lag", type=int, default=1)

    model_parser = subparsers.add_parser("model", parents=[common])
    model_parser.add_argument(
        "--model-type",
        choices=["ar", "ma", "arma", "all"],
        default="all",
    )
    model_parser.add_argument("--ar-order", type=int, default=5)
    model_parser.add_argument("--ma-order", type=int, default=3)
    model_parser.add_argument("--test-size", type=int, default=20)

    academic_parser = subparsers.add_parser(
        "academic",
        parents=[common],
        help="Chạy toàn bộ luồng phân tích học thuật: resample monthly → ADF → decompose → 6 mô hình → so sánh → forecast.",
    )
    academic_parser.add_argument("--output-dir", type=Path, default=Path("outputs/charts"))
    academic_parser.add_argument("--test-size", type=int, default=12,
                                  help="Số tháng cuối dùng làm tập test (mặc định: 12).")
    academic_parser.add_argument("--arima-p", type=int, default=1)
    academic_parser.add_argument("--arima-d", type=int, default=1)
    academic_parser.add_argument("--arima-q", type=int, default=1)
    academic_parser.add_argument("--n-months-forecast", type=int, default=12,
                                  help="Số tháng dự báo tương lai (mặc định: 12).")

    return parser


def command_summarize(
    start_date: str | None,
    end_date: str | None,
    timeframe: str,
    force_refresh: bool,
    series_layer: str,
) -> int:
    pipeline = build_pipeline()
    frame = pipeline.load(
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
        force_refresh=force_refresh,
        series_layer=series_layer,
    )
    print(json.dumps(build_summary_metrics(frame), indent=2))
    return 0


def command_export(
    start_date: str | None,
    end_date: str | None,
    timeframe: str,
    output: Path,
    force_refresh: bool,
    series_layer: str,
) -> int:
    pipeline = build_pipeline()
    frame = pipeline.load(
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
        force_refresh=force_refresh,
        series_layer=series_layer,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    export_frame = frame.reset_index()
    if output.suffix.lower() == ".xlsx":
        try:
            export_frame.to_excel(output, index=False)
        except ModuleNotFoundError as exc:
            raise ValueError(
                "Excel export requires openpyxl. Install dependencies with 'pip install -r backend/requirements.txt'."
            ) from exc
    else:
        export_frame.to_csv(output, index=False)
    print(f"Exported {len(frame)} rows to {output}")
    return 0


def command_model(
    start_date: str | None,
    end_date: str | None,
    timeframe: str,
    series_layer: str,
    model_type: str,
    ar_order: int,
    ma_order: int,
    test_size: int,
    force_refresh: bool,
) -> int:
    if ar_order < 1:
        raise ValueError("ar-order must be >= 1.")
    if ma_order < 1:
        raise ValueError("ma-order must be >= 1.")
    if test_size < 1:
        raise ValueError("test-size must be >= 1.")

    pipeline = build_pipeline()
    frame = pipeline.load(
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
        force_refresh=force_refresh,
        series_layer=series_layer,
    )
    if frame.empty:
        raise ValueError("No data returned from provider.")

    if model_type == "ar":
        results = [train_arx_model(frame=frame, ar_order=ar_order, test_size=test_size)]
    elif model_type == "ma":
        results = [train_ma_model(frame=frame, ma_order=ma_order, test_size=test_size)]
    elif model_type == "arma":
        results = [
            train_arma_model(
                frame=frame,
                ar_order=ar_order,
                ma_order=ma_order,
                test_size=test_size,
            )
        ]
    else:
        trainers = [
            ("ARX", lambda: train_arx_model(frame=frame, ar_order=ar_order, test_size=test_size)),
            ("MA", lambda: train_ma_model(frame=frame, ma_order=ma_order, test_size=test_size)),
            (
                "ARMA",
                lambda: train_arma_model(
                    frame=frame,
                    ar_order=ar_order,
                    ma_order=ma_order,
                    test_size=test_size,
                ),
            ),
        ]
        results = []
        for _, trainer in tqdm(trainers, desc="Training models", unit="model"):
            results.append(trainer())

    print(json.dumps([result.to_dict() for result in results], indent=2))
    return 0


def command_charts(
    start_date: str | None,
    end_date: str | None,
    timeframe: str,
    force_refresh: bool,
    series_layer: str,
    input_csv: Path | None,
    output_dir: Path,
    date_column: str,
    value_column: str,
    ma_window: int,
    volatility_window: int,
    aggregation_rule: str,
    bins: int,
    lag: int,
) -> int:
    try:
        from silver_timeseri.analysis.visualization import load_frame_from_csv, save_time_series_charts
    except ModuleNotFoundError as exc:
        raise ValueError(
            "Charts command requires matplotlib. Install dependencies with 'pip install -r backend/requirements.txt'."
        ) from exc

    if input_csv is not None:
        frame = load_frame_from_csv(
            input_csv,
            date_column=date_column,
            value_column=value_column,
        )
    else:
        pipeline = build_pipeline()
        frame = pipeline.load(
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            force_refresh=force_refresh,
            series_layer=series_layer,
        )

    date_subdir = f"{frame.index.min():%Y-%m}_{frame.index.max():%Y-%m}"
    output_dir = output_dir / date_subdir

    saved_paths = save_time_series_charts(
        frame,
        value_column=value_column,
        output_dir=output_dir,
        moving_average_window=ma_window,
        volatility_window=volatility_window,
        aggregation_rule=aggregation_rule,
        histogram_bins=bins,
        lag=lag,
    )
    print(json.dumps({"saved_files": [str(path) for path in saved_paths]}, indent=2))
    return 0


def command_academic(
    start_date: str | None,
    end_date: str | None,
    timeframe: str,
    series_layer: str,
    force_refresh: bool,
    output_dir: Path,
    test_size: int,
    arima_order: tuple[int, int, int],
    n_months_forecast: int,
) -> int:
    """Thực thi toàn bộ luồng phân tích học thuật theo roadmap CLAUDE.md."""
    from silver_timeseri.analysis.features import build_decomposition_report, build_monthly_series
    from silver_timeseri.analysis.metrics import build_comparison_table, build_stationarity_report
    from silver_timeseri.analysis.models import forecast_future_months, run_academic_suite
    from silver_timeseri.analysis.visualization import (
        save_acf_pacf_chart,
        save_decomposition_charts,
        save_forecast_comparison_chart,
        save_future_forecast_chart,
        save_stationarity_chart,
    )

    pipeline = build_pipeline()
    frame = pipeline.load(
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
        force_refresh=force_refresh,
        series_layer=series_layer,
    )
    if frame.empty:
        raise ValueError("Không có dữ liệu. Chạy 'sync-db' trước hoặc kiểm tra kết nối.")

    # BƯỚC 1 — Resample daily → monthly
    monthly = build_monthly_series(frame)
    n_monthly = len(monthly)

    date_subdir = f"{monthly.index.min():%Y-%m}_{monthly.index.max():%Y-%m}"
    output_dir = output_dir / date_subdir

    # BƯỚC 2 — EDA (charts đã có từ lệnh 'charts'; ở đây tạo ACF/PACF)
    print(f"[1/5] Resample xong: {n_monthly} tháng quan sát.", flush=True)
    acf_path = save_acf_pacf_chart(monthly["price_usd"], output_dir)
    print(f"      → {acf_path}", flush=True)

    # BƯỚC 3 — Kiểm định tính ổn định (ADF) trên chuỗi monthly
    stationarity = build_stationarity_report(monthly)
    stationarity_path = save_stationarity_chart(monthly["price_usd"], stationarity, output_dir)
    print(
        f"[2/5] ADF: {stationarity['conclusion']['summary']} "
        f"(d đề xuất = {stationarity['conclusion']['d_recommended']})",
        flush=True,
    )
    print(f"      → {stationarity_path}", flush=True)

    # BƯỚC 4 — Phân rã chuỗi
    decomp_report = build_decomposition_report(monthly)
    decomp_paths = save_decomposition_charts(monthly["price_usd"], output_dir)
    recommended_decomp = decomp_report.get("recommended_model", "?")
    print(f"[3/5] Phân rã: mô hình được chọn = {recommended_decomp}", flush=True)
    for p in decomp_paths:
        print(f"      → {p}", flush=True)

    # BƯỚC 5 — Huấn luyện 6 mô hình
    print(f"[4/5] Huấn luyện 6 mô hình (test_size={test_size} tháng)…", flush=True)
    results = run_academic_suite(monthly, test_size=test_size, arima_order=arima_order)
    results_dicts = [r.to_dict() for r in results]
    comparison = build_comparison_table(results_dicts)
    best_model = comparison[0]["model"] if comparison else "ARIMA(1, 1, 1)"

    comparison_path = save_forecast_comparison_chart(monthly["price_usd"], results_dicts, output_dir)
    print(f"      → {comparison_path}", flush=True)

    # BƯỚC 6 — Dự báo tương lai bằng mô hình tốt nhất
    future = forecast_future_months(monthly, best_model, n_months=n_months_forecast, arima_order=arima_order)
    future_path = save_future_forecast_chart(monthly["price_usd"], future, output_dir)
    print(
        f"[5/5] Dự báo {n_months_forecast} tháng tới bằng {best_model} → {future_path}",
        flush=True,
    )

    report = {
        "n_monthly_obs": n_monthly,
        "test_size": test_size,
        "stationarity": stationarity,
        "decomposition": decomp_report,
        "comparison_table": comparison,
        "best_model": best_model,
        "future_forecast": future,
        "charts_saved": [
            str(acf_path),
            str(stationarity_path),
            *[str(p) for p in decomp_paths],
            str(comparison_path),
            str(future_path),
        ],
    }
    print(json.dumps(report, indent=2))
    return 0


def command_sync_db(
    start_date: str | None,
    end_date: str | None,
    timeframe: str,
    force_refresh: bool,
) -> int:
    print(
        json.dumps(
            sync_market_data(
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
                force_refresh=force_refresh,
            ),
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "summarize":
            return command_summarize(
                start_date=args.start_date,
                end_date=args.end_date,
                timeframe=args.timeframe,
                force_refresh=args.force_refresh,
                series_layer=args.series_layer,
            )
        if args.command == "export":
            return command_export(
                start_date=args.start_date,
                end_date=args.end_date,
                timeframe=args.timeframe,
                output=args.output,
                force_refresh=args.force_refresh,
                series_layer=args.series_layer,
            )
        if args.command == "sync-db":
            return command_sync_db(
                start_date=args.start_date,
                end_date=args.end_date,
                timeframe=args.timeframe,
                force_refresh=args.force_refresh,
            )
        if args.command == "sync-incremental":
            print(
                json.dumps(
                    sync_incremental(
                        timeframe=args.timeframe,
                        force_refresh=args.force_refresh,
                    ),
                    indent=2,
                )
            )
            return 0
        if args.command == "charts":
            return command_charts(
                start_date=args.start_date,
                end_date=args.end_date,
                timeframe=args.timeframe,
                force_refresh=args.force_refresh,
                series_layer=args.series_layer,
                input_csv=args.input_csv,
                output_dir=args.output_dir,
                date_column=args.date_column,
                value_column=args.value_column,
                ma_window=args.ma_window,
                volatility_window=args.volatility_window,
                aggregation_rule=args.aggregation_rule,
                bins=args.bins,
                lag=args.lag,
            )
        if args.command == "model":
            return command_model(
                start_date=args.start_date,
                end_date=args.end_date,
                timeframe=args.timeframe,
                series_layer=args.series_layer,
                model_type=args.model_type,
                ar_order=args.ar_order,
                ma_order=args.ma_order,
                test_size=args.test_size,
                force_refresh=args.force_refresh,
            )
        if args.command == "academic":
            return command_academic(
                start_date=args.start_date,
                end_date=args.end_date,
                timeframe=args.timeframe,
                series_layer=args.series_layer,
                force_refresh=args.force_refresh,
                output_dir=args.output_dir,
                test_size=args.test_size,
                arima_order=(args.arima_p, args.arima_d, args.arima_q),
                n_months_forecast=args.n_months_forecast,
            )
    except ValueError as exc:
        parser.exit(status=1, message=f"Error: {exc}\n")

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
