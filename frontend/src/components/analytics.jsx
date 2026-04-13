import { useMemo } from "react";

import { formatNumber, formatSignedNumber } from "../lib/formatters";

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function mean(values) {
  if (!values.length) {
    return 0;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function quantile(sortedValues, ratio) {
  if (!sortedValues.length) {
    return 0;
  }
  const index = (sortedValues.length - 1) * ratio;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) {
    return sortedValues[lower];
  }
  const weight = index - lower;
  return sortedValues[lower] * (1 - weight) + sortedValues[upper] * weight;
}

function movingAverage(rows, key, window) {
  return rows.map((row, index) => {
    const start = Math.max(0, index - window + 1);
    const slice = rows.slice(start, index + 1).map((item) => Number(item[key])).filter(Number.isFinite);
    return {
      date: row.date,
      value: slice.length ? mean(slice) : NaN,
    };
  });
}

function buildPolyline(points, xScale, yScale) {
  return points
    .filter((point) => Number.isFinite(point.value))
    .map((point, index, array) => {
      const x = xScale(point.index ?? index, array.length);
      const y = yScale(point.value);
      return `${x},${y}`;
    })
    .join(" ");
}

function ChartCard({ title, note, children, tags = [] }) {
  return (
    <article className="analysis-card">
      <div className="analysis-head">
        <div>
          <div className="card-title">{title}</div>
          <div className="card-sub">{note}</div>
        </div>
        {tags.length ? (
          <div className="analysis-tags">
            {tags.map((tag) => (
              <span key={tag} className="tag tag-blue">
                {tag}
              </span>
            ))}
          </div>
        ) : null}
      </div>
      {children}
    </article>
  );
}

function ChartEmpty({ text = "Không đủ dữ liệu để hiển thị." }) {
  return <div className="chart-empty">{text}</div>;
}

function TrendWithMAChart({ rows }) {
  const chart = useMemo(() => {
    const points = rows
      .map((row, index) => ({
        index,
        date: row.date,
        value: row.usd,
      }))
      .filter((point) => Number.isFinite(point.value));

    if (points.length < 2) {
      return null;
    }

    const ma10 = movingAverage(rows, "usd", 10).map((item, index) => ({ ...item, index }));
    const ma20 = movingAverage(rows, "usd", 20).map((item, index) => ({ ...item, index }));
    const ma50 = movingAverage(rows, "usd", 50).map((item, index) => ({ ...item, index }));
    const values = [
      ...points.map((point) => point.value),
      ...ma10.map((point) => point.value),
      ...ma20.map((point) => point.value),
      ...ma50.map((point) => point.value),
    ].filter(Number.isFinite);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = (max - min || 1) * 0.12;
    const domainMin = min - padding;
    const domainMax = max + padding;
    const domainRange = domainMax - domainMin || 1;
    const xScale = (index, length = points.length) => 6 + (index / Math.max(length - 1, 1)) * 88;
    const yScale = (value) => 10 + ((domainMax - value) / domainRange) * 68;
    const yTicks = Array.from({ length: 5 }, (_, index) => {
      const ratio = index / 4;
      return {
        y: 10 + ratio * 68,
        value: domainMax - ratio * domainRange,
      };
    });
    const xTicks = [0, Math.floor((points.length - 1) / 2), points.length - 1]
      .filter((value, index, array) => array.indexOf(value) === index)
      .map((index) => ({
        x: xScale(index),
        label: points[index]?.date?.slice(0, 10) ?? "--",
      }));

    return {
      latest: points.at(-1),
      min: Math.min(...points.map((point) => point.value)),
      max: Math.max(...points.map((point) => point.value)),
      line: buildPolyline(points, xScale, yScale),
      ma10: buildPolyline(ma10, xScale, yScale),
      ma20: buildPolyline(ma20, xScale, yScale),
      ma50: buildPolyline(ma50, xScale, yScale),
      yTicks,
      xTicks,
      bullish:
        Number.isFinite(ma10.at(-1)?.value) &&
        Number.isFinite(ma20.at(-1)?.value) &&
        Number.isFinite(ma10.at(-1)?.value) &&
        ma10.at(-1).value >= ma20.at(-1).value,
    };
  }, [rows]);

  return (
    <ChartCard
      title="Line chart + Moving Average"
      note="Đọc xu hướng chính của `price_usd` theo thời gian, đồng thời thêm MA10, MA20 và MA50 để làm mượt nhịp biến động."
      tags={["price_usd", "MA10", "MA20", "MA50"]}
    >
      {chart ? (
        <>
          <div className="analysis-chart-shell analysis-chart-shell-lg">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="silver trend chart">
              {chart.yTicks.map((tick) => (
                <g key={`trend-y-${tick.y}`}>
                  <line x1="6" x2="94" y1={tick.y} y2={tick.y} className="analysis-grid-line" />
                  <text x="95.5" y={tick.y + 0.8} className="analysis-axis-text">
                    {formatNumber(tick.value, { maximumFractionDigits: 0 })}
                  </text>
                </g>
              ))}
              {chart.xTicks.map((tick) => (
                <text key={`trend-x-${tick.x}`} x={tick.x} y="92" textAnchor="middle" className="analysis-axis-text">
                  {tick.label}
                </text>
              ))}
              <polyline points={chart.line} fill="none" className="analysis-line-primary" vectorEffect="non-scaling-stroke" />
              <polyline points={chart.ma10} fill="none" className="analysis-line-ma10" vectorEffect="non-scaling-stroke" />
              <polyline points={chart.ma20} fill="none" className="analysis-line-ma20" vectorEffect="non-scaling-stroke" />
              <polyline points={chart.ma50} fill="none" className="analysis-line-ma50" vectorEffect="non-scaling-stroke" />
            </svg>
          </div>
          <div className="analysis-legend">
            <span><i className="legend-swatch analysis-primary" />Close</span>
            <span><i className="legend-swatch analysis-ma10" />MA10</span>
            <span><i className="legend-swatch analysis-ma20" />MA20</span>
            <span><i className="legend-swatch analysis-ma50" />MA50</span>
          </div>
          <div className="analysis-metrics">
            <span className="mbadge">Latest <strong>{formatNumber(chart.latest.value, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong></span>
            <span className="mbadge">Range <strong>{formatNumber(chart.min, { maximumFractionDigits: 2 })} → {formatNumber(chart.max, { maximumFractionDigits: 2 })}</strong></span>
            <span className={`mbadge ${chart.bullish ? "positive" : "negative"}`}>Signal <strong>{chart.bullish ? "MA10 > MA20" : "MA10 < MA20"}</strong></span>
          </div>
        </>
      ) : (
        <ChartEmpty />
      )}
    </ChartCard>
  );
}

function ReturnChart({ rows }) {
  const chart = useMemo(() => {
    const points = rows
      .map((row, index) => {
        if (index === 0 || !Number.isFinite(rows[index - 1]?.usd) || !Number.isFinite(row.usd) || rows[index - 1].usd === 0) {
          return null;
        }
        return {
          index: index - 1,
          date: row.date,
          value: ((row.usd - rows[index - 1].usd) / rows[index - 1].usd) * 100,
        };
      })
      .filter(Boolean);

    if (points.length < 2) {
      return null;
    }

    const absMax = Math.max(...points.map((point) => Math.abs(point.value)), 0.2);
    const domainMin = -absMax * 1.2;
    const domainMax = absMax * 1.2;
    const domainRange = domainMax - domainMin || 1;
    const xScale = (index, length = points.length) => 6 + (index / Math.max(length - 1, 1)) * 88;
    const yScale = (value) => 12 + ((domainMax - value) / domainRange) * 64;
    const zeroY = yScale(0);

    return {
      points,
      zeroY,
      bars: points.map((point, index) => {
        const x = xScale(index);
        const y = yScale(point.value);
        return {
          ...point,
          x,
          y,
          height: Math.abs(y - zeroY),
          positive: point.value >= 0,
        };
      }),
      maxGain: Math.max(...points.map((point) => point.value)),
      maxDrop: Math.min(...points.map((point) => point.value)),
    };
  }, [rows]);

  return (
    <ChartCard
      title="Return chart"
      note="Biến động phần trăm theo từng phiên giúp nhìn rõ giai đoạn tăng nóng, giảm sâu và các phiên bất thường thay vì chỉ nhìn giá tuyệt đối."
      tags={["daily return", "% change"]}
    >
      {chart ? (
        <>
          <div className="analysis-chart-shell">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="return chart">
              <line x1="6" x2="94" y1={chart.zeroY} y2={chart.zeroY} className="analysis-zero-line" />
              {chart.bars.map((bar) => (
                <rect
                  key={`return-${bar.date}`}
                  x={bar.x - 0.55}
                  y={Math.min(bar.y, chart.zeroY)}
                  width="1.1"
                  height={Math.max(bar.height, 0.6)}
                  className={bar.positive ? "analysis-bar-positive" : "analysis-bar-negative"}
                />
              ))}
            </svg>
          </div>
          <div className="analysis-metrics">
            <span className="mbadge positive">Max gain <strong>{formatSignedNumber(chart.maxGain, { maximumFractionDigits: 2 })}%</strong></span>
            <span className="mbadge negative">Max drop <strong>{formatSignedNumber(chart.maxDrop, { maximumFractionDigits: 2 })}%</strong></span>
          </div>
        </>
      ) : (
        <ChartEmpty />
      )}
    </ChartCard>
  );
}

function CandlestickChart({ rows }) {
  const chart = useMemo(() => {
    const candles = rows
      .map((row, index) => {
        if (!Number.isFinite(row.usd)) {
          return null;
        }
        const previousClose = Number.isFinite(rows[index - 1]?.usd) ? rows[index - 1].usd : row.usd;
        const open = previousClose;
        const close = row.usd;
        const high = Math.max(open, close);
        const low = Math.min(open, close);
        return {
          index,
          date: row.date,
          open,
          close,
          high,
          low,
          up: close >= open,
        };
      })
      .filter(Boolean);

    if (candles.length < 2) {
      return null;
    }

    const visible = candles.slice(-60);
    const values = visible.flatMap((item) => [item.high, item.low]).filter(Number.isFinite);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = (max - min || 1) * 0.1;
    const domainMin = min - padding;
    const domainMax = max + padding;
    const domainRange = domainMax - domainMin || 1;
    const xScale = (index, length = visible.length) => 8 + (index / Math.max(length - 1, 1)) * 84;
    const yScale = (value) => 10 + ((domainMax - value) / domainRange) * 72;

    return {
      candles: visible.map((candle, index) => ({
        ...candle,
        x: xScale(index),
        openY: yScale(candle.open),
        closeY: yScale(candle.close),
        highY: yScale(candle.high),
        lowY: yScale(candle.low),
      })),
      latest: visible.at(-1),
    };
  }, [rows]);

  return (
    <ChartCard
      title="Candlestick chart"
      note="Dùng pseudo-OHLC từ chuỗi đóng cửa ngày: `open = close phiên trước`, `high/low = max/min(open, close)` để đọc nhịp đảo chiều gần nhất."
      tags={["synthetic OHLC", "price_usd"]}
    >
      {chart ? (
        <>
          <div className="analysis-chart-shell">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="candlestick chart">
              {chart.candles.map((candle) => (
                <g key={`candle-${candle.date}`}>
                  <line x1={candle.x} x2={candle.x} y1={candle.highY} y2={candle.lowY} className="analysis-candle-wick" />
                  <rect
                    x={candle.x - 0.6}
                    y={Math.min(candle.openY, candle.closeY)}
                    width="1.2"
                    height={Math.max(Math.abs(candle.closeY - candle.openY), 0.9)}
                    className={candle.up ? "analysis-candle-up" : "analysis-candle-down"}
                  />
                </g>
              ))}
            </svg>
          </div>
          <div className="analysis-metrics">
            <span className="mbadge">Open <strong>{formatNumber(chart.latest.open, { maximumFractionDigits: 2 })}</strong></span>
            <span className="mbadge">Close <strong>{formatNumber(chart.latest.close, { maximumFractionDigits: 2 })}</strong></span>
            <span className={`mbadge ${chart.latest.up ? "positive" : "negative"}`}>Bias <strong>{chart.latest.up ? "Bullish" : "Bearish"}</strong></span>
          </div>
        </>
      ) : (
        <ChartEmpty />
      )}
    </ChartCard>
  );
}

function ComparisonChart({ rows }) {
  const chart = useMemo(() => {
    const series = [
      { key: "usd", label: "Silver USD", colorClass: "analysis-line-primary" },
      { key: "vnd", label: "Silver VND", colorClass: "analysis-line-vnd" },
      { key: "silver", label: "Silver USD", colorClass: "analysis-line-silver" },
    ];

    const normalized = series
      .map((seriesItem) => {
        const base = rows.find((row) => Number.isFinite(row[seriesItem.key]))?.[seriesItem.key];
        if (!Number.isFinite(base) || base === 0) {
          return null;
        }
        return {
          ...seriesItem,
          points: rows
            .map((row, index) => ({
              index,
              date: row.date,
              value: Number.isFinite(row[seriesItem.key]) ? (row[seriesItem.key] / base) * 100 : NaN,
            }))
            .filter((point) => Number.isFinite(point.value)),
        };
      })
      .filter(Boolean);

    if (!normalized.length) {
      return null;
    }

    const values = normalized.flatMap((item) => item.points.map((point) => point.value));
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = (max - min || 1) * 0.12;
    const domainMin = min - padding;
    const domainMax = max + padding;
    const domainRange = domainMax - domainMin || 1;
    const maxLength = Math.max(...normalized.map((item) => item.points.length));
    const xScale = (index, length = maxLength) => 6 + (index / Math.max(length - 1, 1)) * 88;
    const yScale = (value) => 10 + ((domainMax - value) / domainRange) * 68;

    return {
      lines: normalized.map((item) => ({
        ...item,
        path: buildPolyline(item.points, xScale, yScale),
        latest: item.points.at(-1)?.value,
      })),
    };
  }, [rows]);

  return (
    <ChartCard
      title="Multi-line comparison"
      note="So sánh cùng lúc `price_usd`, `price_vnd` và `price_silver_usd` sau khi chuẩn hóa về mốc 100 để đọc tương quan thay vì lệch scale."
      tags={["normalized 100", "silver core series"]}
    >
      {chart ? (
        <>
          <div className="analysis-chart-shell">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="comparison chart">
              {chart.lines.map((line) => (
                <polyline
                  key={line.key}
                  points={line.path}
                  fill="none"
                  className={line.colorClass}
                  vectorEffect="non-scaling-stroke"
                />
              ))}
            </svg>
          </div>
          <div className="analysis-legend">
            {chart.lines.map((line) => (
              <span key={line.key}>
                <i className={`legend-swatch ${line.colorClass.replace("analysis-line-", "analysis-legend-")}`} />
                {line.label} {formatNumber(line.latest, { maximumFractionDigits: 1 })}
              </span>
            ))}
          </div>
        </>
      ) : (
        <ChartEmpty />
      )}
    </ChartCard>
  );
}

function ScatterChart({ title, note, points, xLabel, yLabel }) {
  const chart = useMemo(() => {
    const clean = points.filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
    if (clean.length < 3) {
      return null;
    }
    const xMin = Math.min(...clean.map((point) => point.x));
    const xMax = Math.max(...clean.map((point) => point.x));
    const yMin = Math.min(...clean.map((point) => point.y));
    const yMax = Math.max(...clean.map((point) => point.y));
    const xRange = xMax - xMin || 1;
    const yRange = yMax - yMin || 1;
    const meanX = mean(clean.map((point) => point.x));
    const meanY = mean(clean.map((point) => point.y));
    const covariance = mean(clean.map((point) => (point.x - meanX) * (point.y - meanY)));
    const varianceX = mean(clean.map((point) => (point.x - meanX) ** 2));
    const varianceY = mean(clean.map((point) => (point.y - meanY) ** 2));
    const correlation = covariance / Math.sqrt(Math.max(varianceX * varianceY, 1e-9));
    return {
      clean: clean.map((point) => ({
        ...point,
        cx: 10 + ((point.x - xMin) / xRange) * 80,
        cy: 12 + ((yMax - point.y) / yRange) * 70,
      })),
      correlation,
    };
  }, [points]);

  return (
    <ChartCard title={title} note={note} tags={[xLabel, yLabel]}>
      {chart ? (
        <>
          <div className="analysis-chart-shell">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label={title}>
              {chart.clean.map((point) => (
                <circle key={`${point.date}-${point.x}-${point.y}`} cx={point.cx} cy={point.cy} r="0.95" className="analysis-scatter-dot" />
              ))}
            </svg>
          </div>
          <div className="analysis-metrics">
            <span className="mbadge">Corr <strong>{formatNumber(chart.correlation, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong></span>
            <span className="mbadge">Points <strong>{formatNumber(chart.clean.length)}</strong></span>
          </div>
        </>
      ) : (
        <ChartEmpty />
      )}
    </ChartCard>
  );
}

function BoxPlotChart({ rows }) {
  const chart = useMemo(() => {
    const values = rows.map((row) => row.usd).filter(Number.isFinite).sort((left, right) => left - right);
    if (values.length < 5) {
      return null;
    }
    const q1 = quantile(values, 0.25);
    const median = quantile(values, 0.5);
    const q3 = quantile(values, 0.75);
    const iqr = q3 - q1;
    const lowerFence = q1 - iqr * 1.5;
    const upperFence = q3 + iqr * 1.5;
    const lowerWhisker = values.find((value) => value >= lowerFence) ?? values[0];
    const upperWhisker = [...values].reverse().find((value) => value <= upperFence) ?? values.at(-1);
    const outliers = values.filter((value) => value < lowerFence || value > upperFence);
    const min = values[0];
    const max = values.at(-1);
    const scale = (value) => 10 + ((value - min) / Math.max(max - min, 1)) * 80;
    return {
      q1,
      median,
      q3,
      lowerWhisker,
      upperWhisker,
      outliers,
      scale,
    };
  }, [rows]);

  return (
    <ChartCard
      title="Boxplot"
      note="Tóm tắt phân phối `price_usd` qua median, IQR và outliers để đọc độ nhiễu của thị trường nhanh hơn."
      tags={["distribution", "outliers"]}
    >
      {chart ? (
        <>
          <div className="analysis-chart-shell analysis-chart-shell-sm">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="boxplot chart">
              <line x1={chart.scale(chart.lowerWhisker)} x2={chart.scale(chart.upperWhisker)} y1="50" y2="50" className="analysis-candle-wick" />
              <line x1={chart.scale(chart.lowerWhisker)} x2={chart.scale(chart.lowerWhisker)} y1="40" y2="60" className="analysis-candle-wick" />
              <line x1={chart.scale(chart.upperWhisker)} x2={chart.scale(chart.upperWhisker)} y1="40" y2="60" className="analysis-candle-wick" />
              <rect
                x={chart.scale(chart.q1)}
                y="34"
                width={Math.max(chart.scale(chart.q3) - chart.scale(chart.q1), 1.2)}
                height="32"
                className="analysis-boxplot-box"
              />
              <line x1={chart.scale(chart.median)} x2={chart.scale(chart.median)} y1="34" y2="66" className="analysis-boxplot-median" />
              {chart.outliers.map((value, index) => (
                <circle key={`outlier-${value}-${index}`} cx={chart.scale(value)} cy="50" r="1.1" className="analysis-scatter-dot" />
              ))}
            </svg>
          </div>
          <div className="analysis-metrics">
            <span className="mbadge">Median <strong>{formatNumber(chart.median, { maximumFractionDigits: 2 })}</strong></span>
            <span className="mbadge">Q1-Q3 <strong>{formatNumber(chart.q1, { maximumFractionDigits: 2 })} → {formatNumber(chart.q3, { maximumFractionDigits: 2 })}</strong></span>
            <span className="mbadge">Outliers <strong>{formatNumber(chart.outliers.length)}</strong></span>
          </div>
        </>
      ) : (
        <ChartEmpty />
      )}
    </ChartCard>
  );
}

function HistogramChart({ rows }) {
  const chart = useMemo(() => {
    const values = rows.map((row) => row.usd).filter(Number.isFinite);
    if (values.length < 5) {
      return null;
    }
    const min = Math.min(...values);
    const max = Math.max(...values);
    const binCount = Math.min(10, Math.max(5, Math.round(Math.sqrt(values.length))));
    const binSize = Math.max((max - min) / binCount, 1);
    const bins = Array.from({ length: binCount }, (_, index) => ({
      start: min + index * binSize,
      end: index === binCount - 1 ? max : min + (index + 1) * binSize,
      count: 0,
    }));
    values.forEach((value) => {
      const rawIndex = Math.floor((value - min) / binSize);
      const safeIndex = clamp(rawIndex, 0, bins.length - 1);
      bins[safeIndex].count += 1;
    });
    const maxCount = Math.max(...bins.map((bin) => bin.count), 1);
    return {
      bins,
      maxCount,
    };
  }, [rows]);

  return (
    <ChartCard
      title="Histogram"
      note="Phân phối tần suất của `price_usd` để xem vùng giá xuất hiện nhiều nhất và kiểm tra thị trường có lệch phân phối hay không."
      tags={["frequency", "price_usd"]}
    >
      {chart ? (
        <>
          <div className="analysis-chart-shell analysis-chart-shell-sm">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="histogram chart">
              {chart.bins.map((bin, index) => {
                const width = 80 / chart.bins.length;
                const x = 10 + index * width;
                const height = (bin.count / chart.maxCount) * 64;
                return (
                  <rect
                    key={`bin-${bin.start}-${bin.end}`}
                    x={x}
                    y={82 - height}
                    width={Math.max(width - 0.8, 1.2)}
                    height={height}
                    className="analysis-histogram-bar"
                  />
                );
              })}
            </svg>
          </div>
          <div className="analysis-metrics">
            <span className="mbadge">Bins <strong>{formatNumber(chart.bins.length)}</strong></span>
            <span className="mbadge">Peak freq <strong>{formatNumber(chart.maxCount)}</strong></span>
          </div>
        </>
      ) : (
        <ChartEmpty />
      )}
    </ChartCard>
  );
}

function SpreadChart({ rows }) {
  const chart = useMemo(() => {
    const points = rows
      .map((row, index) => ({
        index,
        date: row.date,
        value:
          Number.isFinite(row.vnd) && Number.isFinite(row.usd) && Number.isFinite(row.rate)
            ? row.vnd - row.usd * row.rate
            : NaN,
      }))
      .filter((point) => Number.isFinite(point.value));

    if (points.length < 2) {
      return null;
    }

    const min = Math.min(...points.map((point) => point.value));
    const max = Math.max(...points.map((point) => point.value));
    const padding = (max - min || 1) * 0.12;
    const domainMin = min - padding;
    const domainMax = max + padding;
    const domainRange = domainMax - domainMin || 1;
    const xScale = (index, length = points.length) => 6 + (index / Math.max(length - 1, 1)) * 88;
    const yScale = (value) => 10 + ((domainMax - value) / domainRange) * 68;
    return {
      path: buildPolyline(points, xScale, yScale),
      latest: points.at(-1)?.value,
      maxSpread: max,
      minSpread: min,
    };
  }, [rows]);

  return (
    <ChartCard
      title="Spread chart"
      note="Theo dõi chênh lệch `price_vnd - price_usd * usd_vnd_rate` để phát hiện giai đoạn giá trong nước đi lệch giá thế giới."
      tags={["spread", "VN vs world"]}
    >
      {chart ? (
        <>
          <div className="analysis-chart-shell">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="spread chart">
              <polyline points={chart.path} fill="none" className="analysis-line-spread" vectorEffect="non-scaling-stroke" />
            </svg>
          </div>
          <div className="analysis-metrics">
            <span className="mbadge">Latest <strong>{formatNumber(chart.latest, { maximumFractionDigits: 0 })}</strong></span>
            <span className="mbadge">Min <strong>{formatNumber(chart.minSpread, { maximumFractionDigits: 0 })}</strong></span>
            <span className="mbadge">Max <strong>{formatNumber(chart.maxSpread, { maximumFractionDigits: 0 })}</strong></span>
          </div>
        </>
      ) : (
        <ChartEmpty />
      )}
    </ChartCard>
  );
}

export function TechnicalAnalysisSuite({ data }) {
  const rows = useMemo(
    () =>
      data
        .map((item) => ({
          date: new Date(item.price_timestamp).toLocaleDateString("en-CA"),
          usd: Number(item.price_usd),
          vnd: Number(item.price_vnd),
          silver: Number(item.price_silver_usd),
          rate: Number(item.usd_vnd_rate),
        }))
        .filter((item) => Number.isFinite(item.usd))
        .sort((left, right) => new Date(left.date).getTime() - new Date(right.date).getTime()),
    [data],
  );

  const stats = useMemo(() => {
    if (!rows.length) {
      return null;
    }
    const usableSilver = rows.filter((row) => Number.isFinite(row.silver)).length;
    const usableRate = rows.filter((row) => Number.isFinite(row.rate)).length;
    return {
      rows: rows.length,
      usableSilver,
      usableRate,
    };
  }, [rows]);

  if (!stats) {
    return <ChartEmpty text="Hãy sync thêm dữ liệu để mở cụm biểu đồ phân tích kỹ thuật." />;
  }

  return (
    <div className="analysis-suite">
      <div className="analysis-suite-head">
        <div className="section-label">01 — Technical Analytics</div>
        <p className="chart-note">
          Bộ chart này ưu tiên đúng combo phân tích: xu hướng chính, MA, tương quan, phân phối và spread.
          Các biểu đồ scatter sẽ chỉ đầy đủ khi dataset có `usd_vnd_rate` hoặc `price_silver_usd`.
        </p>
        <div className="analysis-tags">
          <span className="tag tag-teal">{formatNumber(stats.rows)} rows</span>
          <span className="tag tag-blue">{formatNumber(stats.usableRate)} FX points</span>
          <span className="tag tag-purple">{formatNumber(stats.usableSilver)} silver points</span>
        </div>
      </div>

      <div className="analysis-grid analysis-grid-featured">
        <TrendWithMAChart rows={rows} />
        <ReturnChart rows={rows} />
      </div>

      <div className="analysis-grid">
        <CandlestickChart rows={rows} />
        <ComparisonChart rows={rows} />
      </div>

      <div className="analysis-grid">
        <ScatterChart
          title="Scatter: Silver vs USD/VND"
          note="Kiểm tra nhanh việc tỷ giá tăng có đi cùng biến động bạc hay không."
          xLabel="usd_vnd_rate"
          yLabel="price_usd"
          points={rows.map((row) => ({ date: row.date, x: row.rate, y: row.usd }))}
        />
        <ScatterChart
          title="Scatter: Silver vs Silver Mirror"
          note="So chéo chuỗi bạc chính với cột bạc mirror để phát hiện sai lệch dữ liệu nếu có."
          xLabel="price_silver_usd"
          yLabel="price_usd"
          points={rows.map((row) => ({ date: row.date, x: row.silver, y: row.usd }))}
        />
      </div>

      <div className="analysis-grid">
        <BoxPlotChart rows={rows} />
        <HistogramChart rows={rows} />
      </div>

      <div className="analysis-grid analysis-grid-single">
        <SpreadChart rows={rows} />
      </div>
    </div>
  );
}
