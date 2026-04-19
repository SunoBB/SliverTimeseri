from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from silver_timeseri.services.app_service import (
    get_economic_events,
    get_history,
    get_latest,
    get_model_forecasts,
    get_stationarity,
    get_summary,
    sync_incremental,
    sync_market_data,
)
from silver_timeseri.services.scheduler import start_scheduler, stop_scheduler

SERIES_LAYER_PATTERN = "^(raw|curated)$"


app = FastAPI(
    title="Metal Time Series API",
    description="API cho du lieu gia bac, thong ke va dong bo du lieu.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown() -> None:
    stop_scheduler()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/silver/latest")
def silver_latest(
    timeframe: str = Query(default="1d", pattern="^1d$"),
    series_layer: str = Query(default="curated", pattern=SERIES_LAYER_PATTERN),
) -> dict[str, object]:
    latest = get_latest(timeframe=timeframe, series_layer=series_layer)
    if latest is None:
        raise HTTPException(status_code=404, detail="No market data found in database.")
    return latest


@app.get("/silver/history")
def silver_history(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    timeframe: str = Query(default="1d", pattern="^1d$"),
    series_layer: str = Query(default="curated", pattern=SERIES_LAYER_PATTERN),
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int | None = Query(default=None, ge=0),
) -> dict[str, object]:
    return get_history(
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
        series_layer=series_layer,
        limit=limit,
        offset=offset,
    )


@app.get("/silver/summary")
def silver_summary(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    timeframe: str = Query(default="1d", pattern="^1d$"),
    series_layer: str = Query(default="curated", pattern=SERIES_LAYER_PATTERN),
) -> dict[str, object]:
    return get_summary(
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
        series_layer=series_layer,
    )


@app.get("/silver/events")
def silver_events(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    categories: str | None = Query(default=None),
    high_impact_only: bool = Query(default=False),
) -> dict[str, object]:
    parsed_categories = (
        [item.strip() for item in categories.split(",") if item.strip()]
        if categories
        else None
    )
    return get_economic_events(
        start_date=start_date,
        end_date=end_date,
        categories=parsed_categories,
        high_impact_only=high_impact_only,
    )


@app.get("/silver/stationarity")
def silver_stationarity(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    timeframe: str = Query(default="1d", pattern="^1d$"),
    series_layer: str = Query(default="curated", pattern=SERIES_LAYER_PATTERN),
) -> dict[str, object]:
    try:
        return get_stationarity(
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            series_layer=series_layer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/silver/models")
def silver_models(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    timeframe: str = Query(default="1d", pattern="^1d$"),
    series_layer: str = Query(default="curated", pattern=SERIES_LAYER_PATTERN),
    ar_order: int = Query(default=5, ge=1, le=20),
    ma_order: int = Query(default=3, ge=1, le=20),
    test_ratio: float = Query(default=0.2, gt=0.0, lt=1.0),
) -> dict[str, object]:
    try:
        return get_model_forecasts(
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            series_layer=series_layer,
            ar_order=ar_order,
            ma_order=ma_order,
            test_ratio=test_ratio,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/silver/sync/incremental")
def silver_sync_incremental(
    timeframe: str = Query(default="1d", pattern="^1d$"),
    force_refresh: bool = Query(default=True),
) -> dict[str, object]:
    try:
        return sync_incremental(timeframe=timeframe, force_refresh=force_refresh)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/silver/sync")
def silver_sync(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    timeframe: str = Query(default="1d", pattern="^1d$"),
    force_refresh: bool = Query(default=False),
) -> dict[str, object]:
    try:
        return sync_market_data(
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            force_refresh=force_refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
