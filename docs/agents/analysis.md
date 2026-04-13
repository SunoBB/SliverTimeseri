# Agent: Analysis & Models Flow

`Nhãn tài liệu:` Mô tả luồng feature engineering, huấn luyện mô hình, tính metrics và sinh biểu đồ.

## Tổng quan

```
DataFrame (curated layer)
        │
        ▼
features.py  → tính chỉ báo kỹ thuật (MA, RSI, MACD, lag, volatility...)
        │
        ▼
models.py    → huấn luyện ARX / MA / ARMA, tính forecast ngày kế tiếp
        │
        ▼
metrics.py   → MAE, RMSE, MAPE, direction accuracy
        │
        ▼
visualization.py → sinh file PNG biểu đồ
```

## Các file liên quan

| File | Vai trò |
|------|---------|
| `backend/src/silver_timeseri/analysis/features.py` | Feature engineering |
| `backend/src/silver_timeseri/analysis/models.py` | ARX, MA, ARMA training + forecast |
| `backend/src/silver_timeseri/analysis/metrics.py` | Thống kê mô tả, lợi suất, drawdown |
| `backend/src/silver_timeseri/analysis/visualization.py` | Sinh PNG biểu đồ |

## Feature Engineering (`features.py`)

Các đặc trưng được tính từ cột `price_usd`:

| Feature | Mô tả |
|---------|-------|
| `price_usd_lag_1..N` | Giá trễ N ngày (AR features) |
| `return_1d` | Lợi suất ngày `(p_t - p_{t-1}) / p_{t-1}` |
| `ma_5`, `ma_10`, `ma_20` | Simple moving average |
| `volatility_5`, `volatility_10` | Rolling std của return |
| `momentum_5` | `price_t - price_{t-5}` |
| `silver_self_ratio` | `price_usd / price_silver_usd` (= 1 hiện tại, giữ cho mở rộng) |
| `rsi` | Relative Strength Index (14 ngày) |
| `macd`, `macd_signal` | MACD (12/26/9) |
| `bb_upper`, `bb_lower` | Bollinger Bands (20 ngày, ±2σ) |

## Mô hình (`models.py`)

### ARX (Autoregressive with eXogenous variables)

```
Input: price lags (p=5) + technical indicators
Method: OLS (np.linalg.lstsq)
Forecast: next-day predicted price + 95% CI từ residual std
```

Đây là mô hình đơn giản nhất nhưng thực tế thường cho direction accuracy tốt nhất do kết hợp nhiều features.

### MA (Moving Average)

```
ARIMA(0, 0, q) với q = MODEL_MA_ORDER (default: 3)
Method: statsmodels ARIMA
```

Chỉ dùng thành phần moving average của sai số.

### ARMA (AutoRegressive Moving Average)

```
ARIMA(p, 0, q) với p = MODEL_AR_ORDER (default: 5), q = MODEL_MA_ORDER (default: 3)
Method: statsmodels ARIMA
```

Kết hợp cả AR và MA, linh hoạt nhất trong bộ mô hình hiện tại.

### Train/Test split

- Mặc định `test_size = 30` (30 ngày cuối dùng để test).
- Huấn luyện trên toàn bộ dữ liệu trừ test set.
- Forecast cho **ngày kế tiếp sau dữ liệu cuối cùng** (không phải trong test set).

### Metrics trả về mỗi mô hình

```json
{
  "model_name": "ARX",
  "metrics": {"mae": 0.42, "rmse": 0.58, "mape": 1.3},
  "direction_backtest": {"accuracy": 56.7, "correct": 17, "total": 30},
  "next_forecast": {
    "date": "2026-04-13",
    "predicted": 32.15,
    "predicted_direction": "up",
    "lower_95": 31.72,
    "upper_95": 32.58
  }
}
```

## Thống kê mô tả (`metrics.py`)

Tính từ toàn bộ chuỗi trong khoảng `start_date` → `end_date`:

- `rows`: số quan sát
- `start_date`, `end_date`: khoảng thời gian thực tế
- `start_price_usd`, `end_price_usd`: giá đầu/cuối kỳ
- `mean_usd`, `median_usd`, `min_usd`, `max_usd`
- `avg_daily_return`: lợi suất ngày trung bình (%)
- `daily_return_std`: độ lệch chuẩn lợi suất ngày
- `max_drawdown`: mức sụt giảm cực đại từ đỉnh

## Visualization (`visualization.py`)

Sinh file PNG từ CLI command `charts`. Các loại biểu đồ:

| File output | Mô tả |
|-------------|-------|
| `01_trend_overview_line_chart.png` | Line chart xu hướng tổng thể |
| `02_trend_smoothing_moving_average_chart.png` | Đường MA làm mượt |
| `03_trend_zoom_aggregation_*.png` | Zoom theo năm/quý/tháng/tuần |
| `04_distribution_outlier_boxplot_chart.png` | Boxplot phân phối |
| `05_distribution_shape_histogram_chart.png` | Histogram |
| `06_distribution_density_kde_chart.png` | Density plot |
| `07_time_dependency_autocorrelation_chart.png` | Autocorrelation |
| `08_time_dependency_lag_scatter_chart.png` | Lag plot |
| `09_full_combo_chart.png` | Tổng hợp |

```bash
PYTHONPATH=backend/src python3 -m silver_timeseri.cli charts \
  --start-date 2024-01-01 --end-date 2024-12-31 \
  --output-dir outputs/charts
```

## Cách chạy từ CLI

```bash
# Huấn luyện tất cả mô hình
PYTHONPATH=backend/src python3 -m silver_timeseri.cli model \
  --timeframe 1d --model-type all \
  --ar-order 5 --ma-order 3 --test-size 30 \
  --start-date 2022-01-01 --end-date 2026-04-12

# Kết quả trả về JSON gồm metrics và next-day forecast của từng mô hình
```
