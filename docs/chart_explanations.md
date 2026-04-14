# Giải thích từng biểu đồ phân tích chuỗi thời gian giá bạc

> Tài liệu này giải thích **tại sao mỗi biểu đồ trông như vậy**, mô hình/thuật toán nào tạo ra nó, và cách đọc kết quả.

---

## 01 — Biểu đồ đường tổng quan (`01_trend_overview_line_chart.png`)

### Mô hình / Thuật toán
Không dùng mô hình thống kê. Đây là **vẽ thẳng dữ liệu gốc** lên trục thời gian.

```python
ax.plot(series.index, series)
```

### Tại sao trông như vậy?
Mỗi điểm trên đường là giá bạc thực tế vào ngày đó. Đường gấp khúc liên tục vì giá thay đổi mỗi ngày giao dịch. Trục X là thời gian (DatetimeIndex), trục Y là giá USD/ounce.

### Cách đọc
- Đường **dốc lên** về phía phải → xu hướng tăng dài hạn
- Đường **dao động mạnh** → biến động lớn, rủi ro cao
- Đỉnh nhọn bất thường → sự kiện thị trường (khủng hoảng, tăng đột biến)

---

## 02 — Trung bình động (`02_trend_smoothing_moving_average_chart.png`)

### Mô hình / Thuật toán
**Rolling Mean** (trung bình trượt) với cửa sổ mặc định `window=7` ngày.

```python
moving_average = series.rolling(window=7).mean()
```

### Tại sao trông như vậy?
Đường cam (trung bình động) **mượt hơn** đường xanh (dữ liệu gốc) vì mỗi điểm trên đường cam là trung bình của 7 ngày liên tiếp. Nhiễu ngắn hạn bị triệt tiêu, chỉ còn xu hướng dài hạn.

7 ngày đầu tiên sẽ là `NaN` (không đủ dữ liệu để tính trung bình), nên đường cam bắt đầu muộn hơn đường gốc.

### Cách đọc
- Đường cam **nằm trên** đường xanh → giá đang **giảm** (giá hiện tại thấp hơn trung bình quá khứ)
- Đường cam **nằm dưới** đường xanh → giá đang **tăng**
- Hai đường **cắt nhau** → điểm đảo chiều xu hướng tiềm năng

---

## 03 — Gộp theo kỳ (`03_trend_zoom_aggregation_*_chart.png`)

### Mô hình / Thuật toán
**Resample + Mean** — gộp nhiều ngày thành một điểm đại diện.

```python
aggregated = series.resample("W").mean()  # W = weekly, ME = monthly end...
```

### Tại sao trông như vậy?
Thay vì ~250 điểm/năm (daily), sau khi resample tuần thì còn ~52 điểm/năm. Mỗi điểm là **giá trung bình của cả tuần đó**. Biểu đồ "thô" hơn chart trung bình động nhưng vẫn ít nhiễu hơn dữ liệu daily.

### Cách đọc
- Giúp thấy rõ **xu hướng theo kỳ** (tuần/tháng/quý) không bị che bởi biến động ngày
- So sánh với chart trung bình động: nếu cả hai cùng xu hướng → tín hiệu mạnh hơn

---

## 04 — Boxplot phân phối (`04_distribution_outlier_boxplot_chart.png`)

### Mô hình / Thuật toán
**Boxplot** (biểu đồ hộp) — thống kê mô tả dựa trên tứ phân vị.

```python
plt.boxplot(series.dropna())
```

Các thành phần:
- **Hộp**: Q1 (25%) đến Q3 (75%) — nơi 50% dữ liệu nằm
- **Đường ngang trong hộp**: Trung vị (Q2, 50%)
- **Whisker**: Q1 − 1.5×IQR đến Q3 + 1.5×IQR
- **Điểm ngoài whisker**: Outlier

### Tại sao trông như vậy?
Nếu hộp **lệch về phía dưới** (median gần Q1 hơn Q3) → phân phối lệch phải (nhiều giá trị thấp, ít giá trị rất cao). Outlier ở trên cùng là các đỉnh giá bất thường.

### Cách đọc
- Hộp cao → độ phân tán lớn
- Nhiều điểm ngoài whisker → nhiều outlier, giá bất thường
- Vị trí median so với hộp → phân phối lệch hay đối xứng

---

## 05 — Histogram tần suất (`05_distribution_frequency_histogram_chart.png`)

### Mô hình / Thuật toán
**Histogram** — đếm số lần giá rơi vào từng khoảng (bin).

```python
plt.hist(series.dropna(), bins=10)
```

### Tại sao trông như vậy?
Trục X chia khoảng giá thành 10 phần đều nhau. Cột cao nhất cho biết khoảng giá **xuất hiện nhiều nhất** trong lịch sử. Nếu có nhiều cột cao ở một đầu và dài đuôi ở đầu kia → phân phối lệch.

### Cách đọc
- **Lệch phải** (đuôi dài bên phải): giá thấp chiếm đa số, đôi khi có giá rất cao (điển hình cho hàng hóa)
- **Nhiều đỉnh** (bimodal): có thể dữ liệu trải qua hai "chế độ" giá khác nhau (ví dụ: trước và sau một cuộc khủng hoảng)
- **Chuẩn tắc (bell-shaped)**: phân phối đều, ít xu hướng mạnh

---

## 06 — Mật độ KDE (`06_distribution_density_kde_chart.png`)

### Mô hình / Thuật toán
**Kernel Density Estimation (KDE)** — ước lượng hàm mật độ xác suất bằng cách làm mượt histogram.

```python
series.plot(kind="kde")
# Tương đương: scipy.stats.gaussian_kde(series)
```

KDE đặt một "kernel" (thường là Gaussian) lên từng điểm dữ liệu rồi cộng tất cả lại thành đường cong liên tục.

### Tại sao trông như vậy?
Khác histogram ở chỗ **liên tục** và không phụ thuộc số bin. Đỉnh cao nhất = vùng giá **xuất hiện dày đặc nhất**. Nếu có hai đỉnh → bimodal (hai chế độ giá).

### Cách đọc
- Đỉnh nhọn cao → giá tập trung hẹp, ít biến động
- Đỉnh rộng thấp → giá phân tán rộng
- Đuôi dài phải → có những đợt tăng giá đột biến trong lịch sử

---

## 07 — Tự tương quan (`07_time_dependency_autocorrelation_chart.png`)

### Mô hình / Thuật toán
**Autocorrelation Function (ACF) đơn giản** — tính hệ số tương quan giữa chuỗi với chính nó tại mỗi độ trễ k.

```python
from pandas.plotting import autocorrelation_plot
autocorrelation_plot(series.dropna())
```

Công thức: `r(k) = Corr(y_t, y_{t-k})`

### Tại sao trông như vậy?
- Nếu chuỗi **không dừng** (có xu hướng): ACF giảm rất chậm từ 1 về 0 → đường tự tương quan "bền" qua nhiều lag
- Nếu chuỗi **dừng** (stationary): ACF giảm nhanh về 0 và dao động trong vùng tin cậy

Giá bạc có xu hướng dài hạn nên ACF thường giảm chậm → tín hiệu cần lấy sai phân trước khi dùng ARIMA.

### Cách đọc
- Đường nằm ngoài dải tin cậy (đường nét đứt) → tự tương quan có ý nghĩa thống kê tại lag đó
- ACF giảm chậm → chuỗi không dừng, cần lấy sai phân (d ≥ 1 cho ARIMA)
- ACF giảm nhanh → chuỗi dừng

---

## 08 — Lag plot (`08_time_dependency_lag_relationship_chart.png`)

### Mô hình / Thuật toán
**Lag Scatter Plot** — vẽ `y_t` vs `y_{t-lag}` (mặc định lag=1).

```python
from pandas.plotting import lag_plot
lag_plot(series.dropna(), lag=1)
```

### Tại sao trông như vậy?
Mỗi điểm trên biểu đồ là một cặp `(giá hôm qua, giá hôm nay)`. Nếu các điểm tạo thành **đường chéo** từ trái-dưới đến phải-trên → tương quan dương mạnh (giá hôm nay ≈ giá hôm qua).

### Cách đọc
- **Đám điểm dọc theo đường chéo 45°**: tự tương quan tuyến tính rất mạnh → giá thay đổi ít từ ngày sang ngày (phổ biến với hàng hóa)
- **Đám tròn vô hướng**: không có tự tương quan → ngẫu nhiên
- **Hình chữ V / U**: tự tương quan phi tuyến

---

## 09 — Tổng hợp 2×2 (`09_analysis_summary_combo_chart.png`)

### Mô hình / Thuật toán
**Không có mô hình mới** — ghép 4 chart đã có vào 1 figure để so sánh cạnh nhau:
1. Biểu đồ đường gốc
2. Trung bình động
3. Histogram
4. Boxplot

```python
fig = plt.figure(figsize=(12, 8))
plt.subplot(2, 2, 1)  # line
plt.subplot(2, 2, 2)  # moving average
plt.subplot(2, 2, 3)  # histogram
plt.subplot(2, 2, 4)  # boxplot
```

### Cách đọc
Dùng để có **cái nhìn nhanh toàn cảnh** mà không cần mở từng file. Đặc biệt hữu ích khi in báo cáo.

---

## 10 — ACF / PACF (`10_acf_pacf_chart.png`)

### Mô hình / Thuật toán
Dùng **statsmodels** để tính ACF và PACF chuyên sâu hơn chart 07, trên **chuỗi monthly** (đã resample).

```python
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

plot_acf(series.dropna(), lags=24, ax=ax1)         # ACF
plot_pacf(series.dropna(), lags=24, ax=ax2, method="ywm")  # PACF
```

**PACF** (Partial ACF) = tương quan giữa `y_t` và `y_{t-k}` **sau khi đã loại bỏ** ảnh hưởng của các lag trung gian `1, 2, ..., k-1`.

### Tại sao trông như vậy?
- **ACF**: nếu chuỗi không dừng → bar cao kéo dài qua nhiều lag. Sau khi lấy sai phân → bar giảm nhanh.
- **PACF**: thường chỉ có vài bar đầu có ý nghĩa, sau đó cắt về 0.

### Cách đọc — chọn p, q cho ARIMA(p, d, q)
| Quan sát | Kết luận |
|---|---|
| ACF cắt về 0 tại lag q, PACF giảm dần | → MA(q), dùng q |
| PACF cắt về 0 tại lag p, ACF giảm dần | → AR(p), dùng p |
| Cả hai giảm dần | → ARMA(p, q) |

---

## 11 — Kiểm định tính dừng ADF (`11_stationarity_adf_chart.png`)

### Mô hình / Thuật toán
**Augmented Dickey-Fuller (ADF) Test** — kiểm định xem chuỗi có "dừng" (stationary) không.

```python
from statsmodels.tsa.stattools import adfuller

stat, p_value, lags, n_obs, crit, _ = adfuller(series, autolag="AIC")
# autolag="AIC": tự chọn số lần lag tối ưu dựa trên AIC
```

Biểu đồ vẽ **3 panel**:
- Panel 1: Giá gốc (levels)
- Panel 2: Sai phân bậc 1 (`series.diff()`)
- Panel 3: Sai phân bậc 2 (`series.diff().diff()`)

Mỗi panel annotate kết quả ADF: `ADF statistic | p-value → DỪNG ✓ / KHÔNG DỪNG ✗`

### Tại sao trông như vậy?
- **Levels**: thường dao động chậm quanh một xu hướng → không dừng → ADF p > 0.05
- **Diff-1**: chuỗi thay đổi giá hàng tháng, bằng phẳng hơn → thường đã dừng → p < 0.05
- **Diff-2**: nếu diff-1 chưa đủ, diff-2 sẽ dừng; nhưng thường thừa và tăng nhiễu

### Cách đọc
- `p < 0.05` → **dừng** (reject H₀: có unit root) → xanh lá
- `p ≥ 0.05` → **không dừng** → đỏ
- Tiêu đề chart cho biết `d` đề xuất — dùng làm tham số `d` trong `ARIMA(p, d, q)`

---

## 12 — Phân rã cộng (`12_decomposition_additive_chart.png`)

### Mô hình / Thuật toán
**Seasonal Decompose — Additive model**: tách chuỗi thành tổng của 3 thành phần.

```
Observed(t) = Trend(t) + Seasonal(t) + Residual(t)
```

```python
from statsmodels.tsa.seasonal import seasonal_decompose
result = seasonal_decompose(series, model="additive", period=12)
```

**3 bước tách:**

1. **Trend** = Centered Moving Average với window=period=12
   ```
   Trend(t) = mean(y[t-6], ..., y[t+6])
   ```

2. **Seasonal** = trung bình detrended theo từng tháng
   ```
   Detrended(t) = Observed(t) - Trend(t)
   Seasonal[tháng k] = mean(Detrended tại mọi tháng k trong dataset)
   ```
   → Đây là lý do seasonal **lặp đều đặn** — nó là pattern trung bình của nhiều năm.

3. **Residual** = phần còn lại
   ```
   Residual(t) = Observed(t) - Trend(t) - Seasonal(t)
   ```

### Tại sao trông như vậy?
- **Observed**: gấp khúc nhiễu nhiều — là dữ liệu gốc
- **Trend**: mượt — vì là MA12
- **Seasonal**: **lặp hoàn toàn đều mỗi năm** — vì là pattern trung bình, không phải giá trị thực từng tháng
- **Residual**: dao động không có cấu trúc — lý tưởng là gần nhiễu trắng

### Cách đọc
- Seasonal.std() nhỏ → biên độ thời vụ ổn định → nên dùng mô hình cộng
- Residual có cấu trúc (không phải ngẫu nhiên) → mô hình chưa giải thích hết

---

## 13 — Phân rã nhân (`13_decomposition_multiplicative_chart.png`)

### Mô hình / Thuật toán
**Seasonal Decompose — Multiplicative model**: thay vì cộng, nhân các thành phần lại.

```
Observed(t) = Trend(t) × Seasonal(t) × Residual(t)
```

```python
result = seasonal_decompose(series, model="multiplicative", period=12)
```

**Khác biệt so với Additive:**
- Trend tính tương tự (MA12)
- Seasonal(t) = mean(Observed(t) / Trend(t)) theo từng tháng — là **hệ số nhân** (ví dụ: 1.05 nghĩa là tháng đó giá thường cao hơn trung bình 5%)
- Residual = Observed / (Trend × Seasonal)

### Tại sao trông như vậy?
Seasonal trong mô hình nhân là **tỷ lệ phần trăm** so với trend, không phải giá trị tuyệt đối. Nếu biên độ dao động của giá tăng theo thời gian (khi giá cao thì volatility cũng cao hơn), mô hình nhân phù hợp hơn.

### Chọn mô hình nào?
Code tự động so sánh:
```python
recommended = "additive" if add_seasonal_std <= mul_seasonal_std else "multiplicative"
```
Mô hình có **seasonal.std() nhỏ hơn** → seasonal ổn định hơn → được chọn.

---

## 14 — So sánh dự báo tập test (`14_forecast_comparison_chart.png`)

### Mô hình / Thuật toán
Vẽ kết quả dự báo của **6 mô hình** trên cùng tập test, so sánh với giá thực tế.

| Mô hình | Phù hợp khi |
|---|---|
| **SES** — Simple Exponential Smoothing | Không trend, không seasonal |
| **Holt Linear** | Có trend tuyến tính |
| **Holt Damped** | Trend tuyến tính nhưng giảm dần |
| **HW Additive** | Trend + seasonal biên độ cố định |
| **HW Multiplicative** | Trend + seasonal biên độ tỷ lệ với level |
| **ARIMA(p,d,q)** | Chuỗi có tự tương quan, sau khi lấy sai phân |

**Chia train/test:**
```python
train = data.iloc[:-test_size]   # 80% đầu
test  = data.iloc[-test_size:]   # 12 tháng cuối
```

Mỗi mô hình train trên `train`, predict trên `test`, so sánh với actual.

### Tại sao trông như vậy?
- Đường **đen đậm** = giá thực tế (actual)
- Các đường **nét đứt màu** = dự báo của từng mô hình
- Mô hình nào gần đường đen nhất → sai số nhỏ nhất

### Cách đọc
Nhìn vào giai đoạn test (phần cuối):
- Mô hình nào bám sát đường đen nhất → **MAPE thấp nhất** → mô hình tốt nhất
- Mô hình quá phẳng (ngang) → không bắt được biến động (thường là SES)

---

## 15 — Dự báo tương lai (`15_future_forecast_chart.png`)

### Mô hình / Thuật toán
**Mô hình tốt nhất** (chọn theo MAPE nhỏ nhất từ chart 14) được retrain trên **toàn bộ dữ liệu** rồi dự báo `n_months` tháng tiếp theo.

```python
# Chọn mô hình
best_model = comparison[0]["model"]   # đứng đầu bảng MAPE

# Retrain trên toàn bộ
forecast_future_months(monthly, best_model, n_months=12)
```

Với ARIMA, khoảng tin cậy 95% được tính từ `get_forecast().conf_int(alpha=0.05)`.

### Tại sao trông như vậy?
- **Đường xanh đậm** = lịch sử 36 tháng gần nhất
- **Đường cam nét đứt** = dự báo tương lai
- **Vùng tô nhạt** = khoảng tin cậy 95% (chỉ có với ARIMA)
- **Đường thẳng đứng xám** = ranh giới lịch sử / tương lai

Dự báo thường có xu hướng **hội tụ về đường thẳng** khi nhìn xa (vì không có thông tin mới, mô hình dần về mean dài hạn).

### Cách đọc
- Khoảng tin cậy **mở rộng** theo thời gian → càng xa càng bất định
- Đường dự báo đi lên/xuống → mô hình nhận diện được xu hướng hiện tại
- Nếu khoảng tin cậy quá rộng → cần thêm dữ liệu hoặc mô hình phức tạp hơn

---

## Tóm tắt luồng phân tích

```
Dữ liệu daily
    │
    ├─ Charts 01–09  ← EDA (khám phá, không mô hình)
    │   ├── 01: Giá thực tế
    │   ├── 02: Xu hướng (MA)
    │   ├── 03: Gộp kỳ (resample)
    │   ├── 04–06: Phân phối (boxplot, histogram, KDE)
    │   ├── 07–08: Phụ thuộc thời gian (ACF, lag)
    │   └── 09: Tổng hợp
    │
    ↓ Resample sang Monthly
    │
    ├─ Chart 10  ← Chọn p, q cho ARIMA (ACF/PACF)
    ├─ Chart 11  ← Kiểm định ADF → xác định d cho ARIMA
    ├─ Chart 12  ← Phân rã Additive
    ├─ Chart 13  ← Phân rã Multiplicative
    ├─ Chart 14  ← So sánh 6 mô hình trên tập test
    └─ Chart 15  ← Dự báo tương lai bằng mô hình tốt nhất
```
