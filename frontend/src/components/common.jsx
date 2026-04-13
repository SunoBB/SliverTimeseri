import { useEffect, useMemo, useRef, useState } from "react";

import { formatNumber } from "../lib/formatters";
import { AnnotatedLineChart, getCatMeta } from "./chartjs";

export function StatCard({ label, value, subtext, highlight = false }) {
  return (
    <div className={`stat-card${highlight ? " highlight" : ""}`}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      <div className="sub">{subtext}</div>
    </div>
  );
}

export function HeroPanel({ page, summary, history, loading }) {
  const latestRow = history[history.length - 1];

  return (
    <div className="hero-grid">
      <section className="hero-panel hero-panel-primary">
        <div className="section-label">{page.panelLabel}</div>
        <h2 className="hero-title">{page.panelTitle}</h2>
        <p className="hero-copy">{page.panelCopy}</p>
        <div className="hero-facts">
          <div className="hero-fact">
            <span>Range</span>
            <strong>
              {summary.start_date || "--"} → {summary.end_date || "--"}
            </strong>
          </div>
          <div className="hero-fact">
            <span>Latest close</span>
            <strong>
              {loading
                ? "..."
                : formatNumber(summary.end_price_usd, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
            </strong>
          </div>
          <div className="hero-fact">
            <span>Current mode</span>
              <strong>1d / XAGUSD</strong>
          </div>
        </div>
      </section>

      <section className="hero-panel hero-panel-secondary">
        <div className="section-label">Data State</div>
        <div className="hero-kv accent">
          <span className="hero-kv-label">Rows hiện có</span>
          <strong>{loading ? "..." : formatNumber(summary.rows)}</strong>
        </div>
        <div className="hero-kv">
          <span className="hero-kv-label">Mốc dữ liệu mới nhất</span>
          <strong>
            {latestRow ? new Date(latestRow.price_timestamp).toLocaleDateString("en-CA") : "--"}
          </strong>
        </div>
        <div className="hero-kv">
          <span className="hero-kv-label">Giá USD gần nhất</span>
          <strong>
            {loading
              ? "..."
              : formatNumber(summary.end_price_usd, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
          </strong>
        </div>
      </section>
    </div>
  );
}

export function EmptyState({ title, text }) {
  return (
    <div className="empty-panel">
      <div className="empty-title">{title}</div>
      <p>{text}</p>
    </div>
  );
}

export function LineChart({ data, yKey, color, label, note, formatter }) {
  const points = useMemo(() => {
    const values = data
      .map((item) => Number(item[yKey]))
      .filter((value) => Number.isFinite(value));

    if (values.length === 0) {
      return "";
    }

    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;

    return data
      .map((item, index) => {
        const value = Number(item[yKey]);
        if (!Number.isFinite(value)) {
          return null;
        }

        const x = (index / Math.max(data.length - 1, 1)) * 100;
        const y = 100 - ((value - min) / range) * 100;
        return `${x},${y}`;
      })
      .filter(Boolean)
      .join(" ");
  }, [data, yKey]);

  return (
    <div className="chart-card">
      <div className="card-title">{label}</div>
      <div className="card-sub">{note}</div>
      <div className="chart-shell">
        {points ? (
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label={label}>
            <polyline
              points={points}
              fill="none"
              stroke={color}
              strokeWidth="2.2"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
        ) : (
          <div className="chart-empty">Chưa có dữ liệu trong khoảng ngày đã chọn.</div>
        )}
      </div>
      <div className="metric-badges">
        <span className="mbadge">
          Latest <span>{data.length ? formatter(data[data.length - 1][yKey]) : "--"}</span>
        </span>
        <span className="mbadge">
          Rows <span>{formatNumber(data.length)}</span>
        </span>
      </div>
    </div>
  );
}


export function MarketChart({ data, events = [], yKey, label, note, formatter }) {
  const [visibleCount, setVisibleCount] = useState(90);
  const [rangeMode, setRangeMode] = useState("all");
  // windowOffset: how many rows from the END the window finishes.
  // 0 = pinned to the latest bar. Increases as user scrolls left (older).
  const [windowOffset, setWindowOffset] = useState(0);

  // Derived constant: all preprocessed rows (memoised separately so slider max is stable)
  const allRows = useMemo(
    () =>
      data
        .map((item) => ({
          date: new Date(item.price_timestamp).toLocaleDateString("en-CA"),
          value: Number(item[yKey]),
          priceVnd: Number(item.price_vnd),
          usdVndRate: Number(item.usd_vnd_rate),
        }))
        .filter((item) => Number.isFinite(item.value)),
    [data, yKey],
  );

  // Reset pan to latest whenever the range mode changes
  const prevRangeMode = useRef(rangeMode);
  useEffect(() => {
    if (prevRangeMode.current !== rangeMode) {
      setWindowOffset(0);
      prevRangeMode.current = rangeMode;
    }
  }, [rangeMode]);

  const chart = useMemo(() => {
    if (!allRows.length) return null;

    const presetWindowMap = { "1d": 1, "5d": 5, "1m": 30, "3m": 90, "1y": 365, all: allRows.length };
    const winSize = Math.min(Math.max(presetWindowMap[rangeMode] ?? visibleCount, 1), allRows.length);

    // maxOffset: how far left we can slide (0 = latest, maxOffset = oldest possible end)
    const maxOffset = Math.max(allRows.length - winSize, 0);
    const safeOffset = Math.min(Math.max(windowOffset, 0), maxOffset);

    // Window: [windowEnd - winSize, windowEnd)
    const windowEnd = allRows.length - safeOffset;
    const windowStart = Math.max(0, windowEnd - winSize);
    const rows = allRows.slice(windowStart, windowEnd);

    const values    = rows.map((r) => r.value);
    const min       = Math.min(...values);
    const max       = Math.max(...values);
    const range     = max - min || 1;
    const latest    = rows.at(-1);
    const first     = rows[0];
    const change    = latest.value - first.value;
    const changePct = first.value ? (change / first.value) * 100 : 0;

    // Performance always relative to the real global latest, not the window latest
    const globalLatest = allRows.at(-1);
    const performance = [
      { label: "1W", days: 7 },
      { label: "1M", days: 30 },
      { label: "3M", days: 90 },
      { label: "6M", days: 180 },
      { label: "1Y", days: 365 },
    ].map((item) => {
      const anchor = allRows[Math.max(allRows.length - item.days - 1, 0)];
      const pct = anchor?.value ? ((globalLatest.value - anchor.value) / anchor.value) * 100 : 0;
      return { label: item.label, pct, up: pct >= 0 };
    });

    return {
      rows,
      totalRows: allRows.length,
      visibleCount: winSize,
      maxOffset,
      safeOffset,
      latest,
      first,
      min,
      max,
      change,
      changePct,
      rangePosition: ((globalLatest.value - min) / Math.max(range, 1)) * 100,
      performance,
      isPinned: safeOffset === 0,
      isAllView: rangeMode === "all",
    };
  }, [allRows, visibleCount, rangeMode, windowOffset]);

  if (!chart) {
    return (
      <div className="chart-card market-card">
        <div className="card-title">{label}</div>
        <div className="card-sub">{note}</div>
        <div className="chart-empty">Chưa có dữ liệu trong khoảng ngày đã chọn.</div>
      </div>
    );
  }

  const trendPositive = chart.change >= 0;
  const canZoomIn  = chart.visibleCount > 12;
  const canZoomOut = chart.visibleCount < chart.totalRows;
  const canPan     = chart.maxOffset > 0 && !chart.isAllView;

  return (
    <div className="chart-card market-card">
      <div className="market-toolbar">
        <div className="market-toolbar-left">
          <div className="market-search">XAGUSD</div>
          <div className="market-toolbar-group">
            {[["1d","1D"],["5d","5D"],["1m","1M"],["3m","3M"],["1y","1Y"],["all","All"]].map(([mode, text]) => (
              <button
                key={mode}
                type="button"
                className={`market-toolbar-pill${rangeMode === mode ? " active" : ""}`}
                onClick={() => setRangeMode(mode)}
              >
                {text}
              </button>
            ))}
          </div>
        </div>
        <div className="market-toolbar-right">
          <span className="market-toolbar-label">{chart.visibleCount} / {chart.totalRows} phiên</span>
          <button type="button" className="market-toolbar-icon" onClick={() => { setRangeMode("custom"); setVisibleCount((c) => Math.min(chart.totalRows, Math.ceil(c * 1.45))); }} disabled={!canZoomOut}>-</button>
          <button type="button" className="market-toolbar-icon" onClick={() => { setRangeMode("custom"); setVisibleCount((c) => Math.max(12, Math.floor(c * 0.65))); }} disabled={!canZoomIn}>+</button>
        </div>
      </div>

      <div className="market-board">
        <div className="market-main">
          <div className="market-header">
            <div className="market-instrument">
              <div className="market-title-row">
                <strong>XAGUSD</strong>
                <span>Bạc / Đô la Mỹ</span>
                <em>Daily</em>
              </div>
              <div className="market-ohlc">
                O {formatter(chart.first.value)} H {formatter(chart.max)} L {formatter(chart.min)} C {formatter(chart.latest.value)}
              </div>
            </div>
            <div className={`market-change-badge ${trendPositive ? "up" : "down"}`}>
              {trendPositive ? "+" : ""}{formatNumber(chart.changePct, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%
            </div>
          </div>

          <div className="market-shell">
            <AnnotatedLineChart
              rows={chart.rows}
              events={events}
              formatter={formatter}
              height={460}
            />
          </div>

          {/* Pan slider — only shown when there's a sub-window to slide */}
          {canPan && (
            <div className="market-pan-row">
              <span className="market-pan-date">{chart.first.date}</span>
              <input
                type="range"
                className="market-pan-range"
                min="0"
                max={String(chart.maxOffset)}
                step="1"
                // slider right = latest (offset 0), slider left = oldest (offset = max)
                value={String(chart.maxOffset - chart.safeOffset)}
                onChange={(e) => {
                  const sliderVal = Number(e.target.value);
                  setWindowOffset(chart.maxOffset - sliderVal);
                }}
              />
              <span className="market-pan-date">{chart.latest.date}</span>
              {!chart.isPinned && (
                <button
                  type="button"
                  className="market-pan-latest"
                  onClick={() => setWindowOffset(0)}
                >
                  ↳ Mới nhất
                </button>
              )}
            </div>
          )}

          <div className="market-range-tabs">
            {[["1d","1Ngày"],["5d","5Ngày"],["1m","1Tháng"],["3m","3Tháng"],["1y","1Năm"],["all","Tất cả"]].map(([mode, text]) => (
              <span key={mode} className={rangeMode === mode ? "active" : ""} onClick={() => setRangeMode(mode)}>{text}</span>
            ))}
          </div>
        </div>

        <aside className="market-sidepanel">
          <div className="market-side-symbol">XAGUSD</div>
          <div className="market-side-name">Bạc / Đô la Mỹ · FX_IDC</div>
          <div className="market-side-price">{formatter(chart.latest.value)} <span>USD</span></div>
          <div className={`market-side-delta ${trendPositive ? "up" : "down"}`}>
            {trendPositive ? "+" : ""}{formatNumber(chart.change, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ·{" "}
            {trendPositive ? "+" : ""}{formatNumber(chart.changePct, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%
          </div>
          <div className="market-side-strip"><span>Close</span><strong>{formatter(chart.latest.value)}</strong></div>
          <div className="market-side-strip">
            <span>VND/Lượng</span>
            <strong>{Number.isFinite(chart.latest.priceVnd) ? formatNumber(chart.latest.priceVnd, { maximumFractionDigits: 0 }) : "--"}</strong>
          </div>
          <div className="market-side-strip">
            <span>USD/VND</span>
            <strong>{Number.isFinite(chart.latest.usdVndRate) ? formatNumber(chart.latest.usdVndRate, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "--"}</strong>
          </div>
          <div className="market-range-meter">
            <div className="market-range-head">
              <span>{formatter(chart.min)}</span>
              <span>PHẠM VI</span>
              <span>{formatter(chart.max)}</span>
            </div>
            <div className="market-range-bar">
              <div className="market-range-fill" style={{ width: `${Math.min(Math.max(chart.rangePosition, 0), 100)}%` }} />
            </div>
          </div>
          <div className="market-performance">
            <div className="market-performance-title">Hiệu suất</div>
            <div className="market-performance-grid">
              {chart.performance.map((item) => (
                <div key={item.label} className={`market-performance-card ${item.up ? "up" : "down"}`}>
                  <strong>{item.up ? "+" : ""}{formatNumber(item.pct, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%</strong>
                  <span>{item.label}</span>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}


export function DatasetOverviewChart({ data, events = [], yKey, label, note, formatter }) {
  const [activeCategory, setActiveCategory] = useState("all");
  const [selectedEventKey, setSelectedEventKey] = useState(null);

  const rows = useMemo(
    () =>
      data
        .map((item) => ({
          date: new Date(item.price_timestamp).toLocaleDateString("en-CA"),
          value: Number(item[yKey]),
        }))
        .filter((item) => Number.isFinite(item.value)),
    [data, yKey],
  );

  const categories = useMemo(
    () => Array.from(new Set(events.map((e) => e.category).filter(Boolean))),
    [events],
  );

  const filteredEvents = useMemo(
    () => (activeCategory === "all" ? events : events.filter((e) => e.category === activeCategory)),
    [events, activeCategory],
  );

  if (!rows.length) {
    return (
      <div className="chart-card overview-card">
        <div className="card-title">{label}</div>
        <div className="card-sub">{note}</div>
        <div className="chart-empty">Chưa có dữ liệu trong khoảng ngày đã chọn.</div>
      </div>
    );
  }

  return (
    <div className="chart-card overview-card">
      <div className="overview-head">
        <div>
          <div className="card-title overview-title">{label}</div>
          <div className="card-sub overview-subtitle">{note}</div>
        </div>
        <span className="overview-meta">{rows.length} phiên</span>
      </div>

      {/* ── Filter bar ──────────────────────────────────────── */}
      <div className="ev-filter-bar">
        <span className="ev-filter-label">Lọc sự kiện:</span>
        <button
          className={`ev-filter-btn${activeCategory === "all" ? " active" : ""}`}
          onClick={() => setActiveCategory("all")}
        >
          Tất cả
        </button>
        {categories.map((cat) => {
          const meta = getCatMeta(cat);
          return (
            <button
              key={cat}
              className={`ev-filter-btn${activeCategory === cat ? " active" : ""}`}
              style={activeCategory === cat ? { background: meta.bg, color: meta.txt, borderColor: meta.hex } : {}}
              onClick={() => setActiveCategory(cat)}
            >
              {meta.label}
            </button>
          );
        })}
      </div>

      {/* ── Legend ──────────────────────────────────────────── */}
      <div className="ev-legend">
        {categories.map((cat) => {
          const meta = getCatMeta(cat);
          return (
            <span key={cat} className="ev-legend-item">
              <span className="ev-legend-dot" style={{ background: meta.hex }} />
              {meta.label}
            </span>
          );
        })}
      </div>

      {/* ── Chart.js canvas ─────────────────────────────────── */}
      <div className="ev-chart-area">
        <AnnotatedLineChart
          rows={rows}
          events={filteredEvents}
          activeFilter={activeCategory}
          formatter={formatter}
          height={260}
        />
      </div>

      {/* ── Event list ──────────────────────────────────────── */}
      <p className="ev-section-label">Danh mục sự kiện gây sốc giá bạc</p>
      <div className="ev-list">
        {filteredEvents.length ? (
          filteredEvents.map((ev) => {
            const meta = getCatMeta(ev.category);
            const isSelected = selectedEventKey === ev.event_key;
            return (
              <div
                key={ev.event_key}
                className={`ev-card${isSelected ? " selected" : ""}`}
                onClick={() => setSelectedEventKey(isSelected ? null : ev.event_key)}
              >
                <span className="ev-dot" style={{ background: meta.hex }} />
                <div>
                  <div className="ev-title-row">
                    <span className="ev-year">{ev.event_date ? new Date(ev.event_date).getFullYear() : "--"}</span>
                    <span className="ev-title">{ev.title}</span>
                  </div>
                  {ev.summary && <div className="ev-desc">{ev.summary}</div>}
                  {ev.price_impact_summary && (
                    <div className="ev-change" style={{ color: meta.txt }}>{ev.price_impact_summary}</div>
                  )}
                </div>
              </div>
            );
          })
        ) : (
          <div className="chart-empty">Không có sự kiện phù hợp với bộ lọc hiện tại.</div>
        )}
      </div>
    </div>
  );
}

export function StationarityReport({ data, loading }) {
  if (loading) {
    return (
      <div className="chart-card adf-card">
        <div className="card-title">Kiểm định tính dừng — ADF Test</div>
        <div className="chart-note">Đang chạy ADF test…</div>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="chart-card adf-card">
        <div className="card-title">Kiểm định tính dừng — ADF Test</div>
        <div className="chart-note">Chưa có kết quả. Dữ liệu chưa được tải.</div>
      </div>
    );
  }
  if (data.error) {
    return (
      <div className="chart-card adf-card">
        <div className="card-title">Kiểm định tính dừng — ADF Test</div>
        <div className="chart-note adf-error">{data.error}</div>
      </div>
    );
  }

  const { tests = [], conclusion = {}, n_obs, start_date, end_date } = data;
  const d = conclusion.d_recommended ?? "--";
  const verdictOk = d === 0;

  return (
    <div className="chart-card adf-card">
      {/* ── Header ─────────────────────────────────────────── */}
      <div className="adf-header">
        <div>
          <div className="card-title">Kiểm định tính dừng — ADF Test</div>
          <div className="card-sub">
            Augmented Dickey-Fuller · {n_obs} quan sát · {start_date} → {end_date}
          </div>
        </div>
        <div className={`adf-verdict-badge ${verdictOk ? "ok" : "warn"}`}>
          d = {d}
        </div>
      </div>

      {/* ── Test table ─────────────────────────────────────── */}
      <div className="adf-table-wrap">
        <table className="adf-table">
          <thead>
            <tr>
              <th>Chuỗi</th>
              <th>ADF Stat</th>
              <th>p-value</th>
              <th>Lags</th>
              <th>CV 1%</th>
              <th>CV 5%</th>
              <th>CV 10%</th>
              <th>Kết luận</th>
            </tr>
          </thead>
          <tbody>
            {tests.map((t) =>
              t.error ? (
                <tr key={t.label}>
                  <td>{t.label}</td>
                  <td colSpan={7} className="adf-cell-err">{t.error}</td>
                </tr>
              ) : (
                <tr key={t.label} className={t.is_stationary ? "adf-row-ok" : "adf-row-warn"}>
                  <td className="adf-cell-label">{t.label}</td>
                  <td className="adf-cell-mono">{t.test_statistic?.toFixed(4)}</td>
                  <td className="adf-cell-mono">
                    {t.p_value?.toFixed(4)}
                    {t.significance && <span className="adf-sig">{t.significance}</span>}
                  </td>
                  <td className="adf-cell-mono">{t.lags_used}</td>
                  <td className="adf-cell-mono adf-cv">{t.critical_values?.["1%"]?.toFixed(3)}</td>
                  <td className="adf-cell-mono adf-cv">{t.critical_values?.["5%"]?.toFixed(3)}</td>
                  <td className="adf-cell-mono adf-cv">{t.critical_values?.["10%"]?.toFixed(3)}</td>
                  <td>
                    <span className={`adf-pill ${t.is_stationary ? "ok" : "warn"}`}>
                      {t.verdict}
                    </span>
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>

      {/* ── Conclusion ─────────────────────────────────────── */}
      <div className={`adf-conclusion ${verdictOk ? "ok" : "warn"}`}>
        <span className="adf-conclusion-icon">{verdictOk ? "✓" : "!"}</span>
        <div>
          <strong>Kết luận:</strong> {conclusion.summary}
          <div className="adf-sig-note">
            *** p &lt; 0.01 &nbsp;·&nbsp; ** p &lt; 0.05 &nbsp;·&nbsp; * p &lt; 0.10
          </div>
        </div>
      </div>
    </div>
  );
}


export function SummaryGrid({ summary }) {
  const entries = Object.entries(summary || {}).filter(
    ([, value]) => value !== null && value !== undefined,
  );

  if (!entries.length) {
    return <div className="chart-note">Chưa có summary data để hiển thị.</div>;
  }

  return (
    <div className="coef-grid">
      {entries.map(([key, value]) => (
        <div className="coef-card" key={key}>
          <div className="model-name">{key}</div>
          <div className="coef-row">
            <span className="coef-name">value</span>
            <span className="coef-val">
              {typeof value === "number"
                ? formatNumber(value, { maximumFractionDigits: 4 })
                : String(value)}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

export function HistoryTable({ rows }) {
  if (!rows.length) {
    return <div className="chart-note">Database chưa có dữ liệu cho khoảng ngày này.</div>;
  }

  return (
    <div className="dataset-shell">
      <table className="dataset-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>USD/Oz</th>
            <th>VND/Luong</th>
            <th>Silver USD</th>
            <th>Silver VND</th>
            <th>USD/VND</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.symbol}-${row.price_timestamp}`}>
              <td>{new Date(row.price_timestamp).toLocaleDateString("en-CA")}</td>
              <td>{formatNumber(row.price_usd, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
              <td>{formatNumber(row.price_vnd, { maximumFractionDigits: 0 })}</td>
              <td>{formatNumber(row.price_silver_usd, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
              <td>{formatNumber(row.price_silver_vnd, { maximumFractionDigits: 0 })}</td>
              <td>{formatNumber(row.usd_vnd_rate, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TablePagination({ page, totalPages, totalRows, onPrev, onNext }) {
  if (totalRows === 0) {
    return null;
  }

  return (
    <div className="table-pagination">
      <div className="table-pagination-meta">
        <span>{formatNumber(totalRows)} rows</span>
        <strong>
          Page {page} / {totalPages}
        </strong>
      </div>
      <div className="report-pager-actions">
        <button className="report-pager-nav" onClick={onPrev} disabled={page <= 1}>
          Trang trước
        </button>
        <button className="report-pager-nav" onClick={onNext} disabled={page >= totalPages}>
          Trang sau
        </button>
      </div>
    </div>
  );
}
