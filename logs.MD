# Logs

## 2026-04-11

### Bước: Refactor pipeline backend để tạo `curated` series và thêm cờ `is_imputed`
- Làm gì:
  Tách backend thành 2 lớp dữ liệu rõ ràng:
  `raw trading series` giữ nguyên các ngày giao dịch từ nguồn và `curated continuous daily series` là chuỗi ngày liên tục theo lịch.
  Ở lớp `curated`, chuẩn hoá `DatetimeIndex`, `reindex` theo `pd.date_range(start, end, freq="D")`, gắn cờ `is_weekend`, `is_missing_from_source`, `is_imputed`, và lưu thêm `source_date` để biết mỗi dòng fill đến từ ngày gốc nào.
- Để làm gì:
  Giải quyết đúng bài toán clean dữ liệu time series trước khi feature engineering và modeling.
  Tránh việc downstream hiểu nhầm trading-day series là calendar-day series.
  Tạo audit trail cho từng điểm dữ liệu được điền thêm.
- Lợi ích khi báo cáo:
  Có thể giải thích rõ:
  "Em không chỉ làm sạch dữ liệu, mà em đã xây dựng một pipeline tự động có khả năng theo dấu (audit trail) từng điểm dữ liệu bị thiếu."

### Bước: Cập nhật schema PostgreSQL và repository để lưu được cả `raw` và `curated`
- Làm gì:
  Mở rộng bảng dữ liệu với các cột `series_layer`, `source_date`, `is_imputed`, `is_weekend`, `is_missing_from_source`.
  Đổi khóa duy nhất sang `symbol + timeframe + series_layer + price_timestamp`.
  Khi sync dữ liệu, backend upsert cả hai layer thay vì chỉ một bảng phẳng.
- Để làm gì:
  Giữ được dữ liệu gốc và dữ liệu đã làm sạch song song.
  Không làm mất khả năng kiểm tra lại dữ liệu nguồn.
  Tránh ghi đè dữ liệu `raw` bởi dữ liệu `curated`.
- Lợi ích khi báo cáo:
  Có thể nói hệ thống không chỉ "lưu giá bạc", mà còn lưu được lịch sử xử lý dữ liệu một cách có kiểm soát.

### Bước: Cập nhật API và CLI để chọn `series_layer`, đồng thời hỗ trợ export Excel
- Làm gì:
  Bổ sung tham số `series_layer=raw|curated` cho API.
  Cập nhật CLI để export cả `.csv` lẫn `.xlsx`.
  Thêm dependency `openpyxl` để xuất Excel trực tiếp.
- Để làm gì:
  Cho phép xem riêng dữ liệu gốc và dữ liệu đã clean.
  Giúp đưa dữ liệu ra Excel nhanh để kiểm tra, trình bày, hoặc làm báo cáo.
- Lợi ích khi báo cáo:
  Có thể chứng minh pipeline không bị "hộp đen", vì dữ liệu đầu ra được quan sát và đối chiếu dễ dàng bằng Excel.

### Bước: Thêm test cho các case fill dữ liệu theo ngày lịch
- Làm gì:
  Viết test cho các tình huống:
  thiếu 1 ngày lễ,
  thiếu cuối tuần,
  khoảng đầu chuỗi không bị `ffill` sai,
  `return_1d` sau clean mang đúng nghĩa calendar-day.
- Để làm gì:
  Đảm bảo bước clean không chỉ chạy được mà còn đúng logic time series.
  Hạn chế lỗi lan sang bước feature engineering và modeling.
- Lợi ích khi báo cáo:
  Có thể nói phần xử lý dữ liệu đã được kiểm chứng bằng test thay vì làm thủ công hoặc dựa vào cảm tính.

### Bước: Đánh giá dataset hiện tại sau bước Clean & ffill
- Làm gì:
  Chạy đánh giá trực tiếp trên dữ liệu cache hiện tại cho giai đoạn `2020-01-01` đến `2026-04-05`, so sánh `raw` với `curated`.
  Kiểm tra số dòng trước và sau clean, số ngày được impute, tính liên tục của chuỗi, số giá trị null còn lại, và mức độ thay đổi thống kê lợi suất sau khi fill.
- Kết quả chính:
  `raw_rows = 2286`, `curated_rows = 2287`.
  Chuỗi `curated` đã liên tục hoàn toàn theo ngày lịch.
  Không còn null ở `price_usd`, `usd_vnd_rate`, `price_vnd`, `source_date`.
  Chỉ có `1` dòng được impute và đó là ngày cuối tuần `2023-01-21`.
  Không có ngày thường nào bị fill thêm trong khoảng dữ liệu hiện tại.
  Độ lệch chuẩn lợi suất gần như không đổi: `raw = 0.0194678`, `curated = 0.01946355`.
- Để làm gì:
  Xác nhận bước clean hiện tại không làm méo dữ liệu quá mức.
  Chứng minh curated dataset đã đủ liên tục để dùng cho feature engineering theo calendar-day.
- Lợi ích khi báo cáo:
  Có thể trình bày rằng pipeline clean đang can thiệp rất ít vào dữ liệu thực tế:
  "Trong giai đoạn phân tích chính, dữ liệu sau clean chỉ phải điền thêm 1 ngày cuối tuần bị thiếu, còn lại giữ nguyên dữ liệu nguồn."

### Bước: Xóa dữ liệu Docker PostgreSQL và nạp lại dataset vào container
- Làm gì:
  Reset Docker PostgreSQL bằng cách xóa volume cũ để tránh state không khớp với cấu hình hiện tại.
  Khởi động lại container với user/database đúng là `silver_user` và `silver_timeseri`.
  Do môi trường không cho gọi mạng ra Alpha Vantage và kết nối Python host -> Docker PostgreSQL không ổn định, đã dùng cache local để sinh 2 file CSV import-ready cho `raw` và `curated`.
  Copy các file này vào container và import tuần tự bằng `psql \\copy`.
- Kết quả chính:
  Container PostgreSQL được làm sạch và nạp lại thành công.
  Tổng số dòng trong bảng `silver_market_data` là `4573`.
  Trong đó:
  `raw = 2286` dòng,
  `curated = 2287` dòng.
- Để làm gì:
  Đảm bảo DB trong Docker khớp hoàn toàn với pipeline clean hiện tại.
  Giúp API/dashboard/backend sau đó đọc đúng dữ liệu mới nhất đã được chuẩn hoá.
- Lợi ích khi báo cáo:
  Có thể nói rõ backend không chỉ xử lý dữ liệu trên local notebook/file, mà dữ liệu đã được đưa vào hệ quản trị cơ sở dữ liệu phục vụ hệ thống backend thật.

### Bước: Tạo `script.sh` để hướng dẫn và chạy nhanh các lệnh backend
- Làm gì:
  Tạo file `script.sh` ở root repo để gom các lệnh backend thường dùng vào một entrypoint ngắn gọn.
  Script hiện hỗ trợ:
  `install`, `db-up`, `db-down`, `db-status`, `api`, `summary`, `export-csv`, `export-xlsx`, `sync`, `test`.
- Để làm gì:
  Giảm việc phải nhớ nhiều câu lệnh dài như `PYTHONPATH=backend/src python -m ...`.
  Giúp demo dự án và hướng dẫn sử dụng backend nhanh hơn.
  Thuận tiện cho việc nộp đồ án hoặc bàn giao code.
- Lợi ích khi báo cáo:
  Có thể nói hệ thống đã được đóng gói ở mức sử dụng thực tế:
  "Em đã chuẩn hoá cả phần vận hành backend bằng một script điều phối, giúp người dùng chạy các chức năng chính mà không cần nhớ chi tiết kỹ thuật của từng lệnh."

### Bước: Sửa curated pipeline để không lưu các ngày trước điểm dữ liệu đầu tiên
- Làm gì:
  Điều chỉnh logic tạo `pd.date_range(...)` cho `curated` để ngày bắt đầu thực tế là:
  `max(start_date người dùng yêu cầu, ngày dữ liệu đầu tiên có thật trong raw series)`.
  Vì vậy, các ngày nằm trước điểm dữ liệu đầu tiên sẽ không còn xuất hiện dưới dạng dòng `NULL` trong `curated`.
- Kết quả chính:
  Với khoảng `2011-01-01` đến `2026-04-11`, `curated` hiện bắt đầu từ `2011-06-01`.
  Số dòng `curated` tương ứng là `5429`, sạch hơn cho báo cáo vì không chứa phần đầu chuỗi rỗng.
- Để làm gì:
  Tránh làm dataset trông dài giả tạo do các ngày đầu kỳ chưa có dữ liệu thật.
  Giúp bảng và biểu đồ trong báo cáo phản ánh đúng giai đoạn dữ liệu quan sát được.
- Lợi ích khi báo cáo:
  Có thể nói rõ rằng pipeline không chỉ làm đầy khoảng trống, mà còn loại bỏ các đoạn thời gian trước khi dữ liệu thực sự bắt đầu, giúp chuỗi phân tích sạch và trung thực hơn.

### Bước: Cập nhật tài liệu để giải thích rõ `raw` và `curated`
- Làm gì:
  Bổ sung vào `README.md` và `docs/database.md` phần giải thích sự khác nhau giữa `raw` và `curated`, lý do số dòng có thể khác nhau, cùng ý nghĩa của các cờ audit như `is_imputed`, `is_missing_from_source`, `source_date`.
- Để làm gì:
  Tránh nhầm lẫn khi xem kết quả `sync` như:
  `raw = 5237`, `curated = 5428`.
  Giúp người đọc hiểu đây không phải lỗi dữ liệu, mà là hai lớp dữ liệu phục vụ hai mục đích khác nhau.
- Lợi ích khi báo cáo:
  Có thể giải thích rõ với thầy hoặc người chấm rằng hệ thống vừa giữ dữ liệu gốc để đối chiếu, vừa tạo lớp dữ liệu đã chuẩn hóa để phân tích chuỗi thời gian.

### Bước: Bổ sung README phần giải thích từng trường dữ liệu và vai trò biến
- Làm gì:
  Thêm vào `README.md` phần mô tả ý nghĩa từng cột trong dataset và phân loại:
  biến phụ thuộc,
  biến độc lập,
  biến dẫn xuất,
  biến audit.
- Để làm gì:
  Giúp người đọc hiểu dataset không chỉ ở mức tên cột, mà còn hiểu cột nào là mục tiêu dự báo, cột nào là dữ liệu đầu vào, cột nào chỉ phục vụ kiểm soát chất lượng.
- Lợi ích khi báo cáo:
  Có thể dùng trực tiếp phần này trong chương mô tả dữ liệu và thiết kế mô hình mà không cần tự diễn giải lại từ đầu.
