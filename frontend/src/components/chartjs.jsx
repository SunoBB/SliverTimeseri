import { useMemo } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
} from "chart.js";
import { Line } from "react-chartjs-2";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip);

/* ─── Category metadata (matches DB event category values) ────────── */
const CAT_META = {
  all:         { label: "Tất cả",        hex: "#6b7280", bg: "#f3f4f6", txt: "#374151" },
  crisis:      { label: "Khủng hoảng",   hex: "#E24B4A", bg: "#FCEBEB", txt: "#A32D2D" },
  monetary:    { label: "Tiền tệ",       hex: "#378ADD", bg: "#E6F1FB", txt: "#185FA5" },
  fed:         { label: "Fed / NHTW",    hex: "#378ADD", bg: "#E6F1FB", txt: "#185FA5" },
  fx:          { label: "Ngoại hối",     hex: "#8B5CF6", bg: "#EDE9FE", txt: "#5B21B6" },
  geopolitics: { label: "Địa chính trị", hex: "#BA7517", bg: "#FAEEDA", txt: "#633806" },
  commodity:   { label: "Hàng hóa",      hex: "#1D9E75", bg: "#E1F5EE", txt: "#085041" },
  speculation: { label: "Đầu cơ",        hex: "#EC4899", bg: "#FCE7F3", txt: "#831843" },
  policy:      { label: "Chính sách",    hex: "#14B8A6", bg: "#CCFBF1", txt: "#134E4A" },
};

const LINE_HEX  = "#378ADD";
const GRID_CLR  = "rgba(0,0,0,0.055)";
const TICK_CLR  = "#888780";
const TIP_BG    = "#ffffff";
const TIP_BORD  = "rgba(0,0,0,0.1)";

export function getCatMeta(cat) {
  return CAT_META[cat] ?? { label: cat, hex: "#6b7280", bg: "#f3f4f6", txt: "#374151" };
}

export function AnnotatedLineChart({
  rows,
  events = [],
  activeFilter = "all",
  formatter,
  height = 320,
  yAxisLabel = "USD / oz",
}) {
  const filteredEvents = useMemo(
    () => (activeFilter === "all" ? events : events.filter((e) => e.category === activeFilter)),
    [events, activeFilter],
  );

  const eventByDate = useMemo(() => {
    const map = new Map();
    filteredEvents.forEach((ev) => {
      if (ev.event_date) {
        const d = new Date(ev.event_date).toLocaleDateString("en-CA");
        if (!map.has(d)) map.set(d, ev);
      }
    });
    return map;
  }, [filteredEvents]);

  const labels = rows.map((r) => r.date);
  const prices = rows.map((r) => r.value);

  const pointColors      = labels.map((d) => eventByDate.has(d) ? getCatMeta(eventByDate.get(d).category).hex : LINE_HEX);
  const pointRadii       = labels.map((d) => eventByDate.has(d) ? 7 : 2);
  const pointBorderWidths = labels.map((d) => eventByDate.has(d) ? 2 : 0);

  const chartData = {
    labels,
    datasets: [
      {
        data: prices,
        borderColor: LINE_HEX,
        borderWidth: 1.5,
        fill: false,
        tension: 0.3,
        pointBackgroundColor: pointColors,
        pointBorderColor: "#fff",
        pointBorderWidth: pointBorderWidths,
        pointRadius: pointRadii,
        pointHoverRadius: 9,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title: (items) => items[0].label,
          label: (items) =>
            formatter
              ? formatter(items.parsed.y)
              : `$${items.parsed.y.toFixed(2)}/oz`,
          afterLabel: (items) => {
            const ev = eventByDate.get(labels[items.dataIndex]);
            return ev ? `  ↑ ${ev.title}` : "";
          },
        },
        backgroundColor: TIP_BG,
        titleColor: TICK_CLR,
        bodyColor: "#2C2C2A",
        borderColor: TIP_BORD,
        borderWidth: 0.5,
        padding: 10,
        cornerRadius: 8,
      },
    },
    scales: {
      x: {
        ticks: {
          color: TICK_CLR,
          font: { size: 10, family: "'IBM Plex Mono', monospace" },
          maxTicksLimit: 10,
          maxRotation: 0,
        },
        grid: { color: GRID_CLR },
      },
      y: {
        ticks: {
          color: TICK_CLR,
          font: { size: 10, family: "'IBM Plex Mono', monospace" },
          callback: (v) => (formatter ? formatter(v) : `$${v}`),
        },
        grid: { color: GRID_CLR },
        title: {
          display: true,
          text: yAxisLabel,
          color: TICK_CLR,
          font: { size: 11, family: "'IBM Plex Mono', monospace" },
        },
      },
    },
  };

  return (
    <div style={{ position: "relative", width: "100%", height }}>
      <Line data={chartData} options={options} />
    </div>
  );
}
