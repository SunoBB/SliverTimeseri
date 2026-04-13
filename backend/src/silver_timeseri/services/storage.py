from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd
from psycopg import connect
from psycopg.rows import tuple_row
from psycopg.sql import Identifier, SQL

EVENTS_TABLE_NAME = "economic_events"


def _ev(
    key: str,
    date: str,
    title: str,
    category: str,
    impact_level: str,
    impact_score: int,
    summary: str,
    price_impact: str,
    country: str,
    *,
    end_date: str | None = None,
    is_range: bool = False,
    actual: str | None = None,
    forecast: str | None = None,
    previous: str | None = None,
) -> tuple[object, ...]:
    """Build an event seed row in the column order required by the INSERT."""
    return (
        key, date, end_date, title, category, impact_level, impact_score,
        summary, price_impact, is_range, country, actual, forecast, previous,
    )


EVENT_SEED_ROWS: tuple[tuple[object, ...], ...] = (
    _ev("silver_all_time_high_2011", "2011-04-28",
        title="Bạc đỉnh lịch sử $49", category="commodity",
        impact_level="high", impact_score=10, country="global",
        summary="Sóng đầu cơ và lo ngại lạm phát sau gói QE2.",
        price_impact="+80%"),

    _ev("flash_crash_2011", "2011-09-01",
        title="Flash crash 9/2011", category="crisis",
        impact_level="high", impact_score=9, country="global",
        summary="Margin call và tháo chạy khỏi tài sản rủi ro.",
        price_impact="-30%"),

    _ev("fed_qe3_2012", "2012-09-13",
        title="Fed tung gói QE3", category="monetary",
        impact_level="medium", impact_score=7, country="us",
        summary="Fed bơm tiền không giới hạn kích thích hàng hóa.",
        price_impact="+10%"),

    _ev("gold_silver_selloff_2013", "2013-05-22",
        title="Sụp đổ giá vàng/bạc 2013", category="monetary",
        impact_level="high", impact_score=8, country="us",
        summary="Fed úp mở việc siết vòi tiền (Tapering).",
        price_impact="-17%"),

    _ev("oil_collapse_2014", "2014-11-01",
        title="Giá dầu sụp đổ", category="commodity",
        impact_level="medium", impact_score=6, country="global",
        summary="Dầu thô giảm mạnh kéo theo nhóm kim loại.",
        price_impact="-15%"),

    _ev("china_devaluation_2015", "2015-08-11",
        title="Trung Quốc phá giá NDT", category="fx",
        impact_level="medium", impact_score=6, country="china",
        summary="Chiến tranh tiền tệ, USD mạnh áp đảo kim loại.",
        price_impact="-15%"),

    _ev("brexit_2016", "2016-06-23",
        title="Brexit", category="geopolitics",
        impact_level="medium", impact_score=6, country="uk",
        summary="Anh rời EU, nhu cầu trú ẩn an toàn tăng cao.",
        price_impact="+10%"),

    _ev("trade_war_2018", "2018-06-15",
        title="Trade War Mỹ-Trung", category="geopolitics",
        impact_level="medium", impact_score=7, country="global",
        summary="Thuế quan leo thang, bạc rơi về đáy $14.",
        price_impact="-20%"),

    _ev("covid_panic_sell_2020", "2020-03-15",
        title="COVID-19 Panic Sell", category="crisis",
        impact_level="high", impact_score=9, country="global",
        summary="Bán tháo toàn thị trường lấy thanh khoản.",
        price_impact="-35%"),

    _ev("silver_post_covid_peak_2020", "2020-08-07",
        title="Đỉnh hậu COVID $29", category="monetary",
        impact_level="high", impact_score=8, country="global",
        summary="QE khổng lồ + lạm phát + sóng Reddit WSB.",
        price_impact="+140%"),

    _ev("wsb_short_squeeze_2021", "2021-02-01",
        title="Short Squeeze WSB", category="speculation",
        impact_level="medium", impact_score=5, country="us",
        summary="Reddit (WallStreetBets) cố tình đẩy giá bạc.",
        price_impact="+13%"),

    _ev("russia_ukraine_2022", "2022-02-24",
        title="Nga xâm lược Ukraine", category="geopolitics",
        impact_level="medium", impact_score=7, country="global",
        summary="Lo ngại chiến tranh đẩy giá kim loại ngắn hạn.",
        price_impact="+8%"),

    _ev("fed_hike_2022", "2022-06-15",
        title="Fed tăng lãi suất kỷ lục", category="monetary",
        impact_level="high", impact_score=9, country="us",
        summary="Fed tăng 75bp, DXY lập đỉnh làm bạc giảm.",
        price_impact="-30%",
        actual="0.75%", forecast="0.75%", previous="0.50%"),

    _ev("svb_crisis_2023", "2023-03-10",
        title="Khủng hoảng SVB", category="crisis",
        impact_level="medium", impact_score=7, country="us",
        summary="Dòng tiền tháo chạy vào vàng/bạc trú ẩn.",
        price_impact="+10%"),

    _ev("usd_vnd_peak_2024", "2024-04-10",
        title="Tỷ giá USD/VND đạt đỉnh", category="fx",
        impact_level="high", impact_score=8, country="vn",
        summary="Tỷ giá trong nước vượt 25.400đ gây sốc giá.",
        price_impact="Sốc VND"),

    _ev("silver_above_33_2024", "2024-05-20",
        title="Bạc vượt $33", category="commodity",
        impact_level="high", impact_score=8, country="global",
        summary="Nhu cầu pin mặt trời + tín hiệu Fed cắt lãi.",
        price_impact="+40%"),

    _ev("trump_tariff_2025", "2025-01-20",
        title="Tariff Trump 2025", category="policy",
        impact_level="medium", impact_score=7, country="us",
        summary="Thuế quan gây sốc cung bạc từ Mexico/Canada.",
        price_impact="+15%"),

    _ev("silver_ath_2026", "2026-03-15",
        title="Bạc $68 - Đỉnh mọi thời đại", category="commodity",
        impact_level="high", impact_score=10, country="global",
        summary="Nhu cầu năng lượng mặt trời & EV vượt cung.",
        price_impact="+100%"),
)


@dataclass(frozen=True)
class PostgresConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str
    table_name: str

    @property
    def dsn(self) -> str:
        return (
            f"host={self.host} "
            f"port={self.port} "
            f"dbname={self.dbname} "
            f"user={self.user} "
            f"password={self.password}"
        )


class PostgresSilverRepository:
    def __init__(self, config: PostgresConfig) -> None:
        self.config = config

    def ensure_schema(self) -> None:
        create_market_data = SQL("""
        CREATE TABLE IF NOT EXISTS {} (
            id                      BIGSERIAL PRIMARY KEY,
            symbol                  VARCHAR(10)  NOT NULL,
            timeframe               VARCHAR(10)  NOT NULL,
            series_layer            VARCHAR(20)  NOT NULL DEFAULT 'raw',
            price_timestamp         TIMESTAMP    NOT NULL,
            source_date             TIMESTAMP,
            price_usd               NUMERIC(10,2),
            price_vnd               NUMERIC(15,0),
            price_silver_usd        NUMERIC(10,2),
            price_silver_vnd        NUMERIC(15,0),
            usd_vnd_rate            NUMERIC(10,2),
            is_imputed              BOOLEAN      NOT NULL DEFAULT FALSE,
            is_weekend              BOOLEAN      NOT NULL DEFAULT FALSE,
            is_missing_from_source  BOOLEAN      NOT NULL DEFAULT FALSE,
            created_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            UNIQUE (symbol, timeframe, series_layer, price_timestamp)
        );
        """).format(Identifier(self.config.table_name))

        create_events = SQL("""
        CREATE TABLE IF NOT EXISTS {} (
            id                   BIGSERIAL    PRIMARY KEY,
            event_key            VARCHAR(120) NOT NULL UNIQUE,
            event_date           TIMESTAMP    NOT NULL,
            end_date             TIMESTAMP,
            title                VARCHAR(255) NOT NULL,
            category             VARCHAR(50)  NOT NULL,
            impact_level         VARCHAR(20)  NOT NULL DEFAULT 'medium',
            impact_score         SMALLINT     NOT NULL DEFAULT 5,
            summary              TEXT         NOT NULL,
            price_impact_summary VARCHAR(255),
            is_range_event       BOOLEAN      NOT NULL DEFAULT FALSE,
            country              VARCHAR(50),
            actual_value         VARCHAR(120),
            forecast_value       VARCHAR(120),
            previous_value       VARCHAR(120),
            created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        );
        """).format(Identifier(EVENTS_TABLE_NAME))

        # Migration: add series_layer if upgrading from a schema that lacked it,
        # then backfill + rebuild the unique index to include the new column.
        migration_queries = [
            SQL("ALTER TABLE {} ADD COLUMN IF NOT EXISTS series_layer VARCHAR(20) NOT NULL DEFAULT 'raw';").format(
                Identifier(self.config.table_name)
            ),
            SQL("UPDATE {} SET symbol = 'XAGUSD' WHERE symbol IS NULL;").format(
                Identifier(self.config.table_name)
            ),
            SQL("UPDATE {} SET timeframe = '1d'   WHERE timeframe IS NULL;").format(
                Identifier(self.config.table_name)
            ),
            SQL("ALTER TABLE {} DROP CONSTRAINT IF EXISTS {};").format(
                Identifier(self.config.table_name),
                Identifier(f"{self.config.table_name}_symbol_timeframe_price_timestamp_key"),
            ),
            SQL("DROP INDEX IF EXISTS {};").format(
                Identifier(f"{self.config.table_name}_symbol_timeframe_timestamp_idx"),
            ),
            SQL(
                "CREATE UNIQUE INDEX IF NOT EXISTS {} ON {} (symbol, timeframe, series_layer, price_timestamp);"
            ).format(
                Identifier(f"{self.config.table_name}_symbol_timeframe_layer_timestamp_idx"),
                Identifier(self.config.table_name),
            ),
            SQL("CREATE INDEX IF NOT EXISTS {} ON {} (event_date);").format(
                Identifier(f"{EVENTS_TABLE_NAME}_event_date_idx"),
                Identifier(EVENTS_TABLE_NAME),
            ),
            SQL("CREATE INDEX IF NOT EXISTS {} ON {} (category, impact_level, event_date);").format(
                Identifier(f"{EVENTS_TABLE_NAME}_category_impact_date_idx"),
                Identifier(EVENTS_TABLE_NAME),
            ),
            # Prune stale rows where price_usd is NULL — these are calendar-fill
            # rows that were inserted before the first raw observation existed in
            # the source feed.  They render as zero on charts.
            SQL("DELETE FROM {} WHERE price_usd IS NULL;").format(
                Identifier(self.config.table_name)
            ),
        ]

        seed_events_query = SQL("""
        INSERT INTO {} (
            event_key, event_date, end_date,
            title, category, impact_level, impact_score,
            summary, price_impact_summary,
            is_range_event, country,
            actual_value, forecast_value, previous_value
        )
        VALUES (%s, %s::timestamp, %s::timestamp, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (event_key) DO UPDATE
        SET event_date           = EXCLUDED.event_date,
            end_date             = EXCLUDED.end_date,
            title                = EXCLUDED.title,
            category             = EXCLUDED.category,
            impact_level         = EXCLUDED.impact_level,
            impact_score         = EXCLUDED.impact_score,
            summary              = EXCLUDED.summary,
            price_impact_summary = EXCLUDED.price_impact_summary,
            is_range_event       = EXCLUDED.is_range_event,
            country              = EXCLUDED.country,
            actual_value         = EXCLUDED.actual_value,
            forecast_value       = EXCLUDED.forecast_value,
            previous_value       = EXCLUDED.previous_value,
            updated_at           = NOW();
        """).format(Identifier(EVENTS_TABLE_NAME))

        with connect(self.config.dsn, row_factory=tuple_row) as conn:
            with conn.cursor() as cur:
                cur.execute(create_market_data)
                cur.execute(create_events)
                for q in migration_queries:
                    cur.execute(q)
                cur.executemany(seed_events_query, EVENT_SEED_ROWS)
            conn.commit()

    def upsert_market_data(self, frame: pd.DataFrame) -> int:
        if frame.empty:
            return 0

        df = frame.reset_index()
        rows: list[tuple[object, ...]] = []
        for row in df.itertuples(index=False):
            sd = row.source_date
            rows.append((
                row.symbol or "XAGUSD",
                row.timeframe or "1d",
                row.series_layer or "raw",
                row.date.to_pydatetime(),
                sd.to_pydatetime() if sd is not None and not pd.isna(sd) else None,
                _as_decimal(row.price_usd, "0.01"),
                _as_decimal(row.price_vnd, "1"),
                _as_decimal(row.price_silver_usd, "0.01"),
                _as_decimal(row.price_silver_vnd, "1"),
                _as_decimal(row.usd_vnd_rate, "0.01"),
                _as_bool(row.is_imputed),
                _as_bool(row.is_weekend),
                _as_bool(row.is_missing_from_source),
            ))

        query = SQL("""
        INSERT INTO {} (
            symbol, timeframe, series_layer, price_timestamp,
            source_date, price_usd, price_vnd,
            price_silver_usd, price_silver_vnd, usd_vnd_rate,
            is_imputed, is_weekend, is_missing_from_source
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (symbol, timeframe, series_layer, price_timestamp) DO UPDATE
        SET source_date             = EXCLUDED.source_date,
            price_usd               = EXCLUDED.price_usd,
            price_vnd               = EXCLUDED.price_vnd,
            price_silver_usd        = EXCLUDED.price_silver_usd,
            price_silver_vnd        = EXCLUDED.price_silver_vnd,
            usd_vnd_rate            = EXCLUDED.usd_vnd_rate,
            is_imputed              = EXCLUDED.is_imputed,
            is_weekend              = EXCLUDED.is_weekend,
            is_missing_from_source  = EXCLUDED.is_missing_from_source,
            updated_at              = NOW();
        """).format(Identifier(self.config.table_name))

        with connect(self.config.dsn, row_factory=tuple_row) as conn:
            with conn.cursor() as cur:
                cur.executemany(query, rows)
            conn.commit()
        return len(rows)

    def fetch_history(
        self,
        symbol: str = "XAGUSD",
        timeframe: str = "1d",
        series_layer: str = "curated",
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> pd.DataFrame:
        conditions = ["symbol = %s", "timeframe = %s", "series_layer = %s"]
        params: list[object] = [symbol, timeframe, series_layer]
        if start_date:
            conditions.append("price_timestamp >= %s")
            params.append(_normalize_start_date(start_date))
        if end_date:
            conditions.append("price_timestamp <= %s")
            params.append(_normalize_end_date(end_date))

        limit_clause = ""
        if limit is not None:
            limit_clause = " LIMIT %s"
            params.append(limit)
        offset_clause = ""
        if offset is not None:
            offset_clause = " OFFSET %s"
            params.append(offset)

        query = SQL(
            """
            SELECT
                symbol, timeframe, series_layer, price_timestamp,
                source_date, price_usd, price_vnd,
                price_silver_usd, price_silver_vnd, usd_vnd_rate,
                is_imputed, is_weekend, is_missing_from_source,
                created_at, updated_at
            FROM {}
            WHERE
            """
        ).format(Identifier(self.config.table_name))
        where_clause = SQL(" AND ".join(conditions))
        order_clause = SQL(" ORDER BY price_timestamp ASC" + limit_clause + offset_clause)

        with connect(self.config.dsn, row_factory=tuple_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query + where_clause + order_clause, params)
                rows = cur.fetchall()

        columns = [
            "symbol", "timeframe", "series_layer", "price_timestamp",
            "source_date", "price_usd", "price_vnd",
            "price_silver_usd", "price_silver_vnd", "usd_vnd_rate",
            "is_imputed", "is_weekend", "is_missing_from_source",
            "created_at", "updated_at",
        ]
        frame = pd.DataFrame(rows, columns=columns)
        if frame.empty:
            return frame
        frame["price_timestamp"] = pd.to_datetime(frame["price_timestamp"], utc=False)
        frame["source_date"] = pd.to_datetime(frame["source_date"], utc=False, errors="coerce")
        for col in ["price_usd", "price_vnd", "price_silver_usd", "price_silver_vnd", "usd_vnd_rate"]:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        for col in ["is_imputed", "is_weekend", "is_missing_from_source"]:
            frame[col] = frame[col].fillna(False).astype(bool)
        return frame

    def count_history(
        self,
        symbol: str = "XAGUSD",
        timeframe: str = "1d",
        series_layer: str = "curated",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> int:
        conditions = ["symbol = %s", "timeframe = %s", "series_layer = %s"]
        params: list[object] = [symbol, timeframe, series_layer]
        if start_date:
            conditions.append("price_timestamp >= %s")
            params.append(_normalize_start_date(start_date))
        if end_date:
            conditions.append("price_timestamp <= %s")
            params.append(_normalize_end_date(end_date))

        query = SQL("SELECT COUNT(*) FROM {} WHERE ").format(Identifier(self.config.table_name))
        where_clause = SQL(" AND ".join(conditions))

        with connect(self.config.dsn, row_factory=tuple_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query + where_clause, params)
                row = cur.fetchone()
        return int(row[0]) if row is not None else 0

    def fetch_latest(
        self,
        symbol: str = "XAGUSD",
        timeframe: str = "1d",
        series_layer: str = "curated",
    ) -> dict[str, object] | None:
        query = SQL("""
        SELECT
            symbol, timeframe, series_layer, price_timestamp,
            source_date, price_usd, price_vnd,
            price_silver_usd, price_silver_vnd, usd_vnd_rate,
            is_imputed, is_weekend, is_missing_from_source,
            created_at, updated_at
        FROM {}
        WHERE symbol = %s AND timeframe = %s AND series_layer = %s
        ORDER BY price_timestamp DESC
        LIMIT 1
        """).format(Identifier(self.config.table_name))

        with connect(self.config.dsn, row_factory=tuple_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (symbol, timeframe, series_layer))
                row = cur.fetchone()

        if row is None:
            return None
        return {
            "symbol":                  row[0],
            "timeframe":               row[1],
            "series_layer":            row[2],
            "price_timestamp":         row[3].isoformat(),
            "source_date":             row[4].isoformat() if row[4] is not None else None,
            "price_usd":               float(row[5]) if row[5] is not None else None,
            "price_vnd":               float(row[6]) if row[6] is not None else None,
            "price_silver_usd":        float(row[7]) if row[7] is not None else None,
            "price_silver_vnd":        float(row[8]) if row[8] is not None else None,
            "usd_vnd_rate":            float(row[9]) if row[9] is not None else None,
            "is_imputed":              bool(row[10]),
            "is_weekend":              bool(row[11]),
            "is_missing_from_source":  bool(row[12]),
            "created_at":              row[13].isoformat() if row[13] is not None else None,
            "updated_at":              row[14].isoformat() if row[14] is not None else None,
        }

    def fetch_economic_events(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        categories: list[str] | None = None,
        impact_level: str | None = None,
    ) -> list[dict[str, object]]:
        conditions = ["1 = 1"]
        params: list[object] = []
        if start_date:
            conditions.append("(COALESCE(end_date, event_date) >= %s)")
            params.append(_normalize_start_date(start_date))
        if end_date:
            conditions.append("event_date <= %s")
            params.append(_normalize_end_date(end_date))
        if categories:
            conditions.append("category = ANY(%s)")
            params.append(categories)
        if impact_level:
            conditions.append("impact_level = %s")
            params.append(impact_level)

        query = SQL("""
        SELECT
            event_key, event_date, end_date,
            title, category, impact_level, impact_score,
            summary, price_impact_summary,
            is_range_event, country,
            actual_value, forecast_value, previous_value
        FROM {}
        WHERE
        """).format(Identifier(EVENTS_TABLE_NAME))
        where_clause = SQL(" AND ".join(conditions))
        order_clause = SQL(" ORDER BY event_date ASC, impact_score DESC, title ASC")

        with connect(self.config.dsn, row_factory=tuple_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query + where_clause + order_clause, params)
                rows = cur.fetchall()

        return [
            {
                "event_key":           row[0],
                "event_date":          row[1].isoformat() if row[1] is not None else None,
                "end_date":            row[2].isoformat() if row[2] is not None else None,
                "title":               row[3],
                "category":            row[4],
                "impact_level":        row[5],
                "impact_score":        int(row[6]),
                "summary":             row[7],
                "price_impact_summary": row[8],
                "is_range_event":      bool(row[9]),
                "country":             row[10],
                "actual_value":        row[11],
                "forecast_value":      row[12],
                "previous_value":      row[13],
            }
            for row in rows
        ]

    def prune_layer_before(
        self,
        series_layer: str,
        cutoff: datetime,
        symbol: str = "XAGUSD",
        timeframe: str = "1d",
    ) -> int:
        """Delete rows for `series_layer` whose price_timestamp < cutoff.

        Used after each sync to remove stale calendar-fill rows that
        predate the earliest raw observation (they have null prices and
        render as zero on charts).
        """
        query = SQL("""
        DELETE FROM {}
        WHERE symbol = %s
          AND timeframe = %s
          AND series_layer = %s
          AND price_timestamp < %s
        """).format(Identifier(self.config.table_name))

        with connect(self.config.dsn, row_factory=tuple_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (symbol, timeframe, series_layer, cutoff))
                deleted = cur.rowcount
            conn.commit()
        return deleted

    def _get_existing_columns(self, cursor: object) -> set[str]:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (self.config.table_name,),
        )
        return {row[0] for row in cursor.fetchall()}


# ── helpers ────────────────────────────────────────────────────────────────

def _as_decimal(value: object, places: str) -> Decimal | None:
    if value is None or pd.isna(value):
        return None
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _as_bool(value: object) -> bool:
    if value is None or pd.isna(value):
        return False
    return bool(value)


def _normalize_start_date(value: str) -> datetime | str:
    parsed = _try_parse_date(value)
    return parsed.replace(hour=0, minute=0, second=0, microsecond=0) if parsed else value


def _normalize_end_date(value: str) -> datetime | str:
    parsed = _try_parse_date(value)
    return parsed.replace(hour=23, minute=59, second=59, microsecond=999999) if parsed else value


def _try_parse_date(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
