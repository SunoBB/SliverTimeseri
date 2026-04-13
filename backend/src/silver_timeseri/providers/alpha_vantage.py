from __future__ import annotations

import json
from datetime import date
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from tqdm import tqdm

from silver_timeseri.providers.base import MarketDataProvider


class AlphaVantageProvider(MarketDataProvider):
    """Provider lấy dữ liệu giá bạc từ Alpha Vantage.

    Cách sử dụng:
    1. Khởi tạo provider với `api_key` và `base_url`.
    2. Gọi `fetch_silver_history(start_date, end_date)` để lấy dữ liệu lịch sử.
    3. Kết quả trả về là danh sách dict, mỗi dòng gồm:
       - `date`: ngày giao dịch
       - `price_usd`: giá bạc theo USD
       - `price_silver_usd`: giá bạc theo USD

    Vì sao dùng lớp này:
    - Tách riêng phần gọi API khỏi phần xử lý và phân tích dữ liệu.
    - Dễ thay thế sang nguồn dữ liệu khác mà không phải sửa pipeline phía sau.
    - Có chuẩn hóa dữ liệu đầu ra để các bước phân tích dùng thống nhất.
    - Có xử lý các lỗi phổ biến như lỗi mạng, JSON sai định dạng, hoặc API thiếu dữ liệu.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: int = 30,
        cache_dir: Path | None = None,
        cache_ttl_hours: int = 24,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.cache_dir = cache_dir or Path("data/raw/alpha_vantage")
        self.cache_ttl_hours = cache_ttl_hours

    def fetch_silver_history(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        timeframe: str = "1d",
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        if timeframe != "1d":
            raise ValueError(
                "Ban free hien tai chi ho tro timeframe=1d. "
                "Alpha Vantage khong cung cap luong intraday phu hop cho spot silver trong implementation nay."
            )

        silver_rows: list[dict[str, Any]] = []
        for symbol in tqdm(["SILVER"], desc="Fetching Alpha Vantage data", unit="symbol"):
            silver_rows = self._fetch_symbol_history(
                symbol=symbol,
                interval="daily",
                force_refresh=force_refresh,
            )

        rows = []
        for item in silver_rows:
            item_date = item.get("date")
            if not item_date:
                continue

            # Lọc dữ liệu theo khoảng ngày nếu người dùng truyền vào.
            if start_date and item_date < start_date:
                continue
            if end_date and item_date > end_date:
                continue

            rows.append(
                {
                    "date": item_date,
                    "price_usd": self._coerce_number(item.get("price")),
                    "price_silver_usd": self._coerce_number(item.get("price")),
                }
            )

        rows.sort(key=lambda row: row["date"])
        return rows

    def fetch_usd_vnd_history(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        timeframe: str = "1d",
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        if timeframe == "1d":
            payload = self._fetch_fx_history(
                function="FX_DAILY",
                from_symbol="USD",
                to_symbol="VND",
                outputsize="full",
                force_refresh=force_refresh,
            )
            time_series_key = "Time Series FX (Daily)"
        else:
            payload = self._fetch_fx_history(
                function="FX_INTRADAY",
                from_symbol="USD",
                to_symbol="VND",
                outputsize="full",
                interval=timeframe,
                force_refresh=force_refresh,
            )
            time_series_key = f"Time Series FX ({timeframe})"

        time_series = payload.get(time_series_key)
        if not isinstance(time_series, dict):
            raise ValueError("Alpha Vantage returned malformed FX history.")

        rows = []
        for item_date, values in time_series.items():
            if start_date and item_date < start_date:
                continue
            if end_date and item_date > end_date:
                continue

            rows.append(
                {
                    "date": item_date,
                    "usd_vnd_rate": self._coerce_number(values.get("4. close")),
                }
            )

        rows.sort(key=lambda row: row["date"])
        return rows

    def _fetch_symbol_history(
        self,
        symbol: str,
        interval: str,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        # Alpha Vantage yêu cầu truyền rõ kim loại (`symbol`) và tần suất (`interval`).
        cache_key = f"commodity_{symbol.lower()}_{interval}.json"
        cached_payload = None if force_refresh else self._read_cache(cache_key)
        if cached_payload is not None:
            payload = cached_payload
        else:
            payload = self._request_json(
                params={
                    "function": "GOLD_SILVER_HISTORY",
                    "symbol": symbol,
                    "interval": interval,
                    "apikey": self.api_key,
                },
                network_error_message="Could not reach Alpha Vantage API.",
                invalid_json_message="Alpha Vantage returned invalid JSON.",
            )
            self._write_cache(cache_key, payload)

        if "data" not in payload:
            message = payload.get("Information") or payload.get("Note") or payload
            raise ValueError(f"Alpha Vantage response missing data: {message}")
        if not isinstance(payload["data"], list):
            raise ValueError("Alpha Vantage returned malformed historical data.")
        return payload["data"]

    def _fetch_fx_history(
        self,
        function: str,
        from_symbol: str,
        to_symbol: str,
        outputsize: str,
        interval: str | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        cache_suffix = interval or "daily"
        cache_key = f"fx_{from_symbol.lower()}_{to_symbol.lower()}_{cache_suffix}.json"
        cached_payload = None if force_refresh else self._read_cache(cache_key)
        if cached_payload is not None:
            payload = cached_payload
        else:
            params = {
                "function": function,
                "from_symbol": from_symbol,
                "to_symbol": to_symbol,
                "outputsize": outputsize,
                "apikey": self.api_key,
            }
            if interval:
                params["interval"] = interval
            payload = self._request_json(
                params=params,
                network_error_message="Could not reach Alpha Vantage FX API.",
                invalid_json_message="Alpha Vantage returned invalid FX JSON.",
            )
            self._write_cache(cache_key, payload)

        if not any(key.startswith("Time Series FX") for key in payload):
            message = payload.get("Information") or payload.get("Note") or payload
            raise ValueError(f"Alpha Vantage FX response missing data: {message}")
        return payload

    def _request_json(
        self,
        params: dict[str, Any],
        network_error_message: str,
        invalid_json_message: str,
    ) -> dict[str, Any]:
        params = {
            key: value
            for key, value in params.items()
            if value is not None
        }
        try:
            response = requests.get(
                self.base_url,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ValueError(network_error_message) from exc

        try:
            return response.json()
        except ValueError as exc:
            raise ValueError(invalid_json_message) from exc

    def _read_cache(self, cache_key: str) -> dict[str, Any] | None:
        cache_path = self.cache_dir / cache_key
        if not cache_path.exists():
            return None
        if not self._is_cache_fresh(cache_path):
            return None
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _write_cache(self, cache_key: str, payload: dict[str, Any]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self.cache_dir / cache_key
        try:
            cache_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            return

    def _is_cache_fresh(self, cache_path: Path) -> bool:
        try:
            modified_at = datetime.fromtimestamp(
                cache_path.stat().st_mtime,
                tz=timezone.utc,
            )
        except OSError:
            return False
        age = datetime.now(tz=timezone.utc) - modified_at
        return age <= timedelta(hours=self.cache_ttl_hours)

    @staticmethod
    def _coerce_number(value: Any) -> float | None:
        # Chuyển dữ liệu số từ API về float; giá trị rỗng thì trả về None.
        if value in (None, ""):
            return None
        return float(value)

    @staticmethod
    def default_date_range() -> tuple[str, str]:
        # Khoảng ngày mặc định của dự án: từ 2020-01-01 đến hôm nay.
        today = date.today().isoformat()
        return "2020-01-01", today
