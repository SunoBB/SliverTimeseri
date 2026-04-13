# Agent: Storage Flow

`Nhãn tài liệu:` Mô tả luồng ghi và đọc dữ liệu từ PostgreSQL thông qua `PostgresSilverRepository`.

`Chi tiết schema:` Xem [database.md](../database.md) — file đó là nguồn chân lý cho schema, data dictionary và khuyến nghị mở rộng.

## Tổng quan

```
DataFrame (pandas)
        │
        ▼
PostgresSilverRepository
  ├── upsert_market_data()   → INSERT ... ON CONFLICT DO UPDATE
  ├── fetch_history()        → SELECT + LIMIT/OFFSET
  ├── fetch_summary()        → aggregate query
  ├── fetch_latest()         → SELECT ORDER BY DESC LIMIT 1
  └── fetch_events()         → SELECT economic_events
        │
        ▼
PostgreSQL (silver_market_data, economic_events)
```

## Các file liên quan

| File | Vai trò |
|------|---------|
| `backend/src/silver_timeseri/services/storage.py` | Repository, tất cả SQL |
| `backend/docker/postgres/init.sql` | Schema DDL, seeded events |
| `backend/docker-compose.yml` | PostgreSQL container config |
| `backend/src/silver_timeseri/config.py` | DB connection settings |

## Kết nối

Dùng `psycopg` (v3) với connection string từ biến môi trường:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=silver_timeseri
POSTGRES_USER=silver_user
POSTGRES_PASSWORD=silver_password
```

Repository tạo connection mới mỗi lần gọi qua context manager. Không dùng connection pool ở giai đoạn hiện tại.

## Upsert

```sql
INSERT INTO silver_market_data (symbol, timeframe, series_layer, price_timestamp, ...)
VALUES (...)
ON CONFLICT (symbol, timeframe, series_layer, price_timestamp)
DO UPDATE SET
  price_usd = EXCLUDED.price_usd,
  price_vnd = EXCLUDED.price_vnd,
  ...
  updated_at = NOW();
```

- Khóa unique: `(symbol, timeframe, series_layer, price_timestamp)`.
- `raw` và `curated` không ghi đè nhau vì `series_layer` nằm trong khóa.
- Upsert chạy batch theo chunk để tránh timeout với dataset lớn.

## Fetch History (phân trang)

```sql
SELECT * FROM silver_market_data
WHERE symbol = $1 AND timeframe = $2 AND series_layer = $3
  [AND price_timestamp >= $start]
  [AND price_timestamp <= $end]
ORDER BY price_timestamp DESC
[LIMIT $limit OFFSET $offset]
```

Khi `limit` là `None`, bỏ `LIMIT/OFFSET` và trả toàn bộ để vẽ chart.

## Schema tóm tắt

Hai bảng:
1. `silver_market_data` — time series giá, đã có index theo `(symbol, timeframe, series_layer, price_timestamp)`.
2. `economic_events` — sự kiện kinh tế, seeded sẵn 18 events trong `init.sql`.

Xem chi tiết cột, precision và data dictionary tại [database.md](../database.md).

## Khởi tạo schema

```bash
cd backend
docker compose up -d
# Schema tự tạo từ init.sql khi container khởi động
```

Schema cũng được tạo tự động lần đầu khi `PostgresSilverRepository.ensure_schema()` được gọi, phòng trường hợp không dùng Docker.

## Lưu ý vận hành

- `init.sql` chỉ chạy một lần khi tạo volume mới. Nếu muốn reset schema, cần xóa volume Docker.
- Tất cả thay đổi schema nên cập nhật cả `init.sql` và `ensure_schema()`.
- `price_vnd` và `price_silver_vnd` là cột dẫn xuất — chỉ pipeline ETL được ghi, không cập nhật tay.
