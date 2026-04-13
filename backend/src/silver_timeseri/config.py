from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RAW_CACHE_DIR = REPO_ROOT / "data" / "raw" / "alpha_vantage"

load_dotenv(REPO_ROOT / ".env")
load_dotenv(BACKEND_ROOT / ".env", override=True)


@dataclass(frozen=True)
class Settings:
    alpha_vantage_api_key: str = os.getenv("ALPHAVANTAGE_API_KEY", "demo")
    alpha_vantage_base_url: str = os.getenv(
        "ALPHAVANTAGE_BASE_URL",
        "https://www.alphavantage.co/query",
    )
    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db: str = os.getenv("POSTGRES_DB", "silver_timeseri")
    postgres_user: str = os.getenv("POSTGRES_USER", "silver_user")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "silver_password")
    postgres_table: str = os.getenv("POSTGRES_TABLE", "silver_market_data")
    raw_cache_dir: Path = Path(os.getenv("RAW_CACHE_DIR", str(DEFAULT_RAW_CACHE_DIR)))
    raw_cache_ttl_hours: int = int(os.getenv("RAW_CACHE_TTL_HOURS", "24"))
    scheduler_enabled: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
    scheduler_timezone: str = os.getenv("SCHEDULER_TIMEZONE", "Asia/Ho_Chi_Minh")
    scheduler_morning_check_hour: int = int(os.getenv("SCHEDULER_MORNING_CHECK_HOUR", "7"))

    @property
    def scheduler_tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.scheduler_timezone)


def get_settings() -> Settings:
    return Settings()
