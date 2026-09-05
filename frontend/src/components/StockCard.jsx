import Sparkline from "./Sparkline.jsx";
import { rupees, scoreTone, timeAgo } from "../api.js";

function Bin() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"
      fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="4" y1="6" x2="16" y2="6" />
      <path d="M8 6V4.6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1V6" />
      <path d="M6.2 6l.7 9.1a1.3 1.3 0 0 0 1.3 1.2h3.6a1.3 1.3 0 0 0 1.3-1.2L13.8 6" />
      <line x1="9" y1="9" x2="9" y2="13.6" />
      <line x1="11" y1="9" x2="11" y2="13.6" />
    </svg>
  );
}

export default function StockCard({ row, onRemove, onAdd, onOpen }) {
  const down = row.move_pct < 0;
  const open = onOpen ? () => onOpen(row.symbol) : undefined;
  const stop = (fn) => (e) => {
    e.stopPropagation();
    fn();
  };
  return (
    <article
      className={`card stock ${row.stale ? "stale" : ""} ${row.sensitivity === "muted" ? "muted-stock" : ""} ${onOpen ? "clickable" : ""}`}
      onClick={open}
      onKeyDown={(e) => open && (e.key === "Enter" || e.key === " ") && (e.preventDefault(), open())}
      tabIndex={onOpen ? 0 : undefined}
      role={onOpen ? "button" : undefined}
      aria-label={onOpen ? `Open ${row.name}` : undefined}
    >
      <div className="stock-head">
        <div>
          <strong>{row.name}</strong>
          <div className="muted small">{row.symbol} · {row.sector}</div>
        </div>
        <span className={`score ${scoreTone(row.score)}`} title="how much attention this deserves today">
          {row.sensitivity === "muted" ? "Muted" : row.score_label}
        </span>
      </div>

      <div className="stock-body">
        <div>
          <div className="price">{rupees(row.price)}</div>
          <div className={down ? "down" : "up"}>
            {down ? "▼" : "▲"} {Math.abs(row.move_pct)}%
            {row.spread && <span className="muted"> · usual ±{row.spread}%</span>}
          </div>
        </div>
        <Sparkline points={row.spark} />
      </div>

      {(row.reasons || []).length > 0 && (
        <ul className="reasons">
          {row.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}

      {row.conflict && <div className="conflict">⚠ {row.conflict}</div>}

      <div className="stock-foot">
        <span className="muted small">
          {row.source === "simulation" ? (
            "simulated scenario · not live"
          ) : (
            <>
              {row.basis === "live" ? "live · " : "last close · "}
              {timeAgo(row.as_of)}
              {row.stale && " · delayed"}
            </>
          )}
          {row.watchers !== undefined && ` · ${row.watchers} watchlists`}
        </span>
        {onRemove && (
          <button
            className="icon-btn"
            title={`Stop watching ${row.name}`}
            aria-label={`Stop watching ${row.name}`}
            onClick={stop(() => onRemove(row.symbol))}
          >
            <Bin />
          </button>
        )}
        {onAdd && (
          <button className="pill" disabled={row.in_watchlist} onClick={stop(() => onAdd(row.symbol))}>
            {row.in_watchlist ? "on your list" : "+ watch"}
          </button>
        )}
      </div>
    </article>
  );
}
