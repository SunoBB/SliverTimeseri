# Hướng Dẫn Sử Dụng Mô Hình Và Kiểm Thử

Tài liệu này gom toàn bộ cách dùng mô hình dự báo, kiểm thử, input/output của backend và cách frontend tiêu thụ kết quả.

## Phạm vi

Repo hiện có 2 nhóm mô hình:

- `Daily forecasting`: ARX, MA, ARMA trên chuỗi ngày, dùng trong API `/silver/models`, CLI `model` và trang Forecast của frontend.
- `Academic monthly forecasting`: SES, Holt Linear, Holt Damped, Holt-Winters Additive, Holt-Winters Multiplicative, ARIMA monthly, dùng trong CLI `academic`.

## Luồng tổng thể FE/BE

```text
Alpha Vantage / PostgreSQL
    -> backend/services/pipeline.py
    -> backend/services/app_service.py
    -> backend/analysis/*
    -> FastAPI /silver/*
    -> frontend/src/lib/api.js
    -> frontend/src/App.jsx + components/*
```

## 1. Backend Daily Models

Code chính:

- `backend/src/silver_timeseri/analysis/models.py`
- `backend/src/silver_timeseri/services/app_service.py`
- `backend/src/silver_timeseri/api.py`
- `backend/src/silver_timeseri/cli.py`

### 1.1 Mô hình nào đang chạy

`run_model_suite(...)` chạy 3 mô hình:

- `ARX`: autoregressive + technical indicators
- `MA`: `ARIMA(0, 0, q)`
- `ARMA`: `ARIMA(p, 0, q)`

### 1.2 Input của daily models

Input data frame cần tối thiểu:

- index là `DatetimeIndex`
- cột `price_usd`

Tùy theo đường gọi:

- API lấy data từ PostgreSQL qua `get_model_forecasts(...)`
- CLI lấy data qua `build_pipeline().load(...)`
- Hàm nội bộ có thể nhận `pd.DataFrame` trực tiếp

Feature engineering cho ARX:

- `price_usd_lag_1..p`
- `return_1d`
- `ma_5`, `ma_10`, `ma_20`
- `volatility_5`, `volatility_10`
- `momentum_5`

### 1.3 Train/Test split hiện tại

Daily models hiện dùng:

- `train = 80%`
- `test = 20%`
- giữ nguyên thứ tự thời gian, không shuffle

Logic nằm ở `split_train_test(frame, test_ratio=0.2)`.

Lưu ý:

- với ARX, tỷ lệ 80/20 được tính sau khi đã tạo lag và indicator rồi `dropna`
- vì vậy `test_size` thực tế có thể nhỏ hơn `20%` của raw frame ban đầu

### 1.4 Output của daily models

Mỗi model trả về `ModelRunResult.to_dict()` với cấu trúc:

```json
{
  "model_name": "ARMA",
  "train_size": 80,
  "test_size": 20,
  "metrics": {
    "mae": 0.412381,
    "rmse": 0.533912,
    "mape": 1.728144
  },
  "parameters": {
    "ar_order": 5,
    "ma_order": 3
  },
  "predictions": [
    {
      "date": "2026-04-07",
      "actual": 29.481,
      "predicted": 29.732,
      "error": -0.251,
      "lower_bound": 28.904,
      "upper_bound": 30.560,
      "lower_95": 28.904,
      "upper_95": 30.560,
      "band_width": 1.656,
      "interval_level": 0.95
    }
  ],
  "direction_backtest": {
    "samples": 20,
    "correct": 11,
    "accuracy": 55.0
  },
  "next_forecast": {
    "date": "2026-04-18",
    "predicted": 29.845,
    "lower_bound": 28.991,
    "upper_bound": 30.699,
    "lower_95": 28.991,
    "upper_95": 30.699,
    "band_width": 1.708,
    "interval_level": 0.95,
    "predicted_direction": "up"
  }
}
```

Ý nghĩa các trường chính:

- `metrics.mae`, `rmse`, `mape`: sai số trên tập test
- `predictions`: backtest từng điểm trong test set
- `direction_backtest.accuracy`: tỷ lệ đoán đúng hướng tăng/giảm
- `next_forecast`: dự báo ngày kế tiếp
- `lower_bound` / `upper_bound`: khoảng dự báo 95%

## 2. Backend API

Endpoint chính cho forecast daily:

- `GET /silver/models`

### 2.1 Input query của `/silver/models`

```text
start_date   optional, YYYY-MM-DD
end_date     optional, YYYY-MM-DD
timeframe    default "1d"
series_layer default "curated"
ar_order     default 5
ma_order     default 3
test_ratio   default 0.2
```

Ví dụ:

```bash
curl "http://127.0.0.1:8000/silver/models?start_date=2024-01-01&end_date=2026-04-17&ar_order=5&ma_order=3&test_ratio=0.2"
```

### 2.2 Output top-level của `/silver/models`

```json
{
  "rows": 720,
  "start_date": "2024-01-01",
  "end_date": "2026-04-17",
  "timeframe": "1d",
  "series_layer": "curated",
  "test_ratio": 0.2,
  "forecast_context": {
    "latest_data_date": "2026-04-17",
    "current_vn_date": "2026-04-17",
    "next_dataset_date": "2026-04-18",
    "missing_days": 0,
    "latest_data_status": "current",
    "forecast_target_type": "tomorrow",
    "forecast_target_label": "Du bao ngay mai 2026-04-18"
  },
  "latest_actual": {
    "date": "2026-04-17",
    "price_usd": 29.67,
    "price_vnd": 27894500.0
  },
  "model_rankings": {
    "best_by_mae": "ARMA",
    "best_by_direction": "ARX"
  },
  "models": []
}
```

## 3. CLI Daily Models

Command:

```bash
PYTHONPATH=backend/src ./.venv/bin/python -m silver_timeseri.cli model \
  --start-date 2024-01-01 \
  --end-date 2026-04-17 \
  --series-layer curated \
  --model-type all \
  --ar-order 5 \
  --ma-order 3 \
  --test-ratio 0.2
```

### 3.1 Input CLI

- `--model-type`: `ar`, `ma`, `arma`, `all`
- `--ar-order`: bậc AR
- `--ma-order`: bậc MA
- `--test-ratio`: tỷ lệ tập test cho daily models
- `--output-json`: đường dẫn file `.json` để lưu kết quả dễ đọc
- `--series-layer`: `raw` hoặc `curated`
- `--start-date`, `--end-date`

### 3.2 Output CLI

- in JSON ra stdout
- mỗi phần tử là `ModelRunResult.to_dict()`
- nếu truyền `--output-json`, CLI sẽ lưu cùng nội dung đó ra file

Ví dụ lưu ra file:

```bash
PYTHONPATH=backend/src ./.venv/bin/python -m silver_timeseri.cli model \
  --start-date 2024-06-01 \
  --end-date 2026-04-17 \
  --series-layer curated \
  --model-type all \
  --ar-order 5 \
  --ma-order 3 \
  --test-ratio 0.2 \
  --output-json outputs/models/daily_models_2024-06-01_2026-04-17.json
```

### 3.3 Cách đọc output JSON của lệnh `model`

Lệnh `model` trả về một mảng JSON. Mỗi phần tử trong mảng là kết quả của một mô hình:

- `ARX`
- `MA`
- `ARMA`

Ví dụ rút gọn:

```json
[
  {
    "model_name": "ARMA",
    "train_size": 400,
    "test_size": 100,
    "metrics": {
      "mae": 0.412381,
      "rmse": 0.533912,
      "mape": 1.728144
    },
    "parameters": {
      "ar_order": 5,
      "ma_order": 3,
      "aic": 210.231,
      "bic": 221.482
    },
    "predictions": [
      {
        "date": "2026-01-05",
        "actual": 29.481,
        "predicted": 29.732,
        "error": -0.251,
        "lower_bound": 28.904,
        "upper_bound": 30.560,
        "lower_95": 28.904,
        "upper_95": 30.560,
        "band_width": 1.656,
        "interval_level": 0.95
      }
    ],
    "direction_backtest": {
      "samples": 100,
      "correct": 56,
      "accuracy": 56.0,
      "actual_up": 54,
      "actual_down": 46,
      "predicted_up": 60,
      "predicted_down": 40,
      "recent_hits": []
    },
    "next_forecast": {
      "date": "2026-04-18",
      "predicted": 29.845,
      "lower_bound": 28.991,
      "upper_bound": 30.699,
      "lower_95": 28.991,
      "upper_95": 30.699,
      "band_width": 1.708,
      "interval_level": 0.95,
      "predicted_direction": "up"
    }
  }
]
```

Giải thích các field:

- `model_name`: tên mô hình đang xét.
- `train_size`: số quan sát dùng để huấn luyện.
- `test_size`: số quan sát dùng để kiểm tra sau khi chia 80/20.
- `metrics.mae`: sai số tuyệt đối trung bình. Càng thấp càng tốt.
- `metrics.rmse`: sai số bình phương trung bình lấy căn. Nhạy hơn với lỗi lớn.
- `metrics.mape`: sai số phần trăm trung bình. Dễ dùng khi viết nhận xét.
- `parameters`: tham số nội bộ của model. Dùng để giải thích cấu hình model, không phải phần chính để chọn model.
- `predictions`: từng dự báo trên tập test.
- `predictions[].actual`: giá thật ở ngày đó.
- `predictions[].predicted`: giá model dự báo.
- `predictions[].error`: `actual - predicted`. Âm nghĩa là model dự báo cao hơn thực tế.
- `predictions[].lower_bound`, `predictions[].upper_bound`: khoảng dự báo 95%.
- `predictions[].band_width`: độ rộng khoảng dự báo. Càng lớn thì mức bất định càng cao.
- `direction_backtest.samples`: số mẫu được kiểm tra hướng tăng/giảm.
- `direction_backtest.correct`: số lần model đoán đúng hướng.
- `direction_backtest.accuracy`: tỷ lệ đoán đúng hướng theo phần trăm.
- `next_forecast`: dự báo cho ngày kế tiếp sau điểm dữ liệu cuối cùng.
- `next_forecast.predicted`: point forecast, tức giá dự báo trung tâm.
- `next_forecast.predicted_direction`: hướng dự báo so với giá gần nhất, gồm `up`, `down`, `flat`.
- `next_forecast.lower_bound`, `next_forecast.upper_bound`: khoảng dự báo cho ngày kế tiếp.

Cách đọc nhanh để chọn model:

1. So sánh `metrics.mae` giữa các model. Model có `mae` thấp hơn thường là ứng viên tốt hơn.
2. Xem thêm `metrics.rmse` để biết model có hay mắc lỗi lớn không.
3. Nếu bạn quan tâm tín hiệu tăng/giảm hơn là giá tuyệt đối, xem `direction_backtest.accuracy`.
4. Khi đọc dự báo ngày kế tiếp, xem `next_forecast.predicted` cùng với `lower_bound` và `upper_bound`, không chỉ nhìn một con số duy nhất.

Ví dụ nhận xét:

- nếu `ARMA` có `mae` thấp nhất thì có thể nói `ARMA` tốt nhất theo sai số giá trị.
- nếu `ARX` có `direction_backtest.accuracy` cao nhất thì có thể nói `ARX` tốt hơn trong việc đoán hướng tăng/giảm.
- nếu `band_width` quá rộng thì nên đọc forecast thận trọng vì độ bất định cao.

Mẹo xem output dễ hơn:

```bash
cat outputs/models/daily_models_2024_2026.json | jq
```

Hoặc chỉ lấy phần quan trọng:

```bash
cat outputs/models/daily_models_2024_2026.json | jq '.[].{model_name, metrics, direction_backtest, next_forecast}'
```

## 4. Academic Monthly Models

Code chính:

- `build_monthly_series(...)`
- `build_stationarity_report(...)`
- `build_decomposition_report(...)`
- `run_academic_suite(...)`
- `forecast_future_months(...)`

Các mô hình monthly:

- `SES`
- `Holt Linear`
- `Holt Damped`
- `HW Additive`
- `HW Multiplicative`
- `ARIMA(p,d,q)`

### 4.1 Input CLI

```bash
PYTHONPATH=backend/src ./.venv/bin/python -m silver_timeseri.cli academic \
  --start-date 2011-01-01 \
  --end-date 2026-04-17 \
  --series-layer curated \
  --test-size 12 \
  --arima-p 1 \
  --arima-d 1 \
  --arima-q 1 \
  --n-months-forecast 12
```

Ở luồng academic:

- `test_size` vẫn là số tháng cuối
- không đổi sang `test_ratio`

### 4.2 Output academic

CLI in report JSON gồm:

- `n_monthly_obs`
- `test_size`
- `stationarity`
- `decomposition`
- `comparison_table`
- `best_model`
- `future_forecast`
- `charts_saved`

Ví dụ rút gọn:

```json
{
  "n_monthly_obs": 179,
  "test_size": 12,
  "best_model": "Holt Linear",
  "comparison_table": [
    {
      "model": "Holt Linear",
      "train_size": 167,
      "test_size": 12,
      "mae": 23.39,
      "rmse": 30.22,
      "mape": 34.41
    }
  ],
  "future_forecast": {
    "model": "Holt Linear",
    "n_months": 12,
    "forecast": [
      {
        "date": "2026-05-31",
        "predicted": 75.12
      }
    ]
  }
}
```

## 5. Frontend đang dùng forecast như thế nào

Code FE liên quan:

- `frontend/src/App.jsx`
- `frontend/src/lib/api.js`
- `frontend/src/components/forecast.jsx`
- `frontend/src/constants/reportPages.js`

### 5.1 Request từ frontend

Frontend gọi:

```js
requestJson("/silver/models", {
  start_date,
  end_date,
  ar_order: MODEL_AR_ORDER,
  ma_order: MODEL_MA_ORDER,
  test_ratio: MODEL_TEST_RATIO,
})
```

Giá trị mặc định hiện tại:

- `MODEL_AR_ORDER = 5`
- `MODEL_MA_ORDER = 3`
- `MODEL_TEST_RATIO = 0.2`

### 5.2 Component nào dùng output forecast

- `ForecastHero`: hiển thị model tốt nhất, `next_forecast`, CI 95%, hướng dự báo
- `ForecastChart`: vẽ `predictions` actual vs predicted trên test set
- `ForecastReportTable`: bảng so sánh `MAE`, direction accuracy, forecast từng model
- `ForecastContextNote`: hiển thị `forecast_context`

### 5.3 FE đang kỳ vọng trường nào từ BE

- `models[]`
- `model_name`
- `metrics.mae`
- `direction_backtest.accuracy`
- `predictions[].date`
- `predictions[].actual`
- `predictions[].predicted`
- `next_forecast.predicted`
- `next_forecast.predicted_direction`
- `next_forecast.lower_95`
- `next_forecast.upper_95`
- `forecast_context.latest_data_status`

## 6. Kiểm thử hiện có

Hiện repo có automated tests cho backend. Chưa có automated unit/integration tests riêng cho frontend; frontend đang được verify bằng `npm run build`.

### 6.1 Backend tests hiện có

- `backend/tests/test_curated_pipeline.py`
  - kiểm tra raw/curated layer
  - kiểm tra forward-fill ngày thiếu
  - kiểm tra cờ `is_imputed`, `is_weekend`, `is_missing_from_source`
- `backend/tests/test_models.py`
  - kiểm tra `run_model_suite(...)`
  - kiểm tra daily models đều trả `lower_bound`, `upper_bound`, `band_width`, `interval_level`
  - kiểm tra split thực tế là `20%` trên tập dữ liệu hiệu dụng của model
- `backend/tests/test_visualization.py`
  - kiểm tra các chart return/volatility được sinh ra đủ file

### 6.2 Cách chạy backend tests

```bash
PYTHONPATH=backend/src ./.venv/bin/python -m unittest \
  backend.tests.test_curated_pipeline \
  backend.tests.test_models \
  backend.tests.test_visualization
```

Kết quả verify gần nhất trong workspace này:

```text
Ran 7 tests in 14.793s
OK
```

### 6.3 Cách verify frontend

```bash
cd frontend
npm run build
```

Kết quả verify gần nhất trong workspace này:

```text
vite build
✓ built in 9.41s
```

## 7. Checklist thao tác đầy đủ

### 7.1 Chạy backend API

```bash
PYTHONPATH=backend/src ./.venv/bin/uvicorn silver_timeseri.api:app --reload
```

### 7.2 Chạy frontend

```bash
cd frontend
npm run dev
```

### 7.3 Chạy forecast daily từ API

```bash
curl "http://127.0.0.1:8000/silver/models?test_ratio=0.2&ar_order=5&ma_order=3"
```

### 7.4 Chạy forecast daily từ CLI

```bash
PYTHONPATH=backend/src ./.venv/bin/python -m silver_timeseri.cli model \
  --model-type all \
  --test-ratio 0.2 \
  --output-json outputs/models/daily_models.json
```

### 7.5 Chạy academic monthly

```bash
PYTHONPATH=backend/src ./.venv/bin/python -m silver_timeseri.cli academic \
  --test-size 12 \
  --n-months-forecast 12
```

## 8. Lưu ý quan trọng

- `daily models` và `academic models` là 2 luồng khác nhau, không dùng chung tham số chia test.
- `daily models` dùng `test_ratio`.
- `academic models` vẫn dùng `test_size` theo tháng.
- frontend Forecast page hiện chỉ dùng `daily models`.
- nếu đổi schema output của `/silver/models`, cần kiểm tra lại ít nhất:
  - `frontend/src/App.jsx`
  - `frontend/src/components/forecast.jsx`
  - `backend/tests/test_models.py`
