export default function Sparkline({ points, width = 96, height = 30 }) {
  if (!points || points.length < 2) return null;

  const low = Math.min(...points);
  const high = Math.max(...points);
  const span = high - low || 1;
  const step = width / (points.length - 1);
  const y = (p) => height - 3 - ((p - low) / span) * (height - 6);

  const path = points.map((p, i) => `${i ? "L" : "M"}${i * step},${y(p)}`).join(" ");
  const rising = points[points.length - 1] >= points[0];

  return (
    <svg
      className={`spark ${rising ? "up" : "down"}`}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden="true"
    >
      <path d={path} fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={width} cy={y(points[points.length - 1])} r="2.5" />
    </svg>
  );
}
