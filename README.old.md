# Phân Tích Chuỗi Thời Gian Giá Bạc

`Nhãn tài liệu:` Overview dự án, quickstart, cách chạy.

Tài liệu chuyên sâu theo từng mảng:

- Schema, data dictionary: [docs/database.md](docs/database.md)
- Luồng nạp dữ liệu & clean/ffill: [docs/agents/data-ingestion.md](docs/agents/data-ingestion.md)
- FastAPI endpoints & scheduler: [docs/agents/backend-api.md](docs/agents/backend-api.md)
- Storage & PostgreSQL: [docs/agents/storage.md](docs/agents/storage.md)
- Feature engineering & mô hình: [docs/agents/analysis.md](docs/agents/analysis.md)
- React frontend & URL pagination: [docs/agents/frontend.md](docs/agents/frontend.md)

---

## 1. Mục tiêu dự án

- Thu thập dữ liệu lịch sử giá bạc và tỷ giá USD/VND từ Alpha Vantage.
- Chuẩn hóa dữ liệu thành time series liên tục (clean + ffill ngày lễ/cuối tuần).
- Tính thống kê mô tả và tạo đặc trưng cho bài toán dự báo.
- Huấn luyện và so sánh mô hình ARX, MA, ARMA.
- Đồng bộ dataset vào PostgreSQL để phục vụ API, dashboard và tra cứu.

## 2. Nguồn dữ liệu

Alpha Vantage, endpoint được dùng:
- `GOLD_SILVER_HISTORY` — giá bạc theo ngày
- `FX_DAILY` (USDVND) — tỷ giá USD/VND theo ngày

Response thô được cache tại `data/raw/alpha_vantage/` (TTL 24h) để giảm rate limit.

> Lưu ý: khóa `demo` không dùng được cho `GOLD_SILVER_HISTORY`. Cần đăng ký API key riêng.

## 3. Cấu trúc thư mục

```text
frontend/                  # Vite + React frontend
backend/
  src/silver_timeseri/
    analysis/              # features, models, metrics, visualization
    providers/             # AlphaVantageProvider
    services/              # pipeline, storage, app_service, scheduler
    api.py                 # FastAPI app
    cli.py                 # CLI entrypoint
    config.py              # Biến môi trường
  dashboard.py             # Streamlit dashboard (alternative)
  docker/postgres/init.sql # PostgreSQL schema + seeded events
  docker-compose.yml       # PostgreSQL local stack
docs/
  database.md              # Schema, data dictionary
  agents/                  # Tài liệu từng luồng xử lý
data/raw/alpha_vantage/    # API response cache
outputs/charts/            # Biểu đồ sinh ra từ CLI
```

## 4. Luồng xử lý

```
AlphaVantageProvider  →  SilverTimeSeriesPipeline  →  PostgreSQL
       ↑                         ↓                        ↓
   API cache               raw + curated             FastAPI /silver/*
                                                          ↓
                                                    React Frontend
```

1. `AlphaVantageProvider` lấy giá bạc và tỷ giá, cache local 24h.
2. `SilverTimeSeriesPipeline` tạo lớp `raw` (ngày giao dịch) và `curated` (chuỗi liên tục, ffill).
3. CLI, API và scheduler dùng chung `app_service` để đọc, phân tích hoặc sync dữ liệu.
4. Frontend hiển thị chart, bảng phân trang và forecast; URL phản ánh trạng thái hiện tại.

### Sync tăng dần (incremental sync)

Thay vì sync toàn bộ hoặc theo window cố định, hệ thống dùng `sync_incremental`:

```
latest raw date in DB  →  end_date = today - 1
```

- **Nếu DB trống**: full backfill đến hôm qua.
- **Nếu đã up-to-date**: bỏ qua, không gọi API (`skipped: true`).
- **Còn lại**: sync đúng khoảng còn thiếu, không fetch lại dữ liệu cũ.

Scheduler chạy `sync_incremental` tự động lúc 0h, 6h, 12h, 18h, 22h (giờ VN) và morning check. Endpoint thủ công: `POST /silver/sync/incremental`.

Chi tiết về hai lớp `raw` / `curated` và cách ffill: [docs/agents/data-ingestion.md](docs/agents/data-ingestion.md).

## 5. Cài đặt

### Yêu cầu

- Python 3.x, `pip`
- Docker + Docker Compose (cho PostgreSQL local)
- Node.js 18+ (cho frontend)
- Kết nối Internet để gọi Alpha Vantage

### Thiết lập backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
# Sửa ALPHAVANTAGE_API_KEY trong backend/.env
```

Biến môi trường quan trọng:

```env
ALPHAVANTAGE_API_KEY=your_api_key_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=silver_timeseri
POSTGRES_USER=silver_user
POSTGRES_PASSWORD=silver_password
SCHEDULER_ENABLED=true
SCHEDULER_TIMEZONE=Asia/Ho_Chi_Minh
RAW_CACHE_TTL_HOURS=24
```

### Khởi tạo PostgreSQL

```bash
cd backend && docker compose up -d
```

Schema tự động tạo từ `backend/docker/postgres/init.sql` khi container khởi động.

## 6. Cách chạy

### Demo nhanh (5 bước)

```bash
cd backend && docker compose up -d
PYTHONPATH=backend/src uvicorn silver_timeseri.api:app --reload
cd frontend && npm install && npm run dev
# Mở http://127.0.0.1:5173
# Bấm "Sync Data" hoặc POST /silver/sync
```

### CLI

```bash
# In thống kê mô tả
PYTHONPATH=backend/src python3 -m silver_timeseri.cli summarize \
  --series-layer curated --timeframe 1d \
  --start-date 2023-01-01 --end-date 2026-06-30

# Xuất CSV
PYTHONPATH=backend/src python3 -m silver_timeseri.cli export \
  --series-layer curated --timeframe 1d \
  --start-date 2020-01-01 --end-date 2026-04-12 \
  --output data/silver_curated.csv

# Đồng bộ tăng dần: tự phát hiện latest date trong DB, sync đến hôm qua
PYTHONPATH=backend/src python3 -m silver_timeseri.cli sync-incremental

# Đồng bộ thủ công với khoảng ngày cụ thể
PYTHONPATH=backend/src python3 -m silver_timeseri.cli sync-db \
  --timeframe 1d --start-date 2020-01-01 --end-date 2026-04-12

# Huấn luyện mô hình
PYTHONPATH=backend/src python3 -m silver_timeseri.cli model \
  --timeframe 1d --model-type all \
  --ar-order 5 --ma-order 3 --test-size 30 \
  --start-date 2022-01-01 --end-date 2026-04-12

# Sinh biểu đồ
PYTHONPATH=backend/src python3 -m silver_timeseri.cli charts \
  --start-date 2024-01-01 --end-date 2024-12-31 \
  --output-dir outputs/charts
```

> `--timeframe 1d` là timeframe duy nhất ổn định với gói free Alpha Vantage.

### API

```bash
PYTHONPATH=backend/src uvicorn silver_timeseri.api:app --reload
# http://127.0.0.1:8000
# Docs: http://127.0.0.1:8000/docs
```

Endpoints chính:

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/health` | Health check |
| GET | `/silver/latest` | Row mới nhất trong DB |
| GET | `/silver/history` | Lịch sử giá, hỗ trợ phân trang |
| GET | `/silver/summary` | Thống kê mô tả |
| GET | `/silver/events` | Sự kiện kinh tế |
| GET | `/silver/models` | Dự báo mô hình AR/MA/ARMA |
| POST | `/silver/sync/incremental` | Sync tăng dần từ latest DB đến hôm qua |
| POST | `/silver/sync` | Sync thủ công với `start_date`/`end_date` tùy chọn |

Chi tiết từng endpoint: [docs/agents/backend-api.md](docs/agents/backend-api.md).

### Streamlit dashboard (alternative)

```bash
streamlit run backend/dashboard.py
```

## 7. Dataset và mô hình dự báo

### Hai lớp dữ liệu

| Layer | Đặc điểm | Dùng cho |
|-------|---------|---------|
| `raw` | Chỉ ngày giao dịch thật | Audit, đối chiếu nguồn |
| `curated` | Chuỗi liên tục, ffill ngày thiếu | Analytics, ML, dashboard |

Ví dụ sync thực tế:
```json
{"rows_upserted_by_layer": {"raw": 5237, "curated": 5428}}
```
→ 191 ngày được fill (cuối tuần + ngày lễ).

### Các mô hình

- **ARX**: AR với biến ngoại sinh (MA, RSI, momentum...), OLS.
- **MA**: ARIMA(0,0,q), chỉ thành phần moving average.
- **ARMA**: ARIMA(p,0,q), kết hợp AR và MA.

Chi tiết feature engineering và metrics: [docs/agents/analysis.md](docs/agents/analysis.md).

## 8. Lỗi thường gặp

| Lỗi | Nguyên nhân | Xử lý |
|-----|------------|-------|
| Không lấy được dữ liệu | API key sai / rate limit | Kiểm tra `ALPHAVANTAGE_API_KEY`, thử lại sau |
| API trả về nhưng thiếu dữ liệu | Demo key / vượt giới hạn free | Đăng ký API key thật |
| Model báo lỗi thiếu dữ liệu | Khoảng ngày quá hẹp | Nới `start_date`/`end_date` |
| PostgreSQL không kết nối | Container chưa chạy | `cd backend && docker compose up -d` |

## 9. Hướng mở rộng

- Thêm nguồn dữ liệu khác (Investing.com, Yahoo Finance...).
- Thêm mô hình SARIMA, Prophet, LSTM.
- Materialized view cho feature engineering trong DB.
- Partition bảng theo `price_timestamp` khi dữ liệu lớn.
- Tách train/test snapshot thành layer riêng.
