# Tài Liệu Database

`Nhãn tài liệu:` Nguồn chân lý cho schema, ý nghĩa cột, quy tắc lưu trữ và khuyến nghị mở rộng database.

`Không lặp lại ở README:` mọi chi tiết về schema và data dictionary nên cập nhật tại file này trước.

## 1. Mục tiêu của tầng dữ liệu

Bảng PostgreSQL hiện tại không chỉ là nơi lưu raw dump từ API. Nó được thiết kế để:

- Lưu time series theo mốc thời gian chuẩn
- Hỗ trợ analytics theo ngày
- Phục vụ feature engineering và huấn luyện mô hình
- Cho phép sync lặp lại bằng cơ chế upsert
- Phân biệt rõ dữ liệu gốc và dữ liệu đã chuẩn hóa

## 2. Bảng hiện tại

Tên bảng mặc định:

```text
silver_market_data
```

Schema thực tế đang được khởi tạo tại [init.sql](/home/suno/Github/Gold_TimeSeri/backend/docker/postgres/init.sql).

### Các cột chính

- `id`: khóa chính nội bộ
- `symbol`: mã tài sản, hiện tại là `XAGUSD`
- `timeframe`: khung thời gian, hiện tại là `1d`
- `series_layer`: lớp dữ liệu, `raw` hoặc `curated`
- `price_timestamp`: mốc thời gian của bản ghi
- `source_date`: ngày nguồn gần nhất dùng để tạo ra dòng hiện tại
- `price_usd`: giá bạc theo `USD/ounce`
- `price_vnd`: giá bạc quy đổi theo `VND/lượng`
- `price_silver_usd`: giá bạc theo `USD/ounce`
- `price_silver_vnd`: giá bạc quy đổi theo `VND/lượng`
- `usd_vnd_rate`: tỷ giá `USD/VND`
- `is_imputed`: cờ cho biết dòng này được pipeline điền thêm
- `is_weekend`: cờ cho biết ngày này rơi vào cuối tuần
- `is_missing_from_source`: cờ cho biết ngày này không có trong dữ liệu nguồn
- `created_at`: thời điểm tạo bản ghi
- `updated_at`: thời điểm cập nhật bản ghi

### Khóa duy nhất

```sql
UNIQUE (symbol, timeframe, series_layer, price_timestamp)
```

Đây là khóa unique đúng với implementation hiện tại và là cơ sở để upsert không ghi đè nhầm giữa `raw` và `curated`.

## 3. Hai lớp dữ liệu: `raw` và `curated`

Hệ thống hiện lưu song song 2 lớp dữ liệu trong cùng một bảng, phân biệt bằng `series_layer`.

### `raw`

- Chỉ gồm những ngày provider thực sự trả về
- Dùng để đối chiếu với dữ liệu nguồn
- Phù hợp cho kiểm tra ingest và audit

### `curated`

- Được chuẩn hóa thành chuỗi ngày liên tục
- Tạo bằng cách chuẩn hóa index ngày, `reindex` theo `pd.date_range(..., freq="D")`, rồi `ffill` sau ngày quan sát đầu tiên
- Có thêm các cờ audit như `is_imputed`, `is_weekend`, `is_missing_from_source`
- Phù hợp hơn cho thống kê, feature engineering và mô hình theo calendar-day

Ví dụ:

```json
{
  "rows_upserted_by_layer": {
    "raw": 5237,
    "curated": 5428
  }
}
```

Ý nghĩa:

- `raw` có `5237` ngày quan sát thật
- `curated` có `5428` dòng sau bước chuẩn hóa thành chuỗi ngày liên tục

## 4. Data Dictionary rút gọn

### Nhóm định danh

- `id`
- `symbol`
- `timeframe`
- `series_layer`

### Nhóm thời gian

- `price_timestamp`
- `source_date`
- `created_at`
- `updated_at`

### Nhóm giá trị kinh tế

- `price_usd`
- `price_vnd`
- `price_silver_usd`
- `price_silver_vnd`
- `usd_vnd_rate`

### Nhóm audit

- `is_imputed`
- `is_weekend`
- `is_missing_from_source`

## 5. Các cột dẫn xuất

Hiện tại bảng lưu đồng thời:

- `price_usd`
- `usd_vnd_rate`
- `price_vnd`

Và tương tự cho cặp:

- `price_silver_usd`
- `price_silver_vnd`

Quan hệ quy đổi:

```text
price_vnd = price_usd * usd_vnd_rate * (37.5 / 31.1035)
price_silver_vnd = price_silver_usd * usd_vnd_rate * (37.5 / 31.1035)
```

Đánh đổi:

- Ưu điểm: query nhanh hơn, thuận tiện cho dashboard và ML
- Nhược điểm: tăng dư thừa dữ liệu và cần giữ tính nhất quán khi ghi

Kết luận cho giai đoạn hiện tại:

- Giữ các cột dẫn xuất này trong bảng
- Xem chúng là `materialized/derived fields`
- Chỉ cho pipeline ETL ghi vào các cột này

## 6. Precision hiện tại

```text
price_usd NUMERIC(10,2)
price_vnd NUMERIC(15,0)
price_silver_usd NUMERIC(10,2)
price_silver_vnd NUMERIC(15,0)
usd_vnd_rate NUMERIC(10,2)
```

Thiết kế này phù hợp với mục tiêu ứng dụng hiện tại. Nếu sau này cần nghiên cứu với độ chính xác cao hơn, có thể tăng precision cho giá USD hoặc giữ thêm raw JSON ngoài tầng cache file.

## 7. Gợi ý query và feature engineering

### Moving average 7 ngày

```sql
SELECT
  price_timestamp,
  price_usd,
  AVG(price_usd) OVER (
    ORDER BY price_timestamp
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  ) AS ma7
FROM silver_market_data
WHERE symbol = 'XAGUSD'
  AND timeframe = '1d'
  AND series_layer = 'curated'
ORDER BY price_timestamp;
```

### Rolling volatility gần đúng

```sql
SELECT
  price_timestamp,
  price_usd,
  STDDEV(price_usd) OVER (
    ORDER BY price_timestamp
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  ) AS rolling_std_7
FROM silver_market_data
WHERE symbol = 'XAGUSD'
  AND timeframe = '1d'
  AND series_layer = 'curated'
ORDER BY price_timestamp;
```

### Daily return

```sql
SELECT
  price_timestamp,
  price_usd,
  (
    price_usd - LAG(price_usd) OVER (ORDER BY price_timestamp)
  ) / NULLIF(LAG(price_usd) OVER (ORDER BY price_timestamp), 0) AS return_1d
FROM silver_market_data
WHERE symbol = 'XAGUSD'
  AND timeframe = '1d'
  AND series_layer = 'curated'
ORDER BY price_timestamp;
```

## 8. Hướng mở rộng

Nếu dữ liệu tăng lớn hơn hoặc tiến gần production, có thể cân nhắc:

- Partition theo `price_timestamp`
- Bổ sung index chuyên cho truy vấn theo thời gian
- Tạo materialized view cho feature engineering
- Tạo layer riêng cho train/test snapshots
- Thêm versioning cho feature set

## 9. Event Layer

Hệ thống hiện có thêm bảng `economic_events` để lưu các sự kiện kinh tế hoặc địa chính trị ảnh hưởng mạnh tới giá bạc.

Mục đích:

- tách event metadata khỏi bảng giá chính
- cho phép một ngày có nhiều sự kiện
- hỗ trợ frontend hiển thị marker, tooltip, filter category và panel sự kiện

Các cột chính:

- `event_key`
- `event_date`
- `end_date`
- `title`
- `category`
- `impact_level`
- `impact_score`
- `summary`
- `price_impact_summary`
- `is_range_event`

API đọc event hiện có:

- `GET /silver/events`

## 10. Kết luận

Schema hiện tại phù hợp cho giai đoạn đồ án, demo và phân tích cơ bản:

- đủ rõ để lưu time series
- đủ thực dụng cho dashboard và ML
- đủ linh hoạt để mở rộng sau này

Điểm quan trọng nhất cần giữ nhất quán trong tài liệu là:

- database đang có `raw` và `curated`
- upsert dùng khóa `symbol + timeframe + series_layer + price_timestamp`
- `price_vnd` và `price_silver_vnd` là cột dẫn xuất, không nên cập nhật tay
