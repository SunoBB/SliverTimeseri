# Agent: Frontend Flow

`Nhãn tài liệu:` Mô tả luồng React frontend — cách các trang hoạt động, phân trang URL, data loading và cấu trúc component.

## Tổng quan

```
Browser URL (?p=&tp=&start=&end=)
        │ readUrlParams() on mount
        ▼
App.jsx  (state: pageIndex, tablePage, startDate, endDate)
        │ fetch API (requestJson)
        ▼
FastAPI /silver/*
        │ response
        ▼
Components (chart, table, stat cards, forecast)
        │ user navigates
        ▼
URL updated (replaceState) ← URL luôn phản ánh trạng thái hiện tại
```

## Các file liên quan

| File | Vai trò |
|------|---------|
| `frontend/src/App.jsx` | Main orchestrator, state, data loading, URL sync |
| `frontend/src/components/common.jsx` | StatCard, HeroPanel, LineChart, MarketChart, HistoryTable, TablePagination |
| `frontend/src/components/analytics.jsx` | TechnicalAnalysisSuite (MA, RSI, MACD, histogram...) |
| `frontend/src/components/forecast.jsx` | ForecastCards, ForecastFocusChart, DirectionHitTable |
| `frontend/src/lib/api.js` | `requestJson()` wrapper |
| `frontend/src/lib/formatters.js` | `formatNumber()` với locale |
| `frontend/src/constants/reportPages.js` | `REPORT_PAGES` config, `TABLE_PAGE_SIZE = 50` |
| `frontend/src/styles.css` | CSS toàn bộ app (IBM Plex font, design tokens) |

## Các trang (REPORT_PAGES)

| Index | ID | Tên | Nội dung |
|-------|----|-----|---------|
| 0 | overview | Overview | StatCards, HeroPanel, filter |
| 1 | trend | Silver Technical Analytics | LineChart USD/VND, TechnicalAnalysisSuite |
| 2 | market | Market Terminal | MarketChart full-screen |
| 3 | summary | Summary Metrics | SummaryGrid từ `/silver/summary` |
| 4 | history | History Table | HistoryTable + phân trang backend |
| 5 | dataset_overview | Dataset Overview | DatasetOverviewChart + event markers |
| 6 | forecast | Model Forecast | ForecastCards, DirectionHitTable, model comparison |

## URL State Sync

```
URL params:
  ?p=<pageIndex>    (0–6, bỏ qua nếu = 0)
  &tp=<tablePage>   (chỉ khi p=4, bỏ qua nếu = 1)
  &start=YYYY-MM-DD (bỏ qua nếu không lọc)
  &end=YYYY-MM-DD   (bỏ qua nếu không lọc)
```

- URL cập nhật bằng `history.replaceState` (không tạo history entry mới).
- Khi load trang, `readUrlParams()` đọc URL để khôi phục state ban đầu.
- Hỗ trợ `popstate` event để back/forward hoạt động.
- Ví dụ link chia sẻ: `http://localhost:5173/?p=4&tp=3&start=2024-01-01`

## Data Loading

```
loadDashboard()  → /silver/summary + /silver/history (toàn bộ) + /silver/events
                   Chạy khi mount và khi filter thay đổi (params useMemo)

loadTablePage()  → /silver/history?limit=50&offset=(page-1)*50
                   Chỉ chạy khi đang ở pageIndex=4

loadForecast()   → /silver/models (nặng, ~5-15s)
                   Chỉ chạy khi user bấm "Phân tích"
```

## Phân trang bảng (History Table)

- Backend: SQL `LIMIT/OFFSET`, trả `{ data, total_rows, rows }`.
- Frontend: `tablePage` state, `TABLE_PAGE_SIZE = 50` rows/trang.
- Jump-to-page: input + Enter hoặc nút Go.
- URL: `?p=4&tp=<page>` cập nhật realtime khi chuyển trang.

## Top Navigation Bar (`.topnav`)

- Sticky ở đầu trang (`position: sticky; top: 0`).
- Hiển thị tất cả 7 trang, highlight trang đang xem.
- Nút ‹ / › để prev/next nhanh.
- Tên trang ẩn trên mobile (chỉ giữ số).

## Design System

```css
Font: IBM Plex Mono (headings, labels, mono) + IBM Plex Sans (body)
Palette:
  --bg: #f6f2e8
  --accent-blue: #2968c8
  --accent-coral: #d85a30
  --accent-teal: #158a67
  --accent-amber: #b38422
Max width: 1680px
```

## Chạy frontend

```bash
cd frontend
cp .env.example .env        # VITE_API_BASE_URL=http://127.0.0.1:8000
npm install
npm run dev                  # http://127.0.0.1:5173
npm run build                # output → dist/
```
