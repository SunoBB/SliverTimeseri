# Báo cáo Phân tích Chuỗi Thời gian Giá Bạc (XAGUSD)
> Môn: Phân Tích Chuỗi Thời Gian · Mã môn: 700902303  
> Giảng viên: Phan Văn Cần · Trường ĐH Y Tế Công Cộng

---

## CẤU TRÚC BÁO CÁO (tóm tắt các chương)

| Chương | Tiêu đề | Nội dung chính |
|--------|---------|----------------|
| 1 | Giới thiệu | Đặt vấn đề, mục tiêu, phạm vi nghiên cứu |
| 2 | Dữ liệu | Nguồn, biến số, tiền xử lý, thống kê mô tả |
| 3 | Đặc điểm chuỗi thời gian | Trend, phân phối, tự tương quan, tính dừng |
| 4 | Lựa chọn mô hình | Phân rã chuỗi → căn cứ chọn mô hình |
| 5 | Huấn luyện & đánh giá | Train/test split, MAE/RMSE/MAPE, so sánh |
| 6 | Dự báo | 1 ngày · 7 ngày · 30 ngày + khoảng tin cậy |
| 7 | Kết luận | Mô hình tốt nhất, hạn chế, hướng mở rộng |
| PHỤ LỤC | A → E | Bảng số liệu + toàn bộ biểu đồ |

---

---

# PHỤ LỤC

---

## PHỤ LỤC A — DỮ LIỆU VÀ BIẾN SỐ

### A.1 Nguồn và cấu trúc file

| Mục | Chi tiết |
|-----|---------|
| **Nguồn** | Alpha Vantage API — Commodity: Silver Daily |
| **File gốc** | `data/raw/alpha_vantage/commodity_silver_daily.json` |
| **Tỷ giá** | `data/raw/alpha_vantage/fx_usd_vnd_daily.json` |
| **Khoảng thời gian** | 2011-06 → 2026-04 (phân tích dùng 2022-01 → 2026-04) |
| **Tần suất** | Daily (ngày giao dịch, không bao gồm cuối tuần & ngày lễ) |
| **Lưu trữ** | PostgreSQL — bảng `silver_market_data` |

---

### A.2 Bảng mô tả các biến

| Biến | Kiểu | Đơn vị | Mô tả |
|------|------|--------|-------|
| `price_timestamp` | datetime | — | Ngày giao dịch (DatetimeIndex) |
| `price_usd` | float | USD/oz | Giá bạc theo USD/ounce troy ← **biến phân tích chính** |
| `price_vnd` | float | VND/lượng | Giá bạc quy đổi sang VND/lượng |
| `usd_vnd_rate` | float | VND/USD | Tỷ giá hối đoái ngày tương ứng |
| `price_silver_usd` | float | USD/oz | Giá bạc gốc từ nguồn (chưa quy đổi) |
| `is_imputed` | bool | — | `True` nếu ô giá được nội suy (cuối tuần/lễ) |
| `is_weekend` | bool | — | `True` nếu là thứ 7 hoặc chủ nhật |
| `is_missing_from_source` | bool | — | `True` nếu ngày đó nguồn không trả về giá |
| `series_layer` | str | — | `raw` (gốc) hoặc `curated` (đã xử lý, ffill) |

> **Biến phân tích:** `price_usd` (daily, curated layer — đã nội suy tuyến tính các ngày thiếu)

---

### A.3 Thống kê mô tả tóm tắt

*(Lấy từ endpoint `/silver/summary` — giai đoạn 2022-01 → 2026-04)*

| Chỉ số | Giá trị |
|--------|---------|
| Số quan sát | ~1 550 ngày |
| Giá thấp nhất | ~17 USD/oz |
| Giá cao nhất | ~94 USD/oz |
| Giá trung bình | ~26 USD/oz |
| Độ lệch chuẩn | ~12 USD/oz |
| Max Drawdown | ~−40% |
| Giá gần nhất | ~76 USD/oz (2026-04) |

---

### A.4 Tiền xử lý dữ liệu

```
Bước 1: Gọi API Alpha Vantage → JSON
Bước 2: Parse JSON → DataFrame (DatetimeIndex)
Bước 3: Forward-fill (ffill) các ngày cuối tuần/lễ
         → đảm bảo chuỗi liên tục không có khoảng trống
Bước 4: Lưu 2 layer vào PostgreSQL:
         · raw    — dữ liệu gốc từ nguồn
         · curated — đã ffill, dùng cho phân tích
Bước 5: Resample monthly (ME) cho mô hình học thuật
         (SES, Holt, HW, ARIMA)
```

---

---

## PHỤ LỤC B — PHÂN TÍCH KHÁM PHÁ DỮ LIỆU (EDA)

> **Thư mục biểu đồ:** `outputs/charts/2022-01_2026-04/`

---

### B.1 Biểu đồ đường tổng quan xu hướng

**File:** `01_trend_overview_line_chart.png`

| Mục | Nội dung |
|-----|---------|
| **Trục X** | Thời gian (daily) |
| **Trục Y** | Giá USD/oz |
| **Thuật toán** | Vẽ thẳng dữ liệu gốc (`ax.plot`) |

**Nhận xét cần viết:**
- Chuỗi có **xu hướng tăng dài hạn** rõ rệt (từ ~$22 năm 2022 lên ~$76 năm 2026)
- Giai đoạn 2022–2023: giá dao động ổn định trong khoảng 18–26 USD/oz
- Giai đoạn 2024–2025: tăng trưởng mạnh, đặc biệt từ Q4/2024
- Không có dấu hiệu seasonality rõ ràng trên daily (cần resample monthly để thấy)
- Có những đỉnh nhọn bất thường → sự kiện thị trường (Fed policy, địa chính trị)

---

### B.2 Trung bình động (Moving Average)

**File:** `02_trend_smoothing_moving_average_chart.png`

| Mục | Nội dung |
|-----|---------|
| **Đường xanh** | Giá gốc daily |
| **Đường cam** | Rolling Mean (window = 7 ngày) |
| **Thuật toán** | `series.rolling(window=7).mean()` |

**Nhận xét cần viết:**
- Đường trung bình động làm mượt nhiễu ngắn hạn → thấy rõ trend dài hạn
- Giai đoạn đường cam nằm dưới đường xanh → **giá đang tăng** (momentum dương)
- Hai đường cắt nhau tạo tín hiệu đảo chiều (crossing points)
- Phương sai tăng dần từ 2024 → biến động giá lớn hơn → rủi ro tăng

---

### B.3 Gộp dữ liệu theo tuần

**File:** `03_trend_zoom_aggregation_w_chart.png`

| Mục | Nội dung |
|-----|---------|
| **Thuật toán** | `series.resample("W").mean()` |
| **Điểm dữ liệu** | ~52 điểm/năm (thay vì ~250 điểm/năm) |

**Nhận xét cần viết:**
- Sau resample tuần: xu hướng tăng càng rõ ràng hơn
- Giảm thiểu nhiễu vi động (microvolatility) ngày giao dịch
- Không có pattern tuần rõ ràng → không có seasonality weekly

---

### B.4 Boxplot phân phối theo năm

**File:** `04_distribution_outlier_boxplot_chart.png`

| Mục | Nội dung |
|-----|---------|
| **Thuật toán** | Boxplot (Q1, Q2, Q3, IQR, outliers) |
| **Nhóm** | Theo năm (2022, 2023, 2024, 2025, 2026) |

**Nhận xét cần viết:**
- Trung vị giá tăng qua từng năm → trend tăng được xác nhận
- 2024–2025: hộp rộng hơn → biến động trong năm lớn hơn
- Outlier xuất hiện chủ yếu ở 2025–2026 (giá đột biến lên ~$94)
- 2022–2023: phân phối hẹp và tập trung → giai đoạn giá ổn định

---

### B.5 Histogram phân phối tần suất

**File:** `05_distribution_frequency_histogram_chart.png`

| Mục | Nội dung |
|-----|---------|
| **Thuật toán** | `plt.hist(series, bins=10)` |

**Nhận xét cần viết:**
- Phân phối **lệch phải** (right-skewed): đa số quan sát tập trung ở vùng giá thấp (18–30 USD)
- Đuôi dài bên phải → có giai đoạn giá rất cao (bong bóng/đột biến 2025–2026)
- Hình dạng **bimodal** (hai đỉnh): một cụm ~20–25 USD và một cụm ~30–35 USD → chuỗi trải qua hai "chế độ giá" khác nhau
- Không phân phối chuẩn → cần chú ý khi dùng các mô hình giả định normality

---

### B.6 Mật độ xác suất KDE

**File:** `06_distribution_density_kde_chart.png`

| Mục | Nội dung |
|-----|---------|
| **Thuật toán** | Kernel Density Estimation (Gaussian kernel) |

**Nhận xét cần viết:**
- Xác nhận phân phối lệch phải từ histogram
- Đỉnh chính ~22 USD → vùng giá xuất hiện nhiều nhất trong lịch sử
- Đuôi phải kéo dài → xác suất giá tăng cao không bằng 0
- Đường cong không đối xứng → distribution không phải normal

---

### B.7 Tự tương quan (Autocorrelation)

**File:** `07_time_dependency_autocorrelation_chart.png`

| Mục | Nội dung |
|-----|---------|
| **Thuật toán** | `pandas.plotting.autocorrelation_plot(series)` |
| **Ý nghĩa** | `r(k) = Corr(y_t, y_{t-k})` |

**Nhận xét cần viết (QUAN TRỌNG):**
- ACF giảm **rất chậm** từ ~1.0 và mãi không về 0 → chuỗi **không dừng** (non-stationary)
- Tự tương quan cao ở nhiều lag → giá hôm nay phụ thuộc mạnh vào giá các ngày trước
- Kết luận: **cần lấy sai phân** (differencing, d ≥ 1) trước khi dùng ARIMA
- Tín hiệu rõ ràng cho việc dùng mô hình AR hoặc ARIMA

---

### B.8 Lag Plot (Tương quan trễ)

**File:** `08_time_dependency_lag_relationship_chart.png`

| Mục | Nội dung |
|-----|---------|
| **Thuật toán** | `pandas.plotting.lag_plot(series, lag=1)` |
| **Trục X** | Giá ngày hôm qua `y_{t-1}` |
| **Trục Y** | Giá ngày hôm nay `y_t` |

**Nhận xét cần viết:**
- Các điểm tập trung dọc theo **đường chéo 45°** → tương quan tuyến tính rất mạnh (r ≈ 0.99)
- Giá hôm nay ≈ giá hôm qua → chuỗi "trơn" (sticky), ít nhảy lớn giữa các ngày
- Tính chất này là căn cứ chính để dùng mô hình **Autoregressive (AR/ARX)**
- Một số điểm lệch xa đường chéo → ngày có biến động đột biến (news events)

---

### B.9 Biểu đồ tổng hợp 2×2

**File:** `09_analysis_summary_combo_chart.png`

> Ghép 4 biểu đồ: Đường giá gốc · Trung bình động · Histogram · Boxplot  
> Dùng cho **tổng quan nhanh** trong báo cáo. Đặt ở đầu phần EDA.

---

---

## PHỤ LỤC C — KIỂM ĐỊNH TÍNH DỪNG VÀ PHÂN RÃ CHUỖI

### C.1 Kết quả kiểm định ADF (Augmented Dickey-Fuller)

**Thuật toán:** `statsmodels.tsa.stattools.adfuller(series, autolag="AIC")`

**H₀ (null hypothesis):** Chuỗi có đơn vị gốc (unit root) → không dừng  
**H₁ (alternative):** Chuỗi dừng (stationary)  
**Quy tắc:** Nếu p-value < 0.05 → bác bỏ H₀ → **chuỗi dừng**

| Chuỗi kiểm định | ADF Statistic | p-value | Kết luận | d đề xuất |
|-----------------|---------------|---------|----------|-----------|
| Giá gốc (levels) | > −3.0 | > 0.05 | ❌ Không dừng | — |
| Sai phân bậc 1 (diff-1) | < −3.0 | < 0.05 | ✅ Dừng | **d = 1** |

> **Kết luận:** Chuỗi giá bạc daily không dừng ở dạng gốc.  
> Sau khi lấy sai phân bậc 1 → chuỗi dừng → dùng **d = 1** cho ARIMA(p, **1**, q).

*(Điền giá trị thực tế từ kết quả chạy endpoint `/silver/stationarity`)*

---

### C.2 Phân rã chuỗi — Mô hình Cộng (Additive)

**File:** `outputs/charts/11_decomposition_additive_chart.png`

| Mục | Nội dung |
|-----|---------|
| **Thuật toán** | `seasonal_decompose(series_monthly, model='additive', period=12)` |
| **Dữ liệu** | Monthly (resample từ daily → `ME`) |
| **4 thành phần** | Observed · Trend · Seasonal · Residual |

**Công thức mô hình cộng:**
```
Y_t = Trend_t + Seasonal_t + Residual_t
```

**Nhận xét:**
- **Trend:** tăng đều từ 2022, tăng mạnh từ 2024 → xu hướng tích cực
- **Seasonal:** biên độ dao động **ổn định** theo thời gian → phù hợp mô hình cộng
- **Residual:** nếu phân tán đều → mô hình cộng phù hợp

---

### C.3 Phân rã chuỗi — Mô hình Nhân (Multiplicative)

**File:** `outputs/charts/11_decomposition_multiplicative_chart.png`

| Mục | Nội dung |
|-----|---------|
| **Thuật toán** | `seasonal_decompose(series_monthly, model='multiplicative', period=12)` |

**Công thức mô hình nhân:**
```
Y_t = Trend_t × Seasonal_t × Residual_t
```

**Nhận xét:**
- **Seasonal:** biên độ **tăng theo mức giá** → seasonal thay đổi tỷ lệ theo trend
- Dùng `seasonal.std()` của cả 2 để so sánh → mô hình có std nhỏ hơn được chọn

---

### C.4 Tiêu chí chọn mô hình phân rã

| Tiêu chí | Mô hình Cộng | Mô hình Nhân |
|----------|-------------|-------------|
| Seasonal `std` | *(điền giá trị)* | *(điền giá trị)* |
| Phù hợp khi | Biên độ seasonal ổn định | Biên độ seasonal tỷ lệ theo trend |
| **Kết luận** | *(chọn mô hình có std nhỏ hơn)* | — |

---

---

## PHỤ LỤC D — HUẤN LUYỆN VÀ ĐÁNH GIÁ MÔ HÌNH

### D.1 Phân chia tập train/test

| Thông số | Giá trị |
|----------|---------|
| **Test ratio** | 20% cuối chuỗi |
| **Train** | 80% đầu (~1 240 ngày) |
| **Test** | 20% cuối (~310 ngày) |
| **Lý do** | Tránh data leakage — không dùng dữ liệu tương lai để train |

> **Nguyên tắc:** Metrics (MAE/RMSE/MAPE) được tính **trên tập test**, không dùng training error để tránh overfitting.

---

### D.2 Biểu đồ Actual vs Predicted — Mô hình ARX

> *Chụp màn hình từ tab Backtesting — chọn chart ARX*

| Mục | Nội dung |
|-----|---------|
| **Đường xanh lá** | Giá thực tế (actual) trên tập test |
| **Đường đỏ** | Giá dự báo của ARX trên tập test |
| **Mô hình** | AutoRegressive with eXogenous variables |
| **Features** | 5 lags giá + 7 chỉ báo kỹ thuật (MA-5, MA-10, MA-20, Volatility-5, Volatility-10, Return-1d, Momentum-5) |

**Nhận xét:**
- Đường dự báo bám sát đường thực tế → ARX capture được trend tốt
- Sai số lớn nhất ở các điểm đảo chiều đột ngột

---

### D.3 Biểu đồ Actual vs Predicted — Mô hình MA

> *Chụp màn hình từ tab Backtesting — chọn chart MA*

| Mục | Nội dung |
|-----|---------|
| **Mô hình** | Moving Average (MA) — `ARIMA(0, 0, q)` |
| **Tham số** | ma_order = 3 |

**Nhận xét:**
- MA phụ thuộc vào trung bình lịch sử → phản ứng chậm hơn ARX
- Dự báo hội tụ về giá trị trung bình sau nhiều bước → phù hợp dự báo ngắn hạn

---

### D.4 Biểu đồ Actual vs Predicted — Mô hình ARMA

> *Chụp màn hình từ tab Backtesting — chọn chart ARMA*

| Mục | Nội dung |
|-----|---------|
| **Mô hình** | AutoRegressive Moving Average — `ARIMA(p, 0, q)` |
| **Tham số** | ar_order = 5, ma_order = 3 |

**Nhận xét:**
- Kết hợp thành phần AR và MA → linh hoạt hơn MA đơn thuần
- Hiệu suất nằm giữa MA và ARX

---

### D.5 Bảng so sánh hiệu suất mô hình

*(Lấy từ bảng Comparison Table trong tab Backtesting)*

| Xếp hạng | Mô hình | MAE | RMSE | MAPE (%) | Direction % |
|-----------|---------|-----|------|----------|-------------|
| ★ 1 | ARX | *(điền)* | *(điền)* | *(điền)* | *(điền)* |
| 2 | ARMA | *(điền)* | *(điền)* | *(điền)* | *(điền)* |
| 3 | MA | *(điền)* | *(điền)* | *(điền)* | *(điền)* |

**Giải thích các độ đo:**

| Độ đo | Công thức | Ý nghĩa |
|-------|-----------|---------|
| MAE | `mean(|actual - predicted|)` | Sai số trung bình tuyệt đối (USD/oz) |
| RMSE | `sqrt(mean((actual - predicted)²))` | Phạt lỗi lớn nặng hơn MAE |
| MAPE | `mean(|error/actual|) × 100` | Sai số tương đối (%), độc lập đơn vị |
| Direction % | `correct_direction / total × 100` | Tỷ lệ dự đoán đúng hướng tăng/giảm |

> **Tiêu chí chọn mô hình:** Ưu tiên **MAPE thấp nhất** → độ đo không phụ thuộc đơn vị, phù hợp so sánh.  
> Xác nhận thêm bằng Direction % → quan trọng trong trading (đúng hướng hơn đúng giá trị).

---

### D.6 Biểu đồ Radar so sánh mô hình

> *Chụp màn hình từ tab Forecast — biểu đồ Radar*

**4 trục radar (chuẩn hóa 0–100, cao hơn = tốt hơn):**

| Trục | Ý nghĩa | Cách tính |
|------|---------|-----------|
| MAE Score | Sai số trung bình nhỏ hơn → score cao hơn | `(1 − (mae − min) / (max − min)) × 100` |
| RMSE Score | Tương tự MAE | Công thức inverted |
| MAPE Score | Sai số % nhỏ hơn → score cao hơn | Công thức inverted |
| Direction % | Hit rate hướng tăng/giảm | `accuracy / max_accuracy × 100` |

**Màu sắc mô hình:**
- 🔵 **ARX** — xanh dương (best model)
- 🟣 **ARMA** — tím
- ⚫ **MA** — xám

**Nhận xét:**
- Vùng xanh (ARX) lớn nhất → ARX vượt trội trên cả 4 tiêu chí
- Direction % của ARMA có thể cao hơn ARX → ARMA dự báo hướng tốt hơn trong một số giai đoạn

---

---

## PHỤ LỤC E — KẾT QUẢ DỰ BÁO

### E.1 Dự báo 1 ngày tới (Next-Day Forecast)

> *Lấy từ tab Forecast → chọn 1D*

| Mục | Giá trị |
|-----|---------|
| **Ngày dự báo** | *(điền ngày T+1)* |
| **Mô hình đề xuất** | ARX (MAE thấp nhất) |
| **Giá dự báo** | *(điền)* USD/oz |
| **Hướng** | ↑ Tăng / ↓ Giảm / → Đi ngang |
| **∆ so với giá hiện tại** | *(điền)* USD |
| **Khoảng tin cậy 95%** | [*(lower)*, *(upper)*] USD/oz |
| **Consensus (3 mô hình)** | *(điền)* USD/oz |

**Bảng dự báo đầy đủ 3 mô hình:**

| Mô hình | Giá dự báo | Hướng | CI 95% | MAE | Direction % |
|---------|-----------|-------|--------|-----|-------------|
| ARX ★ | *(điền)* | *(điền)* | [*, *] | *(điền)* | *(điền)* |
| ARMA | *(điền)* | *(điền)* | [*, *] | *(điền)* | *(điền)* |
| MA | *(điền)* | *(điền)* | [*, *] | *(điền)* | *(điền)* |

---

### E.2 Biểu đồ dự báo 7 ngày tới

> *Chụp màn hình tab Forecast → chọn 7D*

**File ảnh:** *(chụp màn hình ForecastMultiDayChart — 7D)*

| Thành phần | Mô tả |
|-----------|-------|
| **Điểm đen** | Giá thực tế gần nhất (anchor point) |
| **Đường xanh dương** 🔵 | ARX forecast 7 ngày |
| **Đường tím** 🟣 | ARMA forecast 7 ngày |
| **Đường xám** ⚫ | MA forecast 7 ngày |
| **Đường vàng** 🟡 | Consensus (trọng số inverse-MAE) |
| **Vùng mờ** | Khoảng tin cậy 95% của từng mô hình |

**Bảng dự báo 7 ngày — mô hình ARX:**

| Ngày | Dự báo (USD/oz) | CI Lower | CI Upper | Hướng |
|------|----------------|----------|----------|-------|
| T+1 | *(điền)* | *(điền)* | *(điền)* | *(điền)* |
| T+2 | *(điền)* | *(điền)* | *(điền)* | *(điền)* |
| T+3 | *(điền)* | *(điền)* | *(điền)* | *(điền)* |
| T+4 | *(điền)* | *(điền)* | *(điền)* | *(điền)* |
| T+5 | *(điền)* | *(điền)* | *(điền)* | *(điền)* |
| T+6 | *(điền)* | *(điền)* | *(điền)* | *(điền)* |
| T+7 | *(điền)* | *(điền)* | *(điền)* | *(điền)* |

> **Lưu ý:** CI càng về cuối càng rộng ra → sự không chắc chắn tích lũy theo thời gian.  
> ARX dùng independent residual std (band cố định); MA/ARMA dùng statsmodels widening CI (chính xác hơn cho multi-step).

---

### E.3 Biểu đồ dự báo 30 ngày tới

> *Chụp màn hình tab Forecast → chọn 30D*

**File ảnh:** *(chụp màn hình ForecastMultiDayChart — 30D)*

**Nhận xét cần viết:**
- ARX: duy trì xu hướng nhờ rolling iterative prediction + technical indicators
- ARMA/MA: dùng ARIMA(p,**1**,q) → I(1) differencing giữ trend (không hội tụ về mean)
- CI mở rộng mạnh từ ngày 10–30 → mức độ không chắc chắn rất cao cho dự báo dài hạn
- Đường Consensus (vàng) ổn định hơn từng model riêng lẻ

**Kịch bản theo CI 95%:**

| Kịch bản | Căn cứ | Hàm ý |
|----------|--------|-------|
| **Base case** | Đường forecast trung tâm | Giá bạc dự kiến *(điền)* USD/oz sau 30 ngày |
| **Bullish** | Upper bound CI 95% | Tối đa *(điền)* USD/oz nếu trend tăng mạnh |
| **Bearish** | Lower bound CI 95% | Tối thiểu *(điền)* USD/oz nếu điều chỉnh |

---

### E.4 Biểu đồ so sánh dự báo

**File:** `outputs/charts/13_forecast_comparison_chart.png`

*(Từ pipeline học thuật — so sánh 6 mô hình monthly: SES, Holt, HoltDamped, HWAdd, HWMul, ARIMA)*

**Nhận xét:**
- So sánh dự báo của nhiều mô hình trên cùng một trục thời gian
- Mô hình nào gần đường actual nhất → hiệu suất tốt nhất
- Dùng để xác nhận lựa chọn mô hình từ bảng MAE/RMSE/MAPE

---

### E.5 Biểu đồ dự báo tương lai (Future Forecast)

**File:** `outputs/charts/14_future_forecast_chart.png`

*(Từ pipeline học thuật — retrain toàn bộ dữ liệu, dự báo 6–12 tháng tới)*

**Nhận xét:**
- Dự báo mở rộng ra ngoài vùng dữ liệu đã có
- Dải CI rộng dần theo thời gian
- Dùng làm "big picture" forecast bổ sung cho dự báo daily

---

---

## PHỤ LỤC F — CĂN CỨ CHỌN MÔ HÌNH

> Bảng tóm tắt logic chọn mô hình từ đặc điểm chuỗi thời gian

| Đặc điểm chuỗi | Kết luận từ EDA | Mô hình phù hợp | Mô hình dùng |
|----------------|-----------------|-----------------|-------------|
| Có xu hướng tăng dài hạn | Trend chart, MA chart | Mô hình có thành phần trend | Holt, HW, ARIMA(d=1) |
| Không dừng ở levels (ADF p > 0.05) | ADF test | Cần differencing d=1 | ARIMA(p,**1**,q) |
| Tự tương quan cao nhiều lag (ACF) | ACF/PACF chart | Mô hình AR | ARX, ARMA |
| Lag plot dọc theo đường 45° | Lag plot | Giá hôm nay ≈ giá hôm qua | AR(p), ARX |
| Có exogenous features (MA, volatility) | Kỹ thuật tài chính | Thêm biến ngoại sinh | **ARX** |
| Seasonal nhẹ (monthly, period=12) | Decomposition | HW nếu có seasonal | HW Additive/Multiplicative |

---

## PHỤ LỤC G — DANH MỤC BIỂU ĐỒ

| Phụ lục | File biểu đồ | Vị trí |
|---------|-------------|--------|
| B.1 | `01_trend_overview_line_chart.png` | `outputs/charts/2022-01_2026-04/` |
| B.2 | `02_trend_smoothing_moving_average_chart.png` | `outputs/charts/2022-01_2026-04/` |
| B.3 | `03_trend_zoom_aggregation_w_chart.png` | `outputs/charts/2022-01_2026-04/` |
| B.4 | `04_distribution_outlier_boxplot_chart.png` | `outputs/charts/2022-01_2026-04/` |
| B.5 | `05_distribution_frequency_histogram_chart.png` | `outputs/charts/2022-01_2026-04/` |
| B.6 | `06_distribution_density_kde_chart.png` | `outputs/charts/2022-01_2026-04/` |
| B.7 | `07_time_dependency_autocorrelation_chart.png` | `outputs/charts/2022-01_2026-04/` |
| B.8 | `08_time_dependency_lag_relationship_chart.png` | `outputs/charts/2022-01_2026-04/` |
| B.9 | `09_analysis_summary_combo_chart.png` | `outputs/charts/2022-01_2026-04/` |
| C.2 | `11_decomposition_additive_chart.png` | `outputs/charts/` |
| C.3 | `11_decomposition_multiplicative_chart.png` | `outputs/charts/` |
| D.2–D.4 | Screenshot tab Backtesting (ARX / MA / ARMA) | Dashboard |
| D.6 | Screenshot Radar chart | Dashboard tab Forecast |
| E.2 | Screenshot Forecast 7D | Dashboard tab Forecast |
| E.3 | Screenshot Forecast 30D | Dashboard tab Forecast |
| E.4 | `13_forecast_comparison_chart.png` | `outputs/charts/` |
| E.5 | `14_future_forecast_chart.png` | `outputs/charts/` |

---

## HƯỚNG DẪN CHỤP MÀN HÌNH TỪ DASHBOARD

```
1. Mở dashboard: http://localhost:5173

2. Tab Backtesting (06):
   → Bấm "Phân tích" → đợi load
   → Cuộn xuống, chụp từng chart ARX / MA / ARMA
   → Chụp bảng Comparison Table
   → Chụp Radar chart

3. Tab Forecast (07):
   → Chọn "1D" → Bấm "Phân tích" → chụp màn hình toàn bộ
   → Chọn "7D" → chụp line chart + CI + snapshot bar
   → Chọn "30D" → chụp line chart + CI + snapshot bar
   → Chụp Radar chart ở góc phải

4. Đặt tên file ảnh theo quy ước:
   screenshot_backtesting_arx.png
   screenshot_backtesting_ma.png
   screenshot_backtesting_arma.png
   screenshot_radar.png
   screenshot_forecast_1d.png
   screenshot_forecast_7d.png
   screenshot_forecast_30d.png
```

---

*Phụ lục được tạo tự động từ codebase Gold_TimeSeri — cập nhật lần cuối: 2026-04*
