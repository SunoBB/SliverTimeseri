# Agent: Data Ingestion Flow

`Nhãn tài liệu:` Mô tả luồng nạp dữ liệu từ Alpha Vantage → pipeline → clean/ffill thành time series.

## Tổng quan

Luồng này chịu trách nhiệm lấy dữ liệu thô từ nguồn bên ngoài, chuẩn hóa và tạo ra hai lớp dataset (`raw` và `curated`) sẵn sàng cho storage và analytics.

```
AlphaVantageProvider
  ├── fetch_silver_history()   → giá bạc USD/ounce theo ngày
  └── fetch_usd_vnd_history()  → tỷ giá USD/VND theo ngày
          │
          ▼
SilverTimeSeriesPipeline
  ├── load_raw()       → gắn FX rate, cờ audit
  └── load_curated()   → reindex daily, ffill, cờ is_imputed
```

## Các file liên quan

| File | Vai trò |
|------|---------|
| `backend/src/silver_timeseri/providers/alpha_vantage.py` | Gọi API, cache response local |
| `backend/src/silver_timeseri/providers/base.py` | Interface chung cho provider |
| `backend/src/silver_timeseri/services/pipeline.py` | Biến records thành DataFrame, tạo raw/curated |

## Chi tiết từng bước

### 1. Provider: `AlphaVantageProvider`

- Gọi `GOLD_SILVER_HISTORY` để lấy giá bạc.
- Gọi `FX_DAILY` (USDVND) để lấy tỷ giá.
- Cache response tại `data/raw/alpha_vantage/` với TTL 24h (cấu hình qua `RAW_CACHE_TTL_HOURS`).
- Lọc theo `start_date` / `end_date` nếu có.
- Nếu cache còn hạn và `force_refresh=False`, bỏ qua gọi API.

### 2. Pipeline Raw: `load_raw()`

```python
# Chuẩn hóa index ngày
frame["date"] = pd.to_datetime(frame["date"], utc=False).dt.normalize()
frame = frame.sort_values("date").set_index("date")

# Ghép FX rate (left join theo ngày, ffill+bfill nếu lỗ nhỏ)
dataset = dataset.join(fx_frame[["usd_vnd_rate"]], how="left")
dataset["usd_vnd_rate"] = dataset["usd_vnd_rate"].ffill().bfill()

# Cờ audit
frame["is_missing_from_source"] = False
frame["is_imputed"] = False
frame["is_weekend"] = frame.index.dayofweek >= 5
```

Đặc điểm:
- Chỉ gồm những ngày provider thực sự trả về (ngày giao dịch).
- Không có hàng cho thứ 7, chủ nhật, ngày lễ nếu nguồn không trả.
- `ffill().bfill()` cho FX rate để lấp những ngày cuối tuần thiếu rate.

### 3. Pipeline Curated: `load_curated()`

```python
# Tạo index ngày liên tục từ min đến max của raw
full_index = pd.date_range(start=range_start, end=range_end, freq="D")
curated = raw.reindex(full_index)

# Đánh dấu ngày thiếu
curated["is_missing_from_source"] = ~curated.index.isin(raw.index)
curated["is_weekend"] = curated.index.dayofweek >= 5

# Forward-fill giá và tỷ giá (chỉ ffill, không bfill)
columns_to_ffill = ["price_usd", "price_silver_usd", "usd_vnd_rate", "source_date"]
curated[columns_to_ffill] = curated[columns_to_ffill].ffill()

# Cờ is_imputed: ngày bị thiếu nhưng đã được fill thành công
curated["is_imputed"] = curated["is_missing_from_source"] & curated["price_usd"].notna()
```

Đặc điểm:
- Mọi ngày trong calendar đều có hàng.
- Cuối tuần và ngày lễ được fill bằng giá giao dịch gần nhất trước đó.
- Chỉ dùng `ffill` (không bfill) để tránh dùng dữ liệu tương lai.
- `source_date` trỏ về ngày quan sát thật gần nhất, giúp truy vết nguồn gốc.

### 4. Finalize: `_finalize_frame()`

```python
# Quy đổi ounce → lượng (1 lượng = 37.5g, 1 ounce = 31.1035g)
OUNCE_TO_LUONG_RATIO = 37.5 / 31.1035  # ≈ 1.2055
price_vnd = price_usd * usd_vnd_rate * OUNCE_TO_LUONG_RATIO
```

- Tính `price_vnd` và `price_silver_vnd` cho mọi hàng.
- Gán `symbol = "XAGUSD"`, `timeframe`, `series_layer`.

## Điểm cần lưu ý

| Vấn đề | Hiện trạng |
|--------|-----------|
| Gap lớn > 5 ngày | ffill tiếp tục chạy, không có giới hạn số ngày fill |
| Thiếu FX rate | bfill xử lý được trong raw; curated chỉ ffill nên nếu ngày đầu tiên thiếu rate thì VND = NaN |
| Alpha Vantage rate limit | Cache 24h giảm thiểu; gói free ≈ 25 calls/ngày |
| Gói demo key | Không dùng được cho `GOLD_SILVER_HISTORY`, cần key thật |

## Cách kích hoạt

```bash
# Qua CLI
PYTHONPATH=backend/src python3 -m silver_timeseri.cli sync-db \
  --timeframe 1d --start-date 2020-01-01 --end-date 2026-04-12

# Qua API
POST /silver/sync?force_refresh=true

# Trong code
pipeline = SilverTimeSeriesPipeline(provider=AlphaVantageProvider(config))
df_raw = pipeline.load_raw(start_date="2020-01-01", end_date="2026-04-12")
df_curated = pipeline.load_curated(start_date="2020-01-01", end_date="2026-04-12")
```
