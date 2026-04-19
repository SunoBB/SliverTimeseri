import { useMemo } from "react";
import { Line, Radar } from "react-chartjs-2";
import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  LinearScale,
  LineElement,
  PointElement,
  RadarController,
  RadialLinearScale,
  Tooltip,
} from "chart.js";

import { formatNumber, formatSignedNumber } from "../lib/formatters";

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement, Tooltip,
  Filler, RadarController, RadialLinearScale,
);

// Consistent color identity per model across all charts
const MODEL_COLORS = {
  ARX:  { line: "#1a7fd4", fill: "rgba(26,127,212,0.13)" },   // blue  — best model
  ARMA: { line: "#7c3aed", fill: "rgba(124,58,237,0.13)" },   // purple
  MA:   { line: "#6b7280", fill: "rgba(107,114,128,0.10)" },  // gray
};
const CONSENSUS_COLOR = { line: "#d97706", fill: "rgba(217,119,6,0.1)" };

function formatDirection(value) {
  if (value === "up") return "↑ Tăng";
  if (value === "down") return "↓ Giảm";
  if (value === "flat") return "→ Đi ngang";
  return "--";
}

function dirClass(value) {
  if (value === "up") return "dir-up";
  if (value === "down") return "dir-down";
  return "dir-flat";
}

function bestModelByMetric(models, metricKey) {
  const valid = models.filter((model) => Number.isFinite(Number(model.metrics?.[metricKey])));
  if (!valid.length) return null;
  return [...valid].sort(
    (left, right) => Number(left.metrics?.[metricKey]) - Number(right.metrics?.[metricKey]),
  )[0];
}

export function ForecastContextNote({ forecastContext }) {
  if (!forecastContext) return null;
  const isStale = forecastContext.latest_data_status === "stale";
  return (
    <div className={`fc-context-note ${isStale ? "fc-context-warn" : "fc-context-ok"}`}>
      {isStale
        ? `DB mới có đến ${forecastContext.latest_data_date}. Forecast đang bù cho ngày ${forecastContext.next_dataset_date} (thiếu ${forecastContext.missing_days} ngày so với hôm nay ${forecastContext.current_vn_date}).`
        : `DB đã có đến ${forecastContext.latest_data_date}. Forecast nhắm tới ngày mai ${forecastContext.next_dataset_date}.`}
    </div>
  );
}

export function ForecastHero({ models, latestActual, forecastContext, rankings }) {
  if (!models.length) return null;

  const bestByDir = models.find((m) => m.model_name === rankings?.best_by_direction);
  const bestByMae = models.find((m) => m.model_name === rankings?.best_by_mae);
  const heroModel = bestByDir || bestByMae || models[0];
  const effectiveRows = Number(heroModel?.train_size ?? 0) + Number(heroModel?.test_size ?? 0);
  const testRatio = effectiveRows > 0 ? (Number(heroModel?.test_size ?? 0) / effectiveRows) * 100 : null;

  const forecast = heroModel?.next_forecast;
  const delta = Number(forecast?.predicted ?? NaN) - Number(latestActual?.price_usd ?? NaN);

  const prices = models.map((m) => Number(m.next_forecast?.predicted)).filter(Number.isFinite);
  const consensus = prices.length ? prices.reduce((a, b) => a + b, 0) / prices.length : null;

  const isCatchUp = forecastContext?.forecast_target_type === "catch_up";

  return (
    <div className="fc-hero">
      <div className="fc-hero-main">
        <div className="fc-hero-kicker">
          <span>{isCatchUp ? "Bù dữ liệu" : "Dự báo ngày mai"}</span>
          <span className="fc-hero-sep">·</span>
          <span>{heroModel.model_name}</span>
          {rankings?.best_by_direction === heroModel.model_name && (
            <span className="fc-badge fc-badge-dir">Best direction</span>
          )}
          {rankings?.best_by_mae === heroModel.model_name &&
            rankings?.best_by_direction !== heroModel.model_name && (
              <span className="fc-badge fc-badge-mae">Best MAE</span>
            )}
        </div>
        <div className="fc-hero-row">
          <div className="fc-hero-price">
            {formatNumber(forecast?.predicted, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
            <span className="fc-hero-unit">USD/oz</span>
          </div>
          <div className={`fc-hero-dir ${dirClass(forecast?.predicted_direction)}`}>
            {formatDirection(forecast?.predicted_direction)}
          </div>
        </div>
        <div className="fc-hero-sub">
          <span className={`fc-delta ${delta > 0 ? "dir-up" : delta < 0 ? "dir-down" : "dir-flat"}`}>
            {formatSignedNumber(delta, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} so với giá hiện tại
          </span>
          <span className="fc-hero-sep">·</span>
          <span className="fc-ci">
            CI 95%: [{formatNumber(forecast?.lower_95, { minimumFractionDigits: 2, maximumFractionDigits: 2 })},{" "}
            {formatNumber(forecast?.upper_95, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}]
          </span>
          <span className="fc-hero-sep">·</span>
          <span className="fc-date">{forecast?.date || "--"}</span>
        </div>
        <div className="fc-hero-sub">
          <span className="fc-date">
            Train/Test: {formatNumber(heroModel?.train_size)} / {formatNumber(heroModel?.test_size)}
          </span>
          <span className="fc-hero-sep">·</span>
          <span className="fc-ci">
            Split hiệu dụng: {formatNumber(testRatio, { maximumFractionDigits: 1 })}% test
          </span>
        </div>
      </div>

      <div className="fc-hero-aside">
        <div className="fc-aside-block">
          <div className="fc-aside-label">Giá gần nhất</div>
          <div className="fc-aside-val">
            {formatNumber(latestActual?.price_usd, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </div>
          <div className="fc-aside-sub">{latestActual?.date || "--"}</div>
        </div>
        <div className="fc-aside-block">
          <div className="fc-aside-label">Consensus ({prices.length} models)</div>
          <div className="fc-aside-val">
            {formatNumber(consensus, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="fc-aside-sub">trung bình tất cả mô hình</div>
        </div>
        <div className="fc-aside-block">
          <div className="fc-aside-label">Train / Test</div>
          <div className="fc-aside-val">
            {formatNumber(heroModel?.train_size)} / {formatNumber(heroModel?.test_size)}
          </div>
          <div className="fc-aside-sub">split của model đang được highlight</div>
        </div>
      </div>
    </div>
  );
}

export function ForecastChart({ model }) {
  const predictions = model?.predictions || [];

  const { labels, actualData, predictedData } = useMemo(() => {
    if (!predictions.length) return { labels: [], actualData: [], predictedData: [] };
    const step = Math.max(1, Math.floor(predictions.length / 80));
    const sampled = predictions.filter((_, i) => i % step === 0 || i === predictions.length - 1);
    return {
      labels: sampled.map((r) => r.date || ""),
      actualData: sampled.map((r) =>
        Number.isFinite(Number(r.actual)) ? Number(r.actual) : null,
      ),
      predictedData: sampled.map((r) =>
        Number.isFinite(Number(r.predicted)) ? Number(r.predicted) : null,
      ),
    };
  }, [predictions]);

  if (!predictions.length) return null;

  const nextForecast = model?.next_forecast;

  const chartData = {
    labels,
    datasets: [
      {
        label: "Actual",
        data: actualData,
        borderColor: "#16a34a",
        backgroundColor: "transparent",
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.2,
        spanGaps: false,
      },
      {
        label: model?.model_name || "Predicted",
        data: predictedData,
        borderColor: "#e03535",
        backgroundColor: "rgba(224,53,53,0.07)",
        borderWidth: 1.8,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.2,
        spanGaps: false,
        fill: false,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#1a1410",
        titleColor: "#c8b89a",
        bodyColor: "#e8d9c0",
        borderColor: "#3d2f1a",
        borderWidth: 1,
        padding: 8,
        callbacks: {
          label: (ctx) => {
            const v = ctx.raw;
            if (v == null) return null;
            return `${ctx.dataset.label}: ${v.toFixed(2)}`;
          },
        },
      },
    },
    scales: {
      x: {
        ticks: {
          color: "#7a6a55",
          font: { size: 10, family: "IBM Plex Mono, monospace" },
          maxTicksLimit: 8,
          maxRotation: 0,
        },
        grid: { color: "rgba(0,0,0,0.06)" },
        border: { color: "rgba(0,0,0,0.12)" },
      },
      y: {
        ticks: {
          color: "#7a6a55",
          font: { size: 10, family: "IBM Plex Mono, monospace" },
          callback: (v) => v.toFixed(0),
        },
        grid: { color: "rgba(0,0,0,0.06)" },
        border: { color: "rgba(0,0,0,0.12)" },
      },
    },
  };

  return (
    <div className="chart-card fc-chart-card">
      <div className="fc-chart-head">
        <div>
          <div className="card-title">{model?.model_name} — Actual vs Predicted (test set)</div>
          <div className="card-sub">
            Đường xanh lá = giá thực · Đường đỏ = mô hình dự báo trên tập kiểm tra
          </div>
        </div>
        <div className="fc-chart-legend">
          <span>
            <i className="fc-swatch-actual" />
            Actual
          </span>
          <span>
            <i className="fc-swatch-predicted" />
            {model?.model_name}
          </span>
        </div>
      </div>
      <div style={{ height: 280 }}>
        <Line data={chartData} options={options} />
      </div>
      {nextForecast && (
        <div className="fc-chart-footer">
          <span className="fc-forecast-pill">
            Dự báo {nextForecast.date}:{" "}
            <strong>
              {formatNumber(nextForecast.predicted, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </strong>{" "}
            USD/oz · {formatDirection(nextForecast.predicted_direction)} · CI [{formatNumber(nextForecast.lower_95, { minimumFractionDigits: 2, maximumFractionDigits: 2 })},{" "}
            {formatNumber(nextForecast.upper_95, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}]
          </span>
        </div>
      )}
    </div>
  );
}

export function ForecastEvaluationPanel({ models, rankings }) {
  const summary = useMemo(() => {
    if (!models.length) return null;

    const maeBest = bestModelByMetric(models, "mae");
    const rmseBest = bestModelByMetric(models, "rmse");
    const mapeBest = bestModelByMetric(models, "mape");
    const directionBest = models.find((model) => model.model_name === rankings?.best_by_direction) || null;

    const metricConfig = [
      {
        key: "mae",
        label: "MAE",
        note: "MAE thấp hơn: sai số trung bình nhỏ hơn",
        color: "#2968c8",
        best: maeBest?.model_name ?? null,
      },
      {
        key: "rmse",
        label: "RMSE",
        note: "RMSE thấp hơn: ít lỗi lớn hơn",
        color: "#d85a30",
        best: rmseBest?.model_name ?? null,
      },
      {
        key: "mape",
        label: "MAPE",
        note: "MAPE thấp hơn: sai số tương đối theo %",
        color: "#158a67",
        best: mapeBest?.model_name ?? null,
      },
    ];

    return {
      metricConfig,
      maeBest,
      rmseBest,
      mapeBest,
      directionBest,
      confirmedModel: maeBest || rmseBest || mapeBest || models[0],
    };
  }, [models, rankings]);

  if (!summary) return null;

  return (
    <div className="chart-card fc-eval-card">
      <div className="fc-eval-head">
        <div>
          <div className="card-title">Đánh giá độ chính xác mô hình</div>
          <div className="card-sub">
            Xếp hạng theo tập test: ưu tiên MAE, xem thêm RMSE, MAPE và direction accuracy để xác nhận model phù hợp.
          </div>
        </div>
        <div className="fc-eval-confirm">
          <span className="fc-eval-confirm-label">Model đề xuất</span>
          <strong>{summary.confirmedModel?.model_name || "--"}</strong>
          <span className="fc-eval-confirm-sub">ưu tiên theo MAE thấp nhất</span>
        </div>
      </div>

      <div className="fc-eval-grid">
        <div className="fc-eval-summary">
          <div className="fc-eval-badge">
            <span>Best MAE</span>
            <strong>{summary.maeBest?.model_name || "--"}</strong>
            <em>{formatNumber(summary.maeBest?.metrics?.mae, { maximumFractionDigits: 3 })}</em>
          </div>
          <div className="fc-eval-badge">
            <span>Best RMSE</span>
            <strong>{summary.rmseBest?.model_name || "--"}</strong>
            <em>{formatNumber(summary.rmseBest?.metrics?.rmse, { maximumFractionDigits: 3 })}</em>
          </div>
          <div className="fc-eval-badge">
            <span>Best MAPE</span>
            <strong>{summary.mapeBest?.model_name || "--"}</strong>
            <em>{formatNumber(summary.mapeBest?.metrics?.mape, { maximumFractionDigits: 3 })}%</em>
          </div>
          <div className="fc-eval-badge">
            <span>Best Direction</span>
            <strong>{summary.directionBest?.model_name || "--"}</strong>
            <em>{formatNumber(summary.directionBest?.direction_backtest?.accuracy, { maximumFractionDigits: 1 })}% hit</em>
          </div>
        </div>

        <div className="fc-eval-metrics">
          <table className="fc-metrics-table">
            <thead>
              <tr>
                <th>Model</th>
                <th>MAE <span className="fc-mt-hint">↓ thấp hơn tốt hơn</span></th>
                <th>RMSE <span className="fc-mt-hint">↓</span></th>
                <th>MAPE <span className="fc-mt-hint">↓</span></th>
                <th>Direction % <span className="fc-mt-hint">↑ cao hơn tốt hơn</span></th>
              </tr>
            </thead>
            <tbody>
              {models.map((model) => {
                const isBestMae  = model.model_name === summary.maeBest?.model_name;
                const isBestRmse = model.model_name === summary.rmseBest?.model_name;
                const isBestMape = model.model_name === summary.mapeBest?.model_name;
                const isBestDir  = model.model_name === summary.directionBest?.model_name;
                return (
                  <tr key={model.model_name}>
                    <td className="fc-mt-model">{model.model_name}</td>
                    <td className={`fc-mt-val${isBestMae ? " fc-mt-best" : ""}`}>
                      {formatNumber(model.metrics?.mae, { maximumFractionDigits: 3 })}
                      {isBestMae && <span className="fc-badge fc-badge-mae">Best</span>}
                    </td>
                    <td className={`fc-mt-val${isBestRmse ? " fc-mt-best" : ""}`}>
                      {formatNumber(model.metrics?.rmse, { maximumFractionDigits: 3 })}
                      {isBestRmse && <span className="fc-badge fc-badge-mae">Best</span>}
                    </td>
                    <td className={`fc-mt-val${isBestMape ? " fc-mt-best" : ""}`}>
                      {formatNumber(model.metrics?.mape, { maximumFractionDigits: 3 })}%
                      {isBestMape && <span className="fc-badge fc-badge-mae">Best</span>}
                    </td>
                    <td className={`fc-mt-val${isBestDir ? " fc-mt-best" : ""}`}>
                      {formatNumber(model.direction_backtest?.accuracy, { maximumFractionDigits: 1 })}%
                      {isBestDir && <span className="fc-badge fc-badge-dir">Best</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export function ForecastReportTable({ models, latestActual, forecastContext, rankings }) {
  if (!models.length) return null;

  const sorted = [...models].sort(
    (a, b) =>
      Number(b.direction_backtest?.accuracy ?? -Infinity) -
        Number(a.direction_backtest?.accuracy ?? -Infinity) ||
      Number(a.metrics?.mae ?? Infinity) - Number(b.metrics?.mae ?? Infinity),
  );

  const isCatchUp = forecastContext?.forecast_target_type === "catch_up";

  return (
    <div className="chart-card">
      <div className="card-title">Bảng so sánh mô hình</div>
      <div className="card-sub">
        {isCatchUp
          ? `Dự báo kỳ kế tiếp (DB dừng ở ${forecastContext?.latest_data_date || "--"})`
          : "Dự báo ngày mai — metrics tính trên tập test, sắp xếp theo hit rate giảm dần"}
      </div>
      <div className="dataset-shell">
        <table className="dataset-table fc-report-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Model</th>
              <th>Train / Test</th>
              <th>Ngày dự báo</th>
              <th>Giá dự báo</th>
              <th>Hướng</th>
              <th>∆ vs Hiện tại</th>
              <th>CI 95%</th>
              <th>Hit%</th>
              <th>Đúng / Mẫu</th>
              <th>MAE</th>
              <th>MAPE</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((m, i) => {
              const delta =
                Number(m.next_forecast?.predicted ?? NaN) -
                Number(latestActual?.price_usd ?? NaN);
              const dir = m.next_forecast?.predicted_direction;
              const isBestDir = m.model_name === rankings?.best_by_direction;
              const isBestMae = m.model_name === rankings?.best_by_mae;
              return (
                <tr key={m.model_name} className={i === 0 ? "fc-row-best" : ""}>
                  <td className="fc-rank">
                    {i === 0 ? "★" : `${i + 1}`}
                  </td>
                  <td>
                    <span className="fc-model-name">{m.model_name}</span>
                    {isBestDir && <span className="fc-badge fc-badge-dir">Dir</span>}
                    {isBestMae && <span className="fc-badge fc-badge-mae">MAE</span>}
                  </td>
                  <td className="fc-mono">
                    {formatNumber(m.train_size)} / {formatNumber(m.test_size)}
                  </td>
                  <td className="fc-mono">{m.next_forecast?.date || "--"}</td>
                  <td className="fc-mono fc-price-cell">
                    {formatNumber(m.next_forecast?.predicted, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </td>
                  <td className={`fc-dir-cell ${dirClass(dir)}`}>
                    {formatDirection(dir)}
                  </td>
                  <td
                    className={`fc-mono ${delta > 0 ? "dir-up" : delta < 0 ? "dir-down" : "dir-flat"}`}
                  >
                    {formatSignedNumber(delta, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </td>
                  <td className="fc-mono fc-ci-cell">
                    [{formatNumber(m.next_forecast?.lower_95, { minimumFractionDigits: 2, maximumFractionDigits: 2 })},
                    {" "}
                    {formatNumber(m.next_forecast?.upper_95, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}]
                  </td>
                  <td className="fc-mono fc-hit-cell">
                    {formatNumber(m.direction_backtest?.accuracy, { maximumFractionDigits: 1 })}%
                  </td>
                  <td className="fc-mono">
                    {formatNumber(m.direction_backtest?.correct)} /{" "}
                    {formatNumber(m.direction_backtest?.samples)}
                  </td>
                  <td className="fc-mono">
                    {formatNumber(m.metrics?.mae, { maximumFractionDigits: 2 })}
                  </td>
                  <td className="fc-mono">
                    {formatNumber(m.metrics?.mape, { maximumFractionDigits: 2 })}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ForecastHorizonSelector({ horizon, onChange }) {
  return (
    <div className="fc-horizon-sel">
      {[
        { val: 1,  label: "1D" },
        { val: 7,  label: "7D" },
        { val: 30, label: "30D" },
      ].map(({ val, label }) => (
        <button
          key={val}
          className={`fc-horizon-btn${horizon === val ? " active" : ""}`}
          onClick={() => onChange(val)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export function ForecastMultiDayChart({ models, latestActual, horizon }) {
  const { labels, datasets, snapshotInfo } = useMemo(() => {
    const sliced = models.map((m) => ({
      ...m,
      multi_forecast: (m.multi_forecast || []).slice(0, horizon),
    }));
    const forecastDates = sliced.find((m) => m.multi_forecast.length > 0)
      ?.multi_forecast.map((f) => f.date) || [];
    if (!forecastDates.length) return { labels: [], datasets: [], snapshotInfo: [] };

    const anchorDate  = latestActual?.date;
    const anchorPrice = Number(latestActual?.price_usd);
    const allLabels   = anchorDate ? [anchorDate, ...forecastDates] : forecastDates;
    const bridge      = (arr) => (anchorDate ? [anchorPrice, ...arr] : arr);

    // Inverse-MAE weighted consensus
    const invMaeSum = models.reduce((s, m) => {
      const v = Number(m.metrics?.mae);
      return s + (Number.isFinite(v) ? 1 / Math.max(v, 0.001) : 0);
    }, 0);
    const weights = Object.fromEntries(
      models.map((m) => {
        const v = Number(m.metrics?.mae);
        return [m.model_name, Number.isFinite(v) && invMaeSum > 0
          ? (1 / Math.max(v, 0.001)) / invMaeSum
          : 1 / models.length];
      }),
    );
    const consensusData = forecastDates.map((_, i) =>
      parseFloat(sliced.reduce((s, m) => {
        const p = Number(m.multi_forecast[i]?.predicted);
        return s + (Number.isFinite(p) ? p * (weights[m.model_name] || 0) : 0);
      }, 0).toFixed(2)),
    );

    // Anchor dataset (single dot at last actual price)
    const anchorDataset = anchorDate ? {
      label: "Actual",
      data: [anchorPrice, ...forecastDates.map(() => null)],
      borderColor: "#333333",
      backgroundColor: "transparent",
      borderWidth: 0,
      pointRadius: [6, ...forecastDates.map(() => 0)],
      pointBackgroundColor: "#333333",
      pointHoverRadius: 6,
      tension: 0,
      fill: false,
    } : null;

    // Per-model: lower band + upper band (fill) + predicted line
    const modelDatasets = sliced.flatMap((model) => {
      const color = MODEL_COLORS[model.model_name] || { line: "#999", fill: "rgba(153,153,153,0.1)" };
      const forecasts = model.multi_forecast;
      const lowerArr  = forecasts.map((f) => Number(f.lower_95));
      const upperArr  = forecasts.map((f) => Number(f.upper_95));
      const predArr   = forecasts.map((f) => Number(f.predicted));
      const last      = bridge(predArr).length - 1;

      return [
        // Lower bound (fill target, invisible)
        {
          label: "", data: bridge(lowerArr),
          fill: false, borderColor: "transparent", backgroundColor: "transparent",
          borderWidth: 0, pointRadius: 0, pointHoverRadius: 0,
          isCiBand: true, modelGroup: model.model_name,
        },
        // Upper bound — fills toward lower (CI shading)
        {
          label: "", data: bridge(upperArr),
          fill: "-1", borderColor: "transparent", backgroundColor: color.fill,
          borderWidth: 0, pointRadius: 0, pointHoverRadius: 0,
          isCiBand: true, modelGroup: model.model_name,
        },
        // Predicted line
        {
          label: model.model_name, data: bridge(predArr),
          borderColor: color.line, backgroundColor: "transparent",
          borderWidth: 2, borderDash: [6, 4],
          pointRadius: bridge(predArr).map((_, i) => (i === 0 ? 0 : i === last ? 4 : 0)),
          pointBackgroundColor: color.line, pointHoverRadius: 4,
          tension: 0.2, fill: false,
          modelGroup: model.model_name,
        },
      ];
    });

    // Consensus line (amber, no CI)
    const consensusBridged = bridge(consensusData);
    const consensusDataset = {
      label: "Consensus",
      data: consensusBridged,
      borderColor: CONSENSUS_COLOR.line,
      backgroundColor: "transparent",
      borderWidth: 2.2,
      borderDash: [3, 3],
      pointRadius: consensusBridged.map((_, i) => (i === 0 ? 0 : i === consensusBridged.length - 1 ? 5 : 0)),
      pointBackgroundColor: CONSENSUS_COLOR.line,
      pointHoverRadius: 4,
      tension: 0.2,
      fill: false,
    };

    const allDatasets = [
      ...(anchorDataset ? [anchorDataset] : []),
      ...modelDatasets,
      consensusDataset,
    ];

    const snapshotInfo = models.map((m) => ({
      name: m.model_name,
      mae: Number(m.metrics?.mae),
      color: MODEL_COLORS[m.model_name]?.line || "#999",
    }));

    return { labels: allLabels, datasets: allDatasets, snapshotInfo };
  }, [models, latestActual, horizon]);

  if (!labels.length) return null;

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: {
        display: true,
        position: "top",
        labels: {
          filter: (item, data) => !data.datasets[item.datasetIndex]?.isCiBand && data.datasets[item.datasetIndex]?.label,
          color: "#7a6a55",
          font: { size: 10, family: "IBM Plex Mono, monospace" },
          boxWidth: 24, padding: 14,
        },
        onClick: (e, legendItem, legend) => {
          const chart = legend.chart;
          const clicked = chart.data.datasets[legendItem.datasetIndex];
          const group   = clicked?.modelGroup;
          const meta0   = chart.getDatasetMeta(legendItem.datasetIndex);
          const nextHidden = !meta0.hidden;
          chart.data.datasets.forEach((ds, i) => {
            if (i === legendItem.datasetIndex || (group && ds.modelGroup === group && ds.isCiBand)) {
              chart.getDatasetMeta(i).hidden = nextHidden;
            }
          });
          chart.update();
        },
      },
      tooltip: {
        backgroundColor: "#1a1410", titleColor: "#c8b89a", bodyColor: "#e8d9c0",
        borderColor: "#3d2f1a", borderWidth: 1, padding: 8,
        filter: (item) => !item.dataset.isCiBand && item.raw != null,
        callbacks: {
          label: (ctx) => ctx.raw == null ? null
            : `${ctx.dataset.label}: ${Number(ctx.raw).toFixed(2)} USD/oz`,
        },
      },
    },
    scales: {
      x: {
        ticks: { color: "#7a6a55", font: { size: 10, family: "IBM Plex Mono, monospace" }, maxTicksLimit: 10, maxRotation: 0 },
        grid: { color: "rgba(0,0,0,0.06)" }, border: { color: "rgba(0,0,0,0.12)" },
      },
      y: {
        ticks: { color: "#7a6a55", font: { size: 10, family: "IBM Plex Mono, monospace" }, callback: (v) => v.toFixed(1) },
        grid: { color: "rgba(0,0,0,0.06)" }, border: { color: "rgba(0,0,0,0.12)" },
      },
    },
  };

  return (
    <div className="chart-card">
      <div className="fc-chart-head">
        <div>
          <div className="card-title">Dự báo {horizon} ngày tới — ARX · ARMA · MA · Consensus</div>
          <div className="card-sub">
            Vùng mờ = CI 95% · Đường đứt = từng model · Vàng = Consensus (trọng số theo MAE)
          </div>
        </div>
      </div>
      <div style={{ height: 300 }}>
        <Line data={{ labels, datasets }} options={chartOptions} />
      </div>
      {snapshotInfo.length > 0 && (
        <div className="fc-backtest-snapshot">
          <span className="fc-bts-label">Sai số test set:</span>
          {snapshotInfo.map((info) => (
            <span key={info.name} className="fc-bts-item">
              <i className="fc-bts-dot" style={{ background: info.color }} />
              {info.name} ±{Number.isFinite(info.mae) ? info.mae.toFixed(2) : "--"} USD
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function ForecastRadarChart({ models }) {
  const radarData = useMemo(() => {
    if (!models.length) return null;

    const get = (m, key) => Number(m.metrics?.[key]);
    const getDir = (m) => Number(m.direction_backtest?.accuracy);

    const maeVals  = models.map((m) => get(m, "mae")).filter(Number.isFinite);
    const rmseVals = models.map((m) => get(m, "rmse")).filter(Number.isFinite);
    const mapeVals = models.map((m) => get(m, "mape")).filter(Number.isFinite);
    const dirVals  = models.map((m) => getDir(m)).filter(Number.isFinite);

    const invertScore = (val, vals) => {
      if (!Number.isFinite(val) || !vals.length) return 50;
      const lo = Math.min(...vals), hi = Math.max(...vals);
      if (hi === lo) return 50;
      return (1 - (val - lo) / (hi - lo)) * 100;
    };
    const directScore = (val, vals) => {
      if (!Number.isFinite(val) || !vals.length) return 0;
      const hi = Math.max(...vals);
      return hi === 0 ? 0 : (val / hi) * 100;
    };

    return {
      labels: ["MAE ↓", "RMSE ↓", "MAPE ↓", "Direction %\n(Up/Down hit)"],
      datasets: models.map((model) => {
        const color = MODEL_COLORS[model.model_name] || { line: "#999999", fill: "rgba(153,153,153,0.15)" };
        // Store raw values for tooltip alongside normalized scores
        const rawValues = [
          get(model, "mae"),
          get(model, "rmse"),
          get(model, "mape"),
          getDir(model),
        ];
        return {
          label: model.model_name,
          data: [
            invertScore(get(model, "mae"),  maeVals),
            invertScore(get(model, "rmse"), rmseVals),
            invertScore(get(model, "mape"), mapeVals),
            directScore(getDir(model),      dirVals),
          ],
          rawValues,
          borderColor: color.line,
          backgroundColor: color.fill,
          borderWidth: 1.8,
          pointRadius: 3,
          pointBackgroundColor: color.line,
        };
      }),
    };
  }, [models]);

  if (!radarData) return null;

  const radarOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: {
        display: true,
        position: "bottom",
        labels: { color: "#7a6a55", font: { size: 10, family: "IBM Plex Mono, monospace" }, boxWidth: 18, padding: 12 },
      },
      tooltip: {
        backgroundColor: "#1a1410",
        titleColor: "#c8b89a",
        bodyColor: "#e8d9c0",
        borderColor: "#3d2f1a",
        borderWidth: 1,
        padding: 8,
        callbacks: {
          label: (ctx) => {
            const raw = ctx.dataset.rawValues?.[ctx.dataIndex];
            const score = Number(ctx.raw).toFixed(0);
            const isDir = ctx.dataIndex === 3;
            const rawStr = raw != null && Number.isFinite(raw)
              ? isDir ? ` = ${raw.toFixed(1)}% hit rate` : ` = ${raw.toFixed(3)}`
              : "";
            return `${ctx.dataset.label}: score ${score}${rawStr}`;
          },
        },
      },
    },
    scales: {
      r: {
        min: 0,
        max: 100,
        ticks: {
          color: "#7a6a55",
          font: { size: 9, family: "IBM Plex Mono, monospace" },
          stepSize: 25,
          backdropColor: "transparent",
        },
        pointLabels: {
          color: "#5a4a35",
          font: { size: 11, family: "IBM Plex Mono, monospace" },
        },
        grid: { color: "rgba(0,0,0,0.08)" },
        angleLines: { color: "rgba(0,0,0,0.1)" },
      },
    },
  };

  return (
    <div className="chart-card fc-radar-card">
      <div className="card-title">Model Radar</div>
      <div className="card-sub">Score 0–100 (cao hơn = tốt hơn) · MAE/RMSE/MAPE đã invert · Direction % chuẩn hóa</div>
      <div style={{ height: 300 }}>
        <Radar data={radarData} options={radarOptions} />
      </div>
    </div>
  );
}
