# Phân Tích Chuỗi Thời Gian Giá Bạc

Tài liệu chuyên sâu theo từng mảng:
- Schema, data dictionary: [docs/database.md](docs/database.md)
- Luồng nạp dữ liệu & clean/ffill: [docs/agents/data-ingestion.md](docs/agents/data-ingestion.md)
- FastAPI endpoints & scheduler: [docs/agents/backend-api.md](docs/agents/backend-api.md)
- Feature engineering & mô hình: [docs/agents/analysis.md](docs/agents/analysis.md)
- React frontend: [docs/agents/frontend.md](docs/agents/frontend.md)

---

## Mục tiêu dự án

Thu thập dữ liệu lịch sử giá bạc (USD/ounce → VND/lượng), chuẩn hóa thành chuỗi thời gian liên tục, phân tích học thuật đầy đủ (EDA → ADF → phân rã → 6 mô hình dự báo), đồng thời phục vụ API REST và React dashboard.

---

## Cấu trúc thư mục

```
backend/
  src/silver_timeseri/
    analysis/
      features.py       # build_monthly_series, build_decomposition_report, lag/indicator
      models.py         # SES, Holt, HW×2, ARIMA(monthly) + ARX/MA/ARMA(daily)
      metrics.py        # MAE, RMSE, MAPE, ADF test, build_comparison_table
      visualization.py  # 9 EDA charts + ACF/PACF + decomp + forecast comparison
    providers/
      alpha_vantage.py  # Gọi API, parse JSON, cache local
    services/
      pipeline.py       # raw + curated layer (ffill)
      storage.py        # PostgreSQL upsert
      app_service.py    # Orchestration
      scheduler.py      # Auto sync 0h/6h/12h/18h/22h
    api.py              # FastAPI REST endpoints
    cli.py              # CLI entrypoint
  dashboard.py          # Streamlit dashboard
  docker-compose.yml    # PostgreSQL local

data/raw/alpha_vantage/ # Cache JSON từ API (TTL 24h)
outputs/charts/         # PNG sinh ra từ CLI
frontend/               # Vite + React
script.sh               # Shortcut tất cả lệnh thường dùng
```

---

## Cài đặt (một lần)

```bash
# 1. Tạo virtualenv và cài thư viện
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# 2. Tạo file .env
cp backend/.env.example backend/.env
# Sửa ALPHAVANTAGE_API_KEY trong backend/.env
```

**Biến môi trường bắt buộc** (`backend/.env`):

```env
ALPHAVANTAGE_API_KEY=your_key_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=silver_timeseri
POSTGRES_USER=silver_user
POSTGRES_PASSWORD=silver_password
```

> API key free đủ dùng cho `GOLD_SILVER_HISTORY` và `FX_DAILY`. Key `demo` không hoạt động với endpoint giá bạc.

---

## Vận hành từ A → Z

### Bước 1 — Khởi động PostgreSQL

```bash
./script.sh db-up
# hoặc: cd backend && docker compose up -d
```

Kiểm tra container đã chạy:
```bash
./script.sh db-status
```

---

### Bước 2 — Lấy dữ liệu & nạp vào DB

**Cách thông thường — sync toàn bộ một khoảng ngày:**

```bash
./script.sh sync 2011-01-01 2026-04-12
# hoặc dùng CLI trực tiếp:
PYTHONPATH=backend/src python3 -m silver_timeseri.cli sync-db \
  --start-date 2011-01-01 --end-date 2026-04-12 --timeframe 1d
```

**Sync tăng dần (dùng hàng ngày — tự phát hiện khoảng còn thiếu):**

```bash
PYTHONPATH=backend/src python3 -m silver_timeseri.cli sync-incremental
```

> Luồng bên trong: Alpha Vantage API → cache JSON `data/raw/alpha_vantage/` → pipeline tạo lớp `raw` (ngày giao dịch) + `curated` (chuỗi liên tục, ffill cuối tuần/ngày lễ) → upsert PostgreSQL.

Kiểm tra dữ liệu vừa nạp:
```bash
./script.sh summary curated 2011-01-01 2026-04-12
```

---

### Bước 3 — Chạy phân tích học thuật đầy đủ (lệnh chính)

```bash
PYTHONPATH=backend/src python3 -m silver_timeseri.cli academic \
  --start-date 2011-01-01 --end-date 2026-04-12 \
  --test-size 12 \
  --n-months-forecast 12
```

Lệnh này chạy tuần tự toàn bộ luồng và tự động lưu chart:

| Bước | Nội dung | Output |
|------|----------|--------|
| 1 | Resample daily → monthly (179 tháng) | — |
| 2 | Vẽ ACF/PACF — nhận diện p, q | `10_acf_pacf_chart.png` |
| 3 | ADF test (levels, diff-1, diff-2) → kết luận d | In ra JSON |
| 4 | Phân rã cộng + nhân, chọn mô hình | `11_decomposition_additive/multiplicative_chart.png` |
| 5 | Train 6 mô hình, bảng MAE/RMSE/MAPE | `13_forecast_comparison_chart.png` |
| 6 | Dự báo 12 tháng bằng mô hình tốt nhất | `14_future_forecast_chart.png` |

**Kết quả thực tế (2011–2026, 179 tháng):**
- ADF: chuỗi gốc không dừng → sai phân bậc 1 dừng → **d = 1**
- Phân rã: mô hình **Nhân (Multiplicative)** phù hợp hơn (seasonal.std = 0.0099 vs 0.2641)
- Mô hình tốt nhất: **Holt Linear** — MAPE = 34.41%, MAE = 23.39, RMSE = 30.22
- Dự báo 12 tháng: ~75 → ~91 USD/ounce

Tùy chỉnh tham số:
```bash
# Đổi test size sang 24 tháng, ARIMA(2,1,2), dự báo 6 tháng
PYTHONPATH=backend/src python3 -m silver_timeseri.cli academic \
  --start-date 2011-01-01 --end-date 2026-04-12 \
  --test-size 24 \
  --arima-p 2 --arima-d 1 --arima-q 2 \
  --n-months-forecast 6 \
  --output-dir outputs/charts
```

---

### Bước 4 — Sinh biểu đồ EDA (9 charts cơ bản)

```bash
PYTHONPATH=backend/src python3 -m silver_timeseri.cli charts \
  --start-date 2011-01-01 --end-date 2026-04-12 \
  --output-dir outputs/charts \
  --ma-window 12 \
  --aggregation-rule ME \
  --bins 20
```

Charts sinh ra trong `outputs/charts/`:

| File | Nội dung |
|------|----------|
| `01_trend_overview_line_chart.png` | Giá bạc theo thời gian |
| `02_trend_smoothing_moving_average_chart.png` | Rolling mean (làm mượt xu hướng) |
| `03_trend_zoom_aggregation_*_chart.png` | Gộp theo kỳ |
| `04_distribution_outlier_boxplot_chart.png` | Phân phối + outlier |
| `05_distribution_frequency_histogram_chart.png` | Histogram |
| `06_distribution_density_kde_chart.png` | KDE density |
| `07_time_dependency_autocorrelation_chart.png` | Autocorrelation |
| `08_time_dependency_lag_relationship_chart.png` | Lag plot |
| `09_analysis_summary_combo_chart.png` | Tổng hợp |
| `10_acf_pacf_chart.png` | ACF + PACF (từ lệnh `academic`) |
| `11_decomposition_*_chart.png` | Phân rã cộng/nhân |
| `13_forecast_comparison_chart.png` | 6 mô hình vs actual |
| `14_future_forecast_chart.png` | Dự báo tương lai |

---

### Bước 5 — Khởi động API (nếu cần frontend)

```bash
./script.sh api
# hoặc:
PYTHONPATH=backend/src uvicorn silver_timeseri.api:app --reload
# Docs: http://127.0.0.1:8000/docs
```

Endpoints chính:

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/health` | Health check |
| GET | `/silver/history` | Lịch sử giá, hỗ trợ phân trang |
| GET | `/silver/summary` | Thống kê mô tả |
| GET | `/silver/models` | Dự báo AR/MA/ARMA (daily, backend models) |
| POST | `/silver/sync` | Sync thủ công |
| POST | `/silver/sync/incremental` | Sync tăng dần |

---

### Bước 6 — Khởi động frontend

```bash
cd frontend && npm install && npm run dev
# Mở http://127.0.0.1:5173
```

---

## Lệnh tiện ích qua script.sh

```bash
./script.sh help                                  # Xem tất cả lệnh
./script.sh install                               # Cài dependencies
./script.sh db-up                                 # Khởi động PostgreSQL
./script.sh db-down                               # Tắt PostgreSQL
./script.sh db-status                             # Kiểm tra container
./script.sh api                                   # Chạy FastAPI
./script.sh summary curated 2020-01-01 2026-04-12 # Thống kê mô tả
./script.sh export-csv curated data/out.csv       # Xuất CSV
./script.sh export-xlsx raw data/out.xlsx         # Xuất Excel
./script.sh sync 2011-01-01 2026-04-12            # Sync vào DB
./script.sh test                                   # Chạy test suite
```

---

## Luồng tóm tắt

```
Alpha Vantage API
    ↓ (cache 24h)
data/raw/alpha_vantage/*.json
    ↓
SilverTimeSeriesPipeline
    ├── raw layer   (ngày giao dịch thực, không ffill)
    └── curated layer (chuỗi liên tục, ffill cuối tuần/ngày lễ)
         ↓
    PostgreSQL  →  FastAPI  →  React Frontend
         ↓
    CLI academic command
         ├── build_monthly_series()       resample daily→monthly
         ├── build_stationarity_report()  ADF test → d
         ├── build_decomposition_report() additive vs multiplicative
         ├── run_academic_suite()         SES / Holt / HW×2 / ARIMA
         ├── build_comparison_table()     MAE / RMSE / MAPE
         └── forecast_future_months()     12 tháng tới
              ↓
         outputs/charts/  (5 charts phân tích)
```

---

## Hai lớp dữ liệu

| Layer | Đặc điểm | Dùng cho |
|-------|----------|----------|
| `raw` | Chỉ ngày giao dịch thật, không ffill | Audit, đối chiếu nguồn |
| `curated` | Chuỗi liên tục, ffill ngày thiếu, gắn cờ `is_imputed` | Analytics, ML, dashboard |

Khi sync: `raw` giữ nguyên ngày giao dịch từ Alpha Vantage. `curated` reindex theo `pd.date_range` toàn lịch, ffill giá trị bằng ngày giao dịch gần nhất trước đó.

---

## Lỗi thường gặp

| Lỗi | Nguyên nhân | Xử lý |
|-----|------------|-------|
| Không lấy được dữ liệu | API key sai hoặc rate limit | Kiểm tra `ALPHAVANTAGE_API_KEY` trong `backend/.env` |
| `ModuleNotFoundError` | Chưa activate venv hoặc thiếu `PYTHONPATH` | `source .venv/bin/activate` + thêm `PYTHONPATH=backend/src` |
| `Not enough data` khi chạy HW model | Ít hơn 24 tháng training | Mở rộng `--start-date` ra trước hơn |
| PostgreSQL không kết nối | Container chưa chạy | `./script.sh db-up` |
| `academic` in cảnh báo statsmodels | Bình thường — convergence warning | Không ảnh hưởng kết quả |
