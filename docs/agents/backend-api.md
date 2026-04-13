# Agent: Backend API Flow

`Nhãn tài liệu:` Mô tả luồng xử lý request từ FastAPI → AppService → Storage, bao gồm cấu trúc các endpoint và scheduler.

## Tổng quan

```
Client (Frontend / CLI / External)
        │ HTTP request
        ▼
FastAPI app  (api.py)
        │ gọi AppService methods
        ▼
AppService   (services/app_service.py)
        │ đọc/ghi qua repository
        ▼
PostgresSilverRepository  (services/storage.py)
        │
        ▼
PostgreSQL   (silver_market_data, economic_events)
```

Scheduler chạy song song và tự động gọi `AppService.sync()` theo lịch.

## Các file liên quan

| File | Vai trò |
|------|---------|
| `backend/src/silver_timeseri/api.py` | FastAPI app, route definitions, lifespan |
| `backend/src/silver_timeseri/services/app_service.py` | Business logic, gọi pipeline + storage |
| `backend/src/silver_timeseri/services/storage.py` | Repository pattern, SQL queries |
| `backend/src/silver_timeseri/services/scheduler.py` | APScheduler, auto-sync theo giờ |
| `backend/src/silver_timeseri/config.py` | Đọc biến môi trường |

## Endpoints

### `GET /health`
Kiểm tra trạng thái API. Trả `{"status": "ok"}`.

### `GET /silver/latest`
Lấy giá mới nhất.

```
Query params:
  timeframe     (default: "1d")
  series_layer  (default: "curated")
```

### `GET /silver/history`
Lấy dữ liệu lịch sử với phân trang. Dùng cho bảng và biểu đồ.

```
Query params:
  start_date    (optional, YYYY-MM-DD)
  end_date      (optional, YYYY-MM-DD)
  timeframe     (default: "1d")
  series_layer  (default: "curated")
  limit         (default: None → toàn bộ)
  offset        (default: 0)

Response:
  {
    "data": [...],
    "total_rows": 5428,
    "rows": 50
  }
```

Khi `limit` không truyền, trả toàn bộ dataset để vẽ chart. Khi có `limit`, dùng SQL `LIMIT/OFFSET` cho phân trang.

### `GET /silver/summary`
Trả thống kê mô tả: số dòng, giá đầu/cuối, min/max, trung bình, lợi suất, drawdown, volatility.

### `GET /silver/events`
Lấy các sự kiện kinh tế từ bảng `economic_events`.

```
Query params:
  start_date         (optional)
  end_date           (optional)
  categories         (optional, danh sách)
  high_impact_only   (optional, bool)
```

### `GET /silver/models`
Huấn luyện và trả kết quả mô hình ARX, MA, ARMA. Đây là endpoint nặng nhất (có thể mất 5–15 giây).

```
Query params:
  start_date   end_date   timeframe   series_layer
  ar_order     (default: 5)
  ma_order     (default: 3)
  test_size    (default: 30)

Response:
  {
    "models": [...],
    "model_rankings": {...},
    "forecast_context": {...},
    "latest_actual": {...}
  }
```

### `POST /silver/sync`
Kích hoạt đồng bộ dữ liệu từ Alpha Vantage vào PostgreSQL.

```
Query params:
  start_date, end_date, timeframe
  force_refresh  (bool, bỏ qua cache)

Response:
  {
    "rows_upserted_by_layer": {"raw": 5237, "curated": 5428},
    "synced_at": "..."
  }
```

## AppService: forecast_context

`AppService` tính `forecast_context` để phân biệt hai trường hợp:

| `forecast_target_type` | Ý nghĩa |
|------------------------|---------|
| `"tomorrow"` | DB đã có dữ liệu đến hôm nay, forecast cho ngày mai |
| `"catch_up"` | DB đang thiếu dữ liệu, forecast cho kỳ kế tiếp còn thiếu |

Logic kiểm tra `latest_data_date` so với ngày hiện tại (theo `Asia/Ho_Chi_Minh`).

## Scheduler

Chạy trong background khi API khởi động (`lifespan` FastAPI).

```
Lịch sync:  00:00, 06:00, 12:00, 18:00, 22:00  (Asia/Ho_Chi_Minh)
Morning check: 07:00 → sync nếu dữ liệu stale > 1 ngày
```

Cấu hình qua `.env`:
```env
SCHEDULER_ENABLED=true
SCHEDULER_TIMEZONE=Asia/Ho_Chi_Minh
SCHEDULER_MORNING_CHECK_HOUR=7
```

## Chạy API

```bash
PYTHONPATH=backend/src uvicorn silver_timeseri.api:app --reload
# Mặc định tại http://127.0.0.1:8000
# Docs tại http://127.0.0.1:8000/docs
```
