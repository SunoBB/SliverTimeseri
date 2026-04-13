import { useMemo } from "react";
import { Line } from "react-chartjs-2";
import {
  CategoryScale,
  Chart as ChartJS,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";

import { formatNumber, formatSignedNumber } from "../lib/formatters";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip);

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
        borderColor: "#2d3540",
        backgroundColor: "transparent",
        borderWidth: 1.6,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.2,
        spanGaps: false,
      },
      {
        label: model?.model_name || "Predicted",
        data: predictedData,
        borderColor: "#2968c8",
        backgroundColor: "rgba(41,104,200,0.06)",
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
            Đường đen = giá thực · Đường xanh = mô hình dự báo trên tập kiểm tra
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
