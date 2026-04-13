from __future__ import annotations

import argparse
import json
from pathlib import Path

from silver_timeseri.analysis.metrics import build_summary_metrics
from silver_timeseri.analysis.models import train_arma_model, train_arx_model, train_ma_model
from silver_timeseri.services.pipeline import CURATED_LAYER, RAW_LAYER
from silver_timeseri.services.app_service import build_pipeline, sync_incremental, sync_market_data
from tqdm import tqdm


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

    saved_paths = save_time_series_charts(
        frame,
        value_column=value_column,
        output_dir=output_dir,
        moving_average_window=ma_window,
        aggregation_rule=aggregation_rule,
        histogram_bins=bins,
        lag=lag,
    )
    print(json.dumps({"saved_files": [str(path) for path in saved_paths]}, indent=2))
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
    except ValueError as exc:
        parser.exit(status=1, message=f"Error: {exc}\n")

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
