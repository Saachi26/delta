import { useEffect, useState } from "react";
import { api, rupees, scoreTone, timeAgo } from "../api.js";
import Chart from "./Chart.jsx";
import Peers from "./Peers.jsx";
import Scorecard from "./Scorecard.jsx";

const LEVELS = [
  { id: "normal", label: "Normal", hint: "tell me when this is unusual" },
  { id: "low", label: "Only big", hint: "only for something major" },
  { id: "muted", label: "Muted", hint: "never in my digest" },
];

export default function StockDetail({ symbol, onOpen, onAdd, onSensitivity }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setData(null);
    api(`/stock/${symbol}`)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  const add = async () => {
    try {
      await onAdd(symbol);
      setData({ ...data, in_watchlist: true, sensitivity: "normal" });
    } catch (e) {
      setError(e.message);
    }
  };

  if (error) return <div className="banner error" role="alert">{error}</div>;
  if (!data) return <p className="muted">Loading {symbol}…</p>;

  const down = data.move_pct < 0;
  const tone = scoreTone(data.score);

  return (
    <div className="detail">
      <div className="detail-grid">
        <div className="rail">
          <Scorecard rows={data.scorecard} />
        </div>

        <div className="main-col">
          <section className="card">
            <div className="row-between head">
              <div>
                <h2>{data.name}</h2>
                <div className="muted small">{data.symbol} · {data.sector}</div>
              </div>
              <div className={`attention ${tone}`}>
                <strong>{data.score_label}</strong>
                <span>attention {data.score}/100</span>
              </div>
            </div>

            <div className="detail-price">
              <span className="price">{rupees(data.price)}</span>
              <span className={down ? "down" : "up"}>
                {down ? "▼" : "▲"} {Math.abs(data.move_pct)}% today
              </span>
              <span className="muted small">
                {data.source === "simulation"
                  ? "simulated scenario · not live"
                  : `${data.basis === "live" ? "live" : "last close"} · ${timeAgo(data.as_of)}`}
              </span>
            </div>

            <div className="alerts-row">
              {data.in_watchlist ? (
                <>
                  <span className="muted small">Alert me</span>
                  {LEVELS.map((level) => (
                    <button
                      key={level.id}
                      className={`level ${data.sensitivity === level.id ? "on" : ""}`}
                      title={level.hint}
                      onClick={() =>
                        onSensitivity(symbol, level.id).then(() =>
                          setData({ ...data, sensitivity: level.id }))
                      }
                    >
                      {level.label}
                    </button>
                  ))}
                  <span className="muted small">
                    · {LEVELS.find((l) => l.id === data.sensitivity)?.hint}
                  </span>
                </>
              ) : (
                <button className="pill" onClick={add}>+ Add to watchlist</button>
              )}
            </div>

            <Chart series={data.series} />
          </section>

          <div className="detail-row">
            <section className="card">
              <h3>Returns</h3>
              <div className="returns">
                {Object.entries(data.returns).map(([label, value]) => (
                  <div key={label}>
                    <div className="muted small">{label}</div>
                    <div className={value === null ? "muted" : value < 0 ? "down" : "up"}>
                      {value === null ? "—" : `${value > 0 ? "+" : ""}${value}%`}
                    </div>
                  </div>
                ))}
              </div>
              <p className="muted small">
                Context for today's move: a 2% drop reads differently on a stock up
                40% this year.
              </p>
            </section>

            <section className="card">
              <h3>{data.reasons.length > 0 ? "Why it's on your digest" : "Nothing unusual today"}</h3>
              {data.reasons.length > 0 ? (
                <ul className="reasons">
                  {data.reasons.map((r) => <li key={r}>{r}</li>)}
                </ul>
              ) : (
                <p className="muted">
                  Current price and volume signals are within their configured
                  ranges, so this stock is not included in the digest.
                </p>
              )}
            </section>
          </div>

          <Peers peers={data.peers} onOpen={onOpen} />
        </div>
      </div>
    </div>
  );
}
