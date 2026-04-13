import { useEffect, useMemo, useState } from "react";

import {
  MODEL_AR_ORDER,
  MODEL_MA_ORDER,
  MODEL_TEST_SIZE,
  REPORT_PAGES,
  TABLE_PAGE_SIZE,
} from "./constants/reportPages";
import {
  DatasetOverviewChart,
  EmptyState,
  HistoryTable,
  LineChart,
  MarketChart,
  StatCard,
  StationarityReport,
  SummaryGrid,
  TablePagination,
} from "./components/common";
import { TechnicalAnalysisSuite } from "./components/analytics";
import {
  ForecastChart,
  ForecastContextNote,
  ForecastHero,
  ForecastReportTable,
} from "./components/forecast";
import { requestJson } from "./lib/api";
import { formatNumber } from "./lib/formatters";

function readUrlParams() {
  const search = new URLSearchParams(window.location.search);
  const p = parseInt(search.get("p"), 10);
  const tp = parseInt(search.get("tp"), 10);
  return {
    pageIndex: Number.isFinite(p) && p >= 0 && p < REPORT_PAGES.length ? p : 0,
    tablePage: Number.isFinite(tp) && tp >= 1 ? tp : 1,
    startDate: search.get("start") || "",
    endDate: search.get("end") || "",
  };
}

export default function App() {
  const initial = readUrlParams();
  const [startDate, setStartDate] = useState(initial.startDate);
  const [endDate, setEndDate] = useState(initial.endDate);
  const [summary, setSummary] = useState({});
  const [history, setHistory] = useState([]);
  const [events, setEvents] = useState([]);
  const [modelSuite, setModelSuite] = useState(null);
  const [tableRows, setTableRows] = useState([]);
  const [tableTotalRows, setTableTotalRows] = useState(0);
  const [tablePage, setTablePage] = useState(initial.tablePage);
  const [stationarity, setStationarity] = useState(null);
  const [stationarityLoading, setStationarityLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [tableLoading, setTableLoading] = useState(false);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");
  const [pageIndex, setPageIndex] = useState(initial.pageIndex);
  const [forecastDirty, setForecastDirty] = useState(true);
  const [forecastRequested, setForecastRequested] = useState(false);
  const [jumpInput, setJumpInput] = useState("");

  const params = useMemo(
    () => ({
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      timeframe: "1d",
    }),
    [startDate, endDate],
  );

  const currentPage = REPORT_PAGES[pageIndex];
  const latestRow = history[history.length - 1];
  const hasData = history.length > 0;
  const totalTablePages = Math.max(1, Math.ceil(tableTotalRows / TABLE_PAGE_SIZE));
  const models = modelSuite?.models || [];
  const forecastContext = modelSuite?.forecast_context || null;
  const modelRankings = modelSuite?.model_rankings || null;

  const bestModel = useMemo(
    () =>
      [...models].sort(
        (l, r) =>
          Number(l.metrics?.mae ?? Infinity) - Number(r.metrics?.mae ?? Infinity),
      )[0] || null,
    [models],
  );

  async function loadDashboard() {
    setLoading(true);
    setError("");
    try {
      const [sumRes, histRes, evRes] = await Promise.all([
        requestJson("/silver/summary", params),
        requestJson("/silver/history", params),
        requestJson("/silver/events", params),
      ]);
      setSummary(sumRes);
      setHistory(Array.isArray(histRes.data) ? histRes.data : []);
      setEvents(Array.isArray(evRes.data) ? evRes.data : []);
    } catch (err) {
      setError(err.message);
      setSummary({});
      setHistory([]);
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }

  async function loadTablePage(page = tablePage) {
    setTableLoading(true);
    setError("");
    try {
      const res = await requestJson("/silver/history", {
        ...params,
        limit: TABLE_PAGE_SIZE,
        offset: (page - 1) * TABLE_PAGE_SIZE,
      });
      setTableRows(Array.isArray(res.data) ? res.data : []);
      setTableTotalRows(Number(res.total_rows || 0));
    } catch (err) {
      setError(err.message);
      setTableRows([]);
      setTableTotalRows(0);
    } finally {
      setTableLoading(false);
    }
  }

  async function loadStationarity() {
    setStationarityLoading(true);
    try {
      const res = await requestJson("/silver/stationarity", params);
      setStationarity(res);
    } catch (err) {
      setStationarity({ error: err.message });
    } finally {
      setStationarityLoading(false);
    }
  }

  async function loadForecast() {
    setForecastLoading(true);
    setError("");
    try {
      const res = await requestJson("/silver/models", {
        ...params,
        ar_order: MODEL_AR_ORDER,
        ma_order: MODEL_MA_ORDER,
        test_size: MODEL_TEST_SIZE,
      });
      setModelSuite(res);
      setForecastDirty(false);
      setForecastRequested(true);
    } catch (err) {
      setError(err.message);
      setModelSuite(null);
    } finally {
      setForecastLoading(false);
    }
  }

  async function handleSync() {
    setSyncing(true);
    setError("");
    try {
      await requestJson("/silver/sync", { ...params, force_refresh: true }, "POST");
      await loadDashboard();
      await loadTablePage(1);
      setTablePage(1);
      setForecastDirty(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSyncing(false);
    }
  }

  useEffect(() => { loadDashboard(); }, [params]);

  useEffect(() => {
    setTablePage(1);
    setForecastDirty(true);
  }, [startDate, endDate]);

  useEffect(() => {
    if (pageIndex === 4) loadTablePage(tablePage);
  }, [pageIndex, tablePage, params]);

  useEffect(() => {
    if (pageIndex === 3) loadStationarity();
  }, [pageIndex, params]);

  // Sync URL
  useEffect(() => {
    const q = new URLSearchParams();
    if (pageIndex !== 0) q.set("p", String(pageIndex));
    if (pageIndex === 4 && tablePage !== 1) q.set("tp", String(tablePage));
    if (startDate) q.set("start", startDate);
    if (endDate) q.set("end", endDate);
    const qs = q.toString();
    window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
  }, [pageIndex, tablePage, startDate, endDate]);

  useEffect(() => {
    function onPop() {
      const r = readUrlParams();
      setPageIndex(r.pageIndex);
      setTablePage(r.tablePage);
      setStartDate(r.startDate);
      setEndDate(r.endDate);
    }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  return (
    <div className="app">

      {/* ── App Bar ──────────────────────────────────────────── */}
      <header className="appbar">
        <div className="appbar-brand">
          <span className="brand-mark">◆</span>
          <span className="brand-name">XAGUSD</span>
          <span className="brand-sep">/</span>
          <span className="brand-sub">Silver Analytics</span>
        </div>

        <nav className="appbar-tabs">
          {REPORT_PAGES.map((page, index) => (
            <button
              key={page.id}
              className={`apptab${index === pageIndex ? " active" : ""}`}
              onClick={() => setPageIndex(index)}
              title={page.title}
            >
              {page.shortLabel}
            </button>
          ))}
        </nav>

        <div className="appbar-end">
          <button
            className="appbar-nav"
            onClick={() => setPageIndex((v) => Math.max(v - 1, 0))}
            disabled={pageIndex === 0}
            aria-label="Trang trước"
          >‹</button>
          <button
            className="appbar-nav"
            onClick={() => setPageIndex((v) => Math.min(v + 1, REPORT_PAGES.length - 1))}
            disabled={pageIndex === REPORT_PAGES.length - 1}
            aria-label="Trang sau"
          >›</button>
          <button className="appbar-sync" onClick={handleSync} disabled={syncing}>
            {syncing ? "Syncing…" : "Sync ↑"}
          </button>
        </div>
      </header>

      {/* ── Filter Bar ───────────────────────────────────────── */}
      <div className="filterbar">
        <div className="filterbar-stats">
          {loading
            ? <span className="fstat-loading">Đang tải…</span>
            : hasData && (
              <>
                <div className="fstat">
                  <span className="fstat-key">Rows</span>
                  <strong className="fstat-val">{formatNumber(history.length)}</strong>
                </div>
                <div className="fstat-div" />
                <div className="fstat">
                  <span className="fstat-key">USD/oz</span>
                  <strong className="fstat-val">
                    {formatNumber(summary.end_price_usd, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </strong>
                </div>
                <div className="fstat">
                  <span className="fstat-key">VND/lượng</span>
                  <strong className="fstat-val">
                    {formatNumber(summary.end_price_vnd, { maximumFractionDigits: 0 })}
                  </strong>
                </div>
                <div className="fstat">
                  <span className="fstat-key">Latest</span>
                  <strong className="fstat-val">
                    {latestRow ? new Date(latestRow.price_timestamp).toLocaleDateString("en-CA") : "--"}
                  </strong>
                </div>
                <div className="fstat-div" />
                <div className="fstat">
                  <span className="fstat-key">Range</span>
                  <strong className="fstat-val">
                    {summary.start_date || "--"} → {summary.end_date || "--"}
                  </strong>
                </div>
              </>
            )
          }
        </div>

        <div className="filterbar-controls">
          <label className="fbar-label" htmlFor="fs">Từ</label>
          <input
            id="fs"
            className="fbar-date"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
          <span className="fbar-arrow">→</span>
          <label className="fbar-label" htmlFor="fe">Đến</label>
          <input
            id="fe"
            className="fbar-date"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
          {(startDate || endDate) && (
            <button
              className="fbar-btn fbar-clear"
              onClick={() => { setStartDate(""); setEndDate(""); }}
            >
              × xóa filter
            </button>
          )}
          <button className="fbar-btn fbar-refresh" onClick={loadDashboard} disabled={loading}>
            {loading ? "…" : "↻"}
          </button>
        </div>
      </div>

      {/* ── Error banner ─────────────────────────────────────── */}
      {error && <div className="status-bar error">{error}</div>}

      {/* ── Page body ────────────────────────────────────────── */}
      <main className="page-body">

        {/* 00 — Overview */}
        <section className={`page-section${pageIndex === 0 ? " active" : ""}`}>
          <div className="page-header">
            <h1 className="page-title">{currentPage.headline}</h1>
            <p className="page-desc">{currentPage.description}</p>
          </div>

          <div className="kpi-grid">
            <StatCard
              label="Observations"
              value={loading ? "…" : formatNumber(summary.rows)}
              subtext={`${summary.start_date || "--"} → ${summary.end_date || "--"}`}
              highlight
            />
            <StatCard
              label="Silver USD / oz"
              value={loading ? "…" : formatNumber(summary.end_price_usd, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              subtext="giá đóng cửa gần nhất"
            />
            <StatCard
              label="Silver VND / lượng"
              value={loading ? "…" : formatNumber(summary.end_price_vnd, { maximumFractionDigits: 0 })}
              subtext="quy đổi theo tỷ giá lịch sử"
            />
            <StatCard
              label="Latest Day"
              value={latestRow ? new Date(latestRow.price_timestamp).toLocaleDateString("en-CA") : "--"}
              subtext="mốc dữ liệu gần nhất"
            />
            <StatCard
              label="USD / VND"
              value={loading ? "…" : formatNumber(history.at(-1)?.usd_vnd_rate, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              subtext="tỷ giá gần nhất"
            />
          </div>

          {hasData ? (
            <div className="overview-tiles">
              <div className="tile">
                <div className="tile-label">Khoảng dữ liệu</div>
                <div className="tile-val">{summary.start_date || "--"} → {summary.end_date || "--"}</div>
              </div>
              <div className="tile">
                <div className="tile-label">Giá cao nhất</div>
                <div className="tile-val">{formatNumber(summary.max_price_usd, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
              </div>
              <div className="tile">
                <div className="tile-label">Giá thấp nhất</div>
                <div className="tile-val">{formatNumber(summary.min_price_usd, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
              </div>
              <div className="tile">
                <div className="tile-label">Giá trung bình</div>
                <div className="tile-val">{formatNumber(summary.mean_price_usd, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
              </div>
              <div className="tile">
                <div className="tile-label">Max Drawdown</div>
                <div className="tile-val">{summary.max_drawdown != null ? `${formatNumber(summary.max_drawdown * 100, { maximumFractionDigits: 1 })}%` : "--"}</div>
              </div>
              <div className="tile">
                <div className="tile-label">Series mode</div>
                <div className="tile-val">XAGUSD · 1d · curated</div>
              </div>
            </div>
          ) : (
            <EmptyState title="Chưa có dữ liệu" text="Bấm Sync ↑ để đồng bộ dữ liệu từ Alpha Vantage vào database." />
          )}
        </section>

        {/* 01 — Trend */}
        <section className={`page-section${pageIndex === 1 ? " active" : ""}`}>
          <div className="page-header">
            <h1 className="page-title">{currentPage.headline}</h1>
            <p className="page-desc">{currentPage.description}</p>
          </div>
          {hasData ? (
            <>
              <div className="chart-grid-2">
                <LineChart
                  data={history}
                  yKey="price_usd"
                  color="#2968c8"
                  label="Silver price theo USD/ounce"
                  note="đường giá bạc theo ngày để đọc xu hướng tổng quát nhanh hơn"
                  formatter={(v) => formatNumber(v, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                />
                <LineChart
                  data={history}
                  yKey="price_vnd"
                  color="#d85a30"
                  label="Silver price theo VND/lượng"
                  note="chuỗi giá quy đổi sang VND/lượng theo tỷ giá lịch sử"
                  formatter={(v) => formatNumber(v, { maximumFractionDigits: 0 })}
                />
              </div>
              <TechnicalAnalysisSuite data={history} />
            </>
          ) : (
            <EmptyState title="Chưa có dữ liệu để vẽ biểu đồ" text="Hãy bấm Sync ↑ hoặc nới lại khoảng ngày." />
          )}
        </section>

        {/* 02 — Market Terminal */}
        <section className={`page-section${pageIndex === 2 ? " active" : ""}`}>
          <div className="page-header">
            <h1 className="page-title">{currentPage.headline}</h1>
            <p className="page-desc">{currentPage.description}</p>
          </div>
          {hasData ? (
            <MarketChart
              data={history}
              events={events}
              yKey="price_usd"
              label="Silver price theo USD/ounce"
              note="trang chart riêng, ưu tiên trải nghiệm market terminal hơn là layout báo cáo"
              formatter={(v) => formatNumber(v, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            />
          ) : (
            <EmptyState title="Chưa có dữ liệu để vẽ biểu đồ" text="Hãy bấm Sync ↑ hoặc nới lại khoảng ngày." />
          )}
        </section>

        {/* 03 — Summary */}
        <section className={`page-section${pageIndex === 3 ? " active" : ""}`}>
          <div className="page-header">
            <h1 className="page-title">{currentPage.headline}</h1>
            <p className="page-desc">{currentPage.description}</p>
          </div>
          {Object.keys(summary).length ? (
            <SummaryGrid summary={summary} />
          ) : (
            <EmptyState
              title="Summary chưa sẵn sàng"
              text="Backend đang không có dữ liệu trong khoảng ngày này."
            />
          )}

          <StationarityReport data={stationarity} loading={stationarityLoading} />
        </section>

        {/* 04 — History Table */}
        <section className={`page-section${pageIndex === 4 ? " active" : ""}`}>
          <div className="page-header">
            <h1 className="page-title">{currentPage.headline}</h1>
            <p className="page-desc">{currentPage.description}</p>
          </div>
          <div className="chart-card">
            <div className="card-title">Silver market data</div>
            <div className="card-sub">
              endpoint <code>/silver/history</code> · phân trang backend · URL cập nhật theo trang hiện tại
            </div>
            {tableLoading
              ? <div className="chart-note">Đang tải trang dữ liệu…</div>
              : <HistoryTable rows={tableRows} />
            }
            <TablePagination
              page={tablePage}
              totalPages={totalTablePages}
              totalRows={tableTotalRows}
              onPrev={() => setTablePage((v) => Math.max(v - 1, 1))}
              onNext={() => setTablePage((v) => Math.min(v + 1, totalTablePages))}
            />
            <div className="jump-row">
              <span className="jump-label">Đến trang</span>
              <input
                className="jump-input"
                type="number"
                min={1}
                max={totalTablePages}
                value={jumpInput}
                placeholder={String(tablePage)}
                onChange={(e) => setJumpInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    const t = parseInt(jumpInput, 10);
                    if (Number.isFinite(t) && t >= 1 && t <= totalTablePages) setTablePage(t);
                    setJumpInput("");
                  }
                }}
              />
              <span className="jump-label">/ {totalTablePages}</span>
              <button
                className="fbar-btn"
                onClick={() => {
                  const t = parseInt(jumpInput, 10);
                  if (Number.isFinite(t) && t >= 1 && t <= totalTablePages) setTablePage(t);
                  setJumpInput("");
                }}
              >
                Go
              </button>
            </div>
          </div>
        </section>

        {/* 05 — Dataset Overview */}
        <section className={`page-section${pageIndex === 5 ? " active" : ""}`}>
          <div className="page-header">
            <h1 className="page-title">{currentPage.headline}</h1>
            <p className="page-desc">{currentPage.description}</p>
          </div>
          {hasData ? (
            <DatasetOverviewChart
              data={history}
              events={events}
              yKey="price_usd"
              label="Whole dataset overview with event markers"
              note="overview chart dùng marker, tooltip và event panel để giữ chart sạch nhưng vẫn đọc được nguyên nhân biến động"
              formatter={(v) => formatNumber(v, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            />
          ) : (
            <EmptyState title="Chưa có dữ liệu để vẽ overview" text="Hãy sync data hoặc nới khoảng ngày." />
          )}
        </section>

        {/* 06 — Forecast */}
        <section className={`page-section${pageIndex === 6 ? " active" : ""}`}>
          <div className="page-header">
            <h1 className="page-title">{currentPage.headline}</h1>
            <p className="page-desc">{currentPage.description}</p>
          </div>

          <div className="chart-card forecast-toolbar-card">
            <div>
              <div className="card-title">Phân tích mô hình ARX · MA · ARMA</div>
              <div className="card-sub">Kết quả chỉ tính sau khi bấm Phân tích — endpoint nặng (~5–15s).</div>
            </div>
            <div className="forecast-toolbar-actions">
              <span className={`pill ${forecastDirty ? "pill-warn" : "pill-ok"}`}>
                {forecastDirty ? "cần chạy lại" : "đã cập nhật"}
              </span>
              <button className="btn-primary" onClick={loadForecast} disabled={forecastLoading}>
                {forecastLoading ? "Đang phân tích…" : "Phân tích"}
              </button>
            </div>
          </div>

          {forecastLoading ? (
            <div className="chart-card">
              <div className="chart-note">Đang huấn luyện và đọc forecast từ backend…</div>
            </div>
          ) : models.length ? (
            <>
              <ForecastContextNote forecastContext={forecastContext} />
              <ForecastHero
                models={models}
                latestActual={modelSuite?.latest_actual}
                forecastContext={forecastContext}
                rankings={modelRankings}
              />
              <ForecastChart model={bestModel} />
              <ForecastReportTable
                models={models}
                latestActual={modelSuite?.latest_actual}
                forecastContext={forecastContext}
                rankings={modelRankings}
              />
            </>
          ) : (
            <EmptyState
              title={forecastRequested ? "Forecast chưa sẵn sàng" : "Chưa chạy phân tích"}
              text={
                forecastRequested
                  ? "Cần đủ dữ liệu để train. Nới khoảng ngày hoặc sync thêm rồi thử lại."
                  : "Chọn khoảng ngày nếu cần, sau đó bấm Phân tích để backend chạy mô hình."
              }
            />
          )}
        </section>

      </main>

      {/* ── Footer strip ─────────────────────────────────────── */}
      <footer className="app-footer">
        <span>SILVER TIMESERI · VITE/REACT · FASTAPI</span>
        <span className={`pill ${hasData ? "pill-ok" : "pill-warn"}`}>
          {hasData ? `${formatNumber(history.length)} rows` : "no data"}
        </span>
        <span>{currentPage.title}</span>
      </footer>

    </div>
  );
}
