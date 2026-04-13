from __future__ import annotations

import pandas as pd

from silver_timeseri.providers.alpha_vantage import AlphaVantageProvider
from silver_timeseri.providers.base import MarketDataProvider

OUNCE_TO_GRAM = 31.1035
LUONG_TO_GRAM = 37.5
OUNCE_TO_LUONG_RATIO = LUONG_TO_GRAM / OUNCE_TO_GRAM
RAW_LAYER = "raw"
CURATED_LAYER = "curated"
SUPPORTED_SERIES_LAYERS = {RAW_LAYER, CURATED_LAYER}


class SilverTimeSeriesPipeline:
    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    def load(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        timeframe: str = "1d",
        force_refresh: bool = False,
        series_layer: str = CURATED_LAYER,
    ) -> pd.DataFrame:
        if series_layer == RAW_LAYER:
            return self.load_raw(
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
                force_refresh=force_refresh,
            )
        if series_layer == CURATED_LAYER:
            return self.load_curated(
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
                force_refresh=force_refresh,
            )
        raise ValueError(f"Unsupported series_layer: {series_layer}")

    def load_raw(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        timeframe: str = "1d",
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        records = self.provider.fetch_silver_history(
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            force_refresh=force_refresh,
        )
        frame = pd.DataFrame.from_records(records)
        if frame.empty:
            return self._empty_frame(series_layer=RAW_LAYER, timeframe=timeframe)

        frame["date"] = pd.to_datetime(frame["date"], utc=False).dt.normalize()
        frame = frame.sort_values("date").set_index("date")
        frame["price_usd"] = pd.to_numeric(frame["price_usd"], errors="coerce")
        frame["price_silver_usd"] = pd.to_numeric(
            frame["price_silver_usd"],
            errors="coerce",
        )
        frame = frame.dropna(subset=["price_usd"])
        frame = self._attach_fx_rates(
            frame=frame,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            force_refresh=force_refresh,
        )
        frame["source_date"] = frame.index
        frame["is_missing_from_source"] = False
        frame["is_imputed"] = False
        frame["is_weekend"] = frame.index.dayofweek >= 5
        return self._finalize_frame(frame=frame, timeframe=timeframe, series_layer=RAW_LAYER)

    def load_curated(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        timeframe: str = "1d",
        force_refresh: bool = False,
        _raw: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        raw = _raw if _raw is not None else self.load_raw(
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            force_refresh=force_refresh,
        )
        if raw.empty:
            return self._empty_frame(series_layer=CURATED_LAYER, timeframe=timeframe)

        full_index = self._build_daily_index(raw.index, start_date=start_date, end_date=end_date)
        curated = raw.reindex(full_index)
        curated.index.name = "date"
        source_mask = curated.index.isin(raw.index)
        curated["is_missing_from_source"] = ~source_mask
        curated["is_weekend"] = curated.index.dayofweek >= 5
        curated["source_date"] = pd.Series(
            pd.NaT,
            index=curated.index,
            dtype="datetime64[ns]",
        )
        curated.loc[source_mask, "source_date"] = curated.index[source_mask]

        columns_to_ffill = ["price_usd", "price_silver_usd", "usd_vnd_rate", "source_date"]
        curated[columns_to_ffill] = curated[columns_to_ffill].ffill()
        curated["is_imputed"] = curated["is_missing_from_source"] & curated["price_usd"].notna()

        return self._finalize_frame(frame=curated, timeframe=timeframe, series_layer=CURATED_LAYER)

    def load_all_layers(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        timeframe: str = "1d",
        force_refresh: bool = False,
    ) -> dict[str, pd.DataFrame]:
        # Load raw once, reuse it for curated to avoid double API/cache read
        raw = self.load_raw(
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            force_refresh=force_refresh,
        )
        curated = self.load_curated(
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            _raw=raw,
        )
        return {RAW_LAYER: raw, CURATED_LAYER: curated}

    def _attach_fx_rates(
        self,
        frame: pd.DataFrame,
        start_date: str | None,
        end_date: str | None,
        timeframe: str,
        force_refresh: bool,
    ) -> pd.DataFrame:
        dataset = frame.copy()
        if isinstance(self.provider, AlphaVantageProvider):
            fx_records = self.provider.fetch_usd_vnd_history(
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
                force_refresh=force_refresh,
            )
            fx_frame = pd.DataFrame.from_records(fx_records)
            if not fx_frame.empty:
                fx_frame["date"] = pd.to_datetime(fx_frame["date"], utc=False).dt.normalize()
                fx_frame = fx_frame.sort_values("date").set_index("date")
                fx_frame["usd_vnd_rate"] = pd.to_numeric(
                    fx_frame["usd_vnd_rate"],
                    errors="coerce",
                )
                dataset = dataset.join(fx_frame[["usd_vnd_rate"]], how="left")
                dataset["usd_vnd_rate"] = dataset["usd_vnd_rate"].ffill().bfill()

        if "usd_vnd_rate" not in dataset.columns:
            dataset["usd_vnd_rate"] = pd.NA
        return dataset

    def _finalize_frame(
        self,
        frame: pd.DataFrame,
        timeframe: str,
        series_layer: str,
    ) -> pd.DataFrame:
        dataset = frame.sort_index().copy()
        dataset.index = pd.to_datetime(dataset.index, utc=False).normalize()
        dataset.index.name = "date"
        dataset["price_usd"] = pd.to_numeric(dataset["price_usd"], errors="coerce")
        dataset["price_silver_usd"] = pd.to_numeric(dataset["price_silver_usd"], errors="coerce")
        dataset["usd_vnd_rate"] = pd.to_numeric(dataset["usd_vnd_rate"], errors="coerce")

        # Alpha Vantage trả bạc theo USD/ounce, trong khi thị trường Việt Nam
        # thường dùng VND/lượng. Vì vậy cần quy đổi từ ounce sang lượng.
        dataset["price_vnd"] = dataset["price_usd"] * dataset["usd_vnd_rate"] * OUNCE_TO_LUONG_RATIO
        dataset["price_silver_vnd"] = (
            dataset["price_silver_usd"] * dataset["usd_vnd_rate"] * OUNCE_TO_LUONG_RATIO
        )
        dataset["symbol"] = "XAGUSD"
        dataset["timeframe"] = timeframe
        dataset["series_layer"] = series_layer
        dataset["source_date"] = pd.to_datetime(dataset["source_date"], errors="coerce")
        dataset["is_missing_from_source"] = dataset["is_missing_from_source"].fillna(False).astype(bool)
        dataset["is_imputed"] = dataset["is_imputed"].fillna(False).astype(bool)
        dataset["is_weekend"] = dataset["is_weekend"].fillna(False).astype(bool)
        return dataset

    @staticmethod
    def _build_daily_index(
        observed_index: pd.Index,
        start_date: str | None,
        end_date: str | None,
    ) -> pd.DatetimeIndex:
        observed_start = pd.Timestamp(observed_index.min()).normalize()
        requested_start = (
            pd.Timestamp(start_date).normalize()
            if start_date is not None
            else observed_start
        )
        range_start = max(requested_start, observed_start)
        range_end = (
            pd.Timestamp(end_date).normalize()
            if end_date is not None
            else pd.Timestamp(observed_index.max()).normalize()
        )
        if range_end < range_start:
            raise ValueError("end_date must be greater than or equal to start_date.")
        return pd.date_range(start=range_start, end=range_end, freq="D", name="date")

    @staticmethod
    def _empty_frame(series_layer: str, timeframe: str) -> pd.DataFrame:
        return pd.DataFrame(
            columns=[
                "price_usd",
                "price_silver_usd",
                "usd_vnd_rate",
                "price_vnd",
                "price_silver_vnd",
                "symbol",
                "timeframe",
                "series_layer",
                "source_date",
                "is_missing_from_source",
                "is_imputed",
                "is_weekend",
            ]
        ).assign(
            symbol="XAGUSD",
            timeframe=timeframe,
            series_layer=series_layer,
        )
