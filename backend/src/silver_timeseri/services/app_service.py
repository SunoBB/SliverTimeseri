from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from silver_timeseri.analysis.metrics import build_stationarity_report, build_summary_metrics
from silver_timeseri.analysis.models import run_model_suite
from silver_timeseri.config import get_settings
from silver_timeseri.providers.alpha_vantage import AlphaVantageProvider
from silver_timeseri.services.pipeline import CURATED_LAYER, RAW_LAYER, SilverTimeSeriesPipeline
from silver_timeseri.services.storage import PostgresConfig, PostgresSilverRepository


def build_pipeline() -> SilverTimeSeriesPipeline:
    settings = get_settings()
    provider = AlphaVantageProvider(
        api_key=settings.alpha_vantage_api_key,
        base_url=settings.alpha_vantage_base_url,
        cache_dir=settings.raw_cache_dir,
        cache_ttl_hours=settings.raw_cache_ttl_hours,
    )
    return SilverTimeSeriesPipeline(provider)


def build_repository() -> PostgresSilverRepository:
    settings = get_settings()
    return PostgresSilverRepository(
        PostgresConfig(
            host=settings.postgres_host,
            port=settings.postgres_port,
            dbname=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            table_name=settings.postgres_table,
        )
    )


def sync_market_data(
    start_date: str | None = None,
    end_date: str | None = None,
    timeframe: str = "1d",
    force_refresh: bool = False,
) -> dict[str, object]:
    pipeline = build_pipeline()
    frames = pipeline.load_all_layers(
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
        force_refresh=force_refresh,
    )
    if all(frame.empty for frame in frames.values()):
        raise ValueError("No data returned from provider.")

    repository = build_repository()
    repository.ensure_schema()

    raw_frame = frames[RAW_LAYER]
    curated_frame = frames[CURATED_LAYER]

    # Prune stale curated rows that predate the first raw observation.
    # These have NULL prices (calendar fill before any real data) and
    # render as a flat-zero line at the start of every chart.
    # Only prune on full sync (start_date=None): in that case first_raw_ts
    # is the global earliest observation. For incremental syncs the cutoff
    # would be the start of the narrow window and would incorrectly delete
    # all valid historical curated rows (including filled weekend/holiday rows).
    pruned = 0
    if not raw_frame.empty and start_date is None:
        first_raw_ts = raw_frame.index.min().to_pydatetime()
        pruned = repository.prune_layer_before(
            series_layer=CURATED_LAYER,
            cutoff=first_raw_ts,
            timeframe=timeframe,
        )

    raw_rows = repository.upsert_market_data(raw_frame)
    curated_rows = repository.upsert_market_data(curated_frame)
    return {
        "table": get_settings().postgres_table,
        "rows_upserted": raw_rows + curated_rows,
        "rows_upserted_by_layer": {
            RAW_LAYER: raw_rows,
            CURATED_LAYER: curated_rows,
        },
        "rows_pruned_stale": pruned,
        "start_date": start_date,
        "end_date": end_date,
        "timeframe": timeframe,
        "force_refresh": force_refresh,
    }


def get_history(
    start_date: str | None = None,
    end_date: str | None = None,
    timeframe: str = "1d",
    series_layer: str = CURATED_LAYER,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, object]:
    repository = build_repository()
    total_rows = repository.count_history(
        symbol="XAGUSD",
        timeframe=timeframe,
        series_layer=series_layer,
        start_date=start_date,
        end_date=end_date,
    )
    frame = repository.fetch_history(
        symbol="XAGUSD",
        timeframe=timeframe,
        series_layer=series_layer,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    if frame.empty:
        return {"rows": 0, "total_rows": total_rows, "data": []}

    rows: list[dict[str, object]] = []
    for row in frame.itertuples(index=False):
        rows.append(
            {
                "symbol": row.symbol,
                "timeframe": row.timeframe,
                "series_layer": row.series_layer,
                "price_timestamp": row.price_timestamp.isoformat(),
                "source_date": row.source_date.isoformat() if not pd.isna(row.source_date) else None,
                "price_usd": float(row.price_usd) if row.price_usd is not None else None,
                "price_vnd": float(row.price_vnd) if row.price_vnd is not None else None,
                "price_silver_usd": float(row.price_silver_usd) if row.price_silver_usd is not None else None,
                "price_silver_vnd": float(row.price_silver_vnd) if row.price_silver_vnd is not None else None,
                "usd_vnd_rate": float(row.usd_vnd_rate) if row.usd_vnd_rate is not None else None,
                "is_imputed": bool(row.is_imputed),
                "is_weekend": bool(row.is_weekend),
                "is_missing_from_source": bool(row.is_missing_from_source),
            }
        )
    return {"rows": len(rows), "total_rows": total_rows, "data": rows}


def get_summary(
    start_date: str | None = None,
    end_date: str | None = None,
    timeframe: str = "1d",
    series_layer: str = CURATED_LAYER,
) -> dict[str, object]:
    repository = build_repository()
    frame = repository.fetch_history(
        symbol="XAGUSD",
        timeframe=timeframe,
        series_layer=series_layer,
        start_date=start_date,
        end_date=end_date,
    )
    if frame.empty:
        return {"rows": 0}

    dataset = frame.drop(columns=["created_at", "updated_at"]).rename(
        columns={"price_timestamp": "date"}
    )
    dataset = dataset.set_index("date")
    return build_summary_metrics(dataset)


def get_stationarity(
    start_date: str | None = None,
    end_date: str | None = None,
    timeframe: str = "1d",
    series_layer: str = CURATED_LAYER,
) -> dict[str, object]:
    repository = build_repository()
    frame = repository.fetch_history(
        symbol="XAGUSD",
        timeframe=timeframe,
        series_layer=series_layer,
        start_date=start_date,
        end_date=end_date,
    )
    if frame.empty:
        raise ValueError("No market data found in database for the selected date range.")

    dataset = frame.drop(columns=["created_at", "updated_at"]).rename(
        columns={"price_timestamp": "date"}
    )
    dataset = dataset.set_index("date").sort_index()
    dataset = dataset.dropna(subset=["price_usd"])
    if dataset.empty:
        raise ValueError("No non-null prices available for the selected date range.")

    report = build_stationarity_report(dataset, price_col="price_usd")
    return {
        "start_date": dataset.index.min().date().isoformat(),
        "end_date": dataset.index.max().date().isoformat(),
        "timeframe": timeframe,
        "series_layer": series_layer,
        **report,
    }


def get_model_forecasts(
    start_date: str | None = None,
    end_date: str | None = None,
    timeframe: str = "1d",
    series_layer: str = CURATED_LAYER,
    ar_order: int = 5,
    ma_order: int = 3,
    test_size: int = 20,
) -> dict[str, object]:
    if ar_order < 1:
        raise ValueError("ar_order must be >= 1.")
    if ma_order < 1:
        raise ValueError("ma_order must be >= 1.")
    if test_size < 3:
        raise ValueError("test_size must be >= 3.")

    repository = build_repository()
    frame = repository.fetch_history(
        symbol="XAGUSD",
        timeframe=timeframe,
        series_layer=series_layer,
        start_date=start_date,
        end_date=end_date,
    )
    if frame.empty:
        raise ValueError("No market data found in database for the selected date range.")

    dataset = frame.drop(columns=["created_at", "updated_at"]).rename(
        columns={"price_timestamp": "date"}
    )
    dataset = dataset.set_index("date").sort_index()
    dataset = dataset.dropna(subset=["price_usd"])
    if dataset.empty:
        raise ValueError("No non-null prices available in database for the selected date range.")

    results = run_model_suite(
        frame=dataset,
        ar_order=ar_order,
        ma_order=ma_order,
        test_size=test_size,
    )

    latest_row = dataset.iloc[-1]
    settings = get_settings()
    today_vn = datetime.now(settings.scheduler_tzinfo).date()
    tomorrow_vn = today_vn + timedelta(days=1)
    latest_data_date = dataset.index.max().date()
    next_dataset_date = latest_data_date + timedelta(days=1)
    missing_days = max((today_vn - latest_data_date).days, 0)
    forecast_target_type = "catch_up" if next_dataset_date <= today_vn else "tomorrow"
    forecast_target_label = (
        f"Bu ngay con thieu {next_dataset_date.isoformat()}"
        if forecast_target_type == "catch_up"
        else f"Du bao ngay mai {next_dataset_date.isoformat()}"
    )
    model_rows = [result.to_dict() for result in results]
    for row in model_rows:
        if row.get("next_forecast"):
            row["next_forecast"]["target_type"] = forecast_target_type
            row["next_forecast"]["display_label"] = forecast_target_label

    ranked_by_mae = sorted(
        model_rows,
        key=lambda row: _safe_metric_number(row.get("metrics", {}).get("mae"), default=float("inf")),
    )
    ranked_by_direction = sorted(
        model_rows,
        key=lambda row: (
            -_safe_metric_number(row.get("direction_backtest", {}).get("accuracy"), default=-1.0),
            _safe_metric_number(row.get("metrics", {}).get("mae"), default=float("inf")),
        ),
    )

    return {
        "rows": int(len(dataset)),
        "start_date": dataset.index.min().date().isoformat(),
        "end_date": dataset.index.max().date().isoformat(),
        "timeframe": timeframe,
        "series_layer": series_layer,
        "forecast_context": {
            "latest_data_date": latest_data_date.isoformat(),
            "current_vn_date": today_vn.isoformat(),
            "tomorrow_vn_date": tomorrow_vn.isoformat(),
            "next_dataset_date": next_dataset_date.isoformat(),
            "missing_days": missing_days,
            "latest_data_status": "stale" if latest_data_date < today_vn else "current",
            "forecast_target_type": forecast_target_type,
            "forecast_target_label": forecast_target_label,
        },
        "latest_actual": {
            "date": dataset.index.max().date().isoformat(),
            "price_usd": round(float(latest_row["price_usd"]), 6),
            "price_vnd": round(float(latest_row["price_vnd"]), 6)
            if latest_row.get("price_vnd") is not None
            else None,
        },
        "model_rankings": {
            "best_by_mae": ranked_by_mae[0]["model_name"] if ranked_by_mae else None,
            "best_by_direction": ranked_by_direction[0]["model_name"] if ranked_by_direction else None,
        },
        "models": model_rows,
    }


def get_latest(
    timeframe: str = "1d",
    series_layer: str = CURATED_LAYER,
) -> dict[str, object] | None:
    repository = build_repository()
    return repository.fetch_latest(symbol="XAGUSD", timeframe=timeframe, series_layer=series_layer)


def get_economic_events(
    start_date: str | None = None,
    end_date: str | None = None,
    categories: list[str] | None = None,
    high_impact_only: bool = False,
) -> dict[str, object]:
    repository = build_repository()
    repository.ensure_schema()
    impact_level = "high" if high_impact_only else None
    events = repository.fetch_economic_events(
        start_date=start_date,
        end_date=end_date,
        categories=categories,
        impact_level=impact_level,
    )
    available_categories = sorted({str(event["category"]) for event in events})
    return {
        "rows": len(events),
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "categories": categories or [],
            "high_impact_only": high_impact_only,
        },
        "available_categories": available_categories,
        "data": events,
    }


def sync_recent_market_data(
    timeframe: str = "1d",
    lookback_days: int = 7,
    force_refresh: bool = True,
) -> dict[str, object]:
    settings = get_settings()
    today_vn = datetime.now(settings.scheduler_tzinfo).date()
    latest = get_latest(timeframe=timeframe, series_layer=RAW_LAYER)

    if latest is None:
        return sync_market_data(timeframe=timeframe, force_refresh=force_refresh)

    latest_date = datetime.fromisoformat(str(latest["price_timestamp"])).date()
    start_date = min(latest_date, today_vn) - timedelta(days=lookback_days)
    return sync_market_data(
        start_date=start_date.isoformat(),
        end_date=today_vn.isoformat(),
        timeframe=timeframe,
        force_refresh=force_refresh,
    )


def morning_check_and_sync(timeframe: str = "1d") -> dict[str, object] | None:
    settings = get_settings()
    today_vn = datetime.now(settings.scheduler_tzinfo).date()
    latest = get_latest(timeframe=timeframe, series_layer=RAW_LAYER)

    if latest is None:
        return sync_market_data(timeframe=timeframe, force_refresh=True)

    latest_date = datetime.fromisoformat(str(latest["price_timestamp"])).date()
    if latest_date < today_vn:
        return sync_incremental(timeframe=timeframe, force_refresh=True)

    return None


def sync_incremental(
    timeframe: str = "1d",
    force_refresh: bool = True,
) -> dict[str, object]:
    """Sync from the latest raw date in DB up to yesterday (today - 1).

    This is the canonical incremental sync: it never re-fetches data that is
    already in the database and never reaches into today's not-yet-closed candle.
    """
    settings = get_settings()
    today_vn = datetime.now(settings.scheduler_tzinfo).date()
    yesterday_vn = today_vn - timedelta(days=1)

    latest = get_latest(timeframe=timeframe, series_layer=RAW_LAYER)

    if latest is None:
        # No data at all — full backfill up to yesterday
        return sync_market_data(
            end_date=yesterday_vn.isoformat(),
            timeframe=timeframe,
            force_refresh=force_refresh,
        )

    latest_date = datetime.fromisoformat(str(latest["price_timestamp"])).date()

    if latest_date >= yesterday_vn:
        return {
            "table": get_settings().postgres_table,
            "rows_upserted": 0,
            "rows_upserted_by_layer": {RAW_LAYER: 0, CURATED_LAYER: 0},
            "rows_pruned_stale": 0,
            "start_date": latest_date.isoformat(),
            "end_date": yesterday_vn.isoformat(),
            "timeframe": timeframe,
            "force_refresh": force_refresh,
            "skipped": True,
            "reason": "Data already up to date.",
        }

    return sync_market_data(
        start_date=latest_date.isoformat(),
        end_date=yesterday_vn.isoformat(),
        timeframe=timeframe,
        force_refresh=force_refresh,
    )


def _safe_metric_number(value: object, default: float) -> float:
    if value is None:
        return default
    return float(value)
