import { useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import "./Chart.css";

const RANGES = [
  { id: "1M", days: 21, speech: "last 1 month" },
  { id: "3M", days: 63, speech: "last 3 months" },
  { id: "6M", days: 126, speech: "last 6 months" },
  { id: "1Y", days: 250, speech: "last 1 year" },
];

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const GREEN = "#00b386";
const RED = "#e2543a";
const PAD = { top: 12, right: 66, bottom: 26, left: 8 };

// Parse date-only values in local time to avoid UTC date shifts.
function parseDate(text) {
  const bits = String(text || "").split("-");
  if (bits.length !== 3) return null;
  const d = new Date(Number(bits[0]), Number(bits[1]) - 1, Number(bits[2]));
  return Number.isNaN(d.getTime()) ? null : d;
}

function dayMonth(d) {
  return d ? `${d.getDate()} ${MONTHS[d.getMonth()]}` : "";
}

function monthYear(d) {
  return d ? `${MONTHS[d.getMonth()]} '${String(d.getFullYear()).slice(-2)}` : "";
}

function fullDate(d) {
  return d ? `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}` : "";
}

function money(n) {
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function niceStep(raw) {
  const pow = Math.pow(10, Math.floor(Math.log10(raw)));
  const n = raw / pow;
  const mult = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10;
  return mult * pow;
}

function niceBounds(min, max, count) {
  let lowest = min;
  let highest = max;
  if (highest - lowest <= 0) {
    const pad = Math.abs(highest) * 0.01 || 1;
    lowest = highest - pad;
    highest = highest + pad;
  }
  const step = niceStep((highest - lowest) / (count - 1));
  const lo = Math.floor(lowest / step) * step;
  const hi = Math.ceil(highest / step) * step;
  const ticks = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Number(v.toFixed(6))); // toFixed clears float drift
  return { lo, hi, ticks };
}

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n));
}

export default function Chart({ series, height = 260 }) {
  const plotRef = useRef(null);
  const [width, setWidth] = useState(720);
  const [rangeId, setRangeId] = useState("3M");
  const [hover, setHover] = useState(null);
  const gradientId = `chart-fill-${useId().replace(/:/g, "")}`;

  useLayoutEffect(() => {
    const node = plotRef.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const next = Math.round(entry.contentRect.width);
      if (next > 0) setWidth(next);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const points = useMemo(
    () => (series || []).filter((p) => p && Number.isFinite(p.close)),
    [series]
  );

  const options = RANGES.map((r, i) => ({
    ...r,
    enabled: i === 0 ? points.length >= 2 : points.length > RANGES[i - 1].days,
  }));
  const usable = options.filter((o) => o.enabled);
  const active = usable.find((o) => o.id === rangeId) || usable[usable.length - 1] || options[0];

  const view = useMemo(() => {
    if (points.length < 2) return null;
    const slice = points.slice(Math.max(0, points.length - active.days));
    if (slice.length < 2) return null;

    const closes = slice.map((p) => p.close);
    const min = Math.min(...closes);
    const max = Math.max(...closes);
    const { lo, hi, ticks } = niceBounds(min, max, 4);

    const plotW = Math.max(1, width - PAD.left - PAD.right);
    const plotH = Math.max(1, height - PAD.top - PAD.bottom);
    const base = PAD.top + plotH;
    const x = (i) => PAD.left + (i / (slice.length - 1)) * plotW;
    const y = (v) => PAD.top + (1 - (v - lo) / (hi - lo)) * plotH;

    const line = slice
      .map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(2)},${y(p.close).toFixed(2)}`)
      .join(" ");
    const area = `${line} L${x(slice.length - 1).toFixed(2)},${base} L${x(0).toFixed(2)},${base} Z`;

    const xTicks = [];
    const seen = new Set();
    for (let k = 0; k < 4; k++) {
      const i = Math.round((k / 3) * (slice.length - 1));
      if (seen.has(i)) continue;
      seen.add(i);
      xTicks.push({ i, anchor: k === 0 ? "start" : k === 3 ? "end" : "middle" });
    }

    const first = closes[0];
    const last = closes[closes.length - 1];
    const rising = last >= first;
    const pct = first ? ((last - first) / first) * 100 : 0;
    const longSpan = active.days > 63;

    return {
      slice, x, y, line, area, base, plotW, ticks, xTicks,
      min, max, first, last, rising, pct, longSpan,
      color: rising ? GREEN : RED,
      firstDate: parseDate(slice[0].date),
      lastDate: parseDate(slice[slice.length - 1].date),
    };
  }, [points, active.days, width, height]);

  function handleMove(e) {
    if (!view) return;
    const box = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - box.left) / box.width) * width;
    const t = (px - PAD.left) / view.plotW;
    const i = clamp(Math.round(t * (view.slice.length - 1)), 0, view.slice.length - 1);
    setHover((prev) => (prev === i ? prev : i));
  }

  if (!view) {
    return (
      <div className="chart">
        <p className="chart-empty">Not enough price history yet</p>
      </div>
    );
  }

  const point = hover === null ? null : view.slice[hover];
  const pointDate = point ? parseDate(point.date) : null;
  const arrow = view.rising ? "▲" : "▼";
  const sign = view.pct >= 0 ? "up" : "down";
  const label =
    `Price chart, ${active.speech}, from ${money(view.first)} on ${dayMonth(view.firstDate)} ` +
    `to ${money(view.last)} on ${dayMonth(view.lastDate)}, ${sign} ${Math.abs(view.pct).toFixed(1)}%`;

  return (
    <div className="chart">
      <div className="chart-head">
        <div className="chart-ranges" role="group" aria-label="Chart range">
          {options.map((o) => (
            <button
              key={o.id}
              type="button"
              className={`chart-range ${o.id === active.id ? "on" : ""}`}
              disabled={!o.enabled}
              aria-pressed={o.id === active.id}
              onClick={() => setRangeId(o.id)}
            >
              {o.id}
            </button>
          ))}
        </div>
      </div>

      <div className="chart-plot" ref={plotRef}>
        <svg
          className="chart-svg"
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label={label}
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={view.color} stopOpacity="0.18" />
              <stop offset="100%" stopColor={view.color} stopOpacity="0" />
            </linearGradient>
          </defs>

          {view.ticks.map((t) => (
            <g key={t}>
              <line
                className="chart-grid"
                x1={PAD.left}
                x2={width - PAD.right}
                y1={view.y(t)}
                y2={view.y(t)}
              />
              <text
                className="chart-axis"
                x={width - PAD.right + 10}
                y={view.y(t)}
                dominantBaseline="middle"
              >
                {money(t)}
              </text>
            </g>
          ))}

          {view.xTicks.map((t) => (
            <text
              key={t.i}
              className="chart-axis"
              x={view.x(t.i)}
              y={height - 8}
              textAnchor={t.anchor}
            >
              {view.longSpan
                ? monthYear(parseDate(view.slice[t.i].date))
                : dayMonth(parseDate(view.slice[t.i].date))}
            </text>
          ))}

          <path d={view.area} fill={`url(#${gradientId})`} />
          <path
            d={view.line}
            fill="none"
            stroke={view.color}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          <circle
            cx={view.x(view.slice.length - 1)}
            cy={view.y(view.last)}
            r="3.5"
            fill={view.color}
            stroke="#ffffff"
            strokeWidth="2"
          />

          {point && (
            <g>
              <line
                className="chart-cross"
                x1={view.x(hover)}
                x2={view.x(hover)}
                y1={PAD.top}
                y2={view.base}
              />
              <circle
                cx={view.x(hover)}
                cy={view.y(point.close)}
                r="4"
                fill={view.color}
                stroke="#ffffff"
                strokeWidth="2"
              />
            </g>
          )}

          <rect
            x="0"
            y="0"
            width={width}
            height={height}
            fill="transparent"
            onPointerMove={handleMove}
            onPointerLeave={() => setHover(null)}
          />
        </svg>

        {point && (
          <div
            className="chart-tip"
            style={{
              left: clamp(view.x(hover), 70, width - 70),
              top: view.y(point.close) < height / 2 ? view.base - 54 : PAD.top + 4,
            }}
          >
            <strong>{money(point.close)}</strong>
            <span>{fullDate(pointDate)}</span>
          </div>
        )}
      </div>

      <div className="chart-foot">
        <span>High {money(view.max)}</span>
        <span className="chart-sep">·</span>
        <span>Low {money(view.min)}</span>
        <span className={`chart-move ${view.rising ? "up" : "down"}`}>
          {arrow} {Math.abs(view.pct).toFixed(1)}% over {active.id}
        </span>
      </div>
    </div>
  );
}
