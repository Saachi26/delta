import { rupees, scoreTone } from "../api.js";
import "./Peers.css";

const MINUS = "−";
const NO_DATA = "—";

function missing(value) {
  return value === null || value === undefined || Number.isNaN(value);
}

function attentionText(peer) {
  const number = Math.round(peer.score);
  return peer.score_label ? `${peer.score_label} · ${number}` : String(number);
}

function Pct({ value }) {
  if (missing(value)) return <span className="peers-null">{NO_DATA}</span>;
  return (
    <span className={value < 0 ? "peers-down" : "peers-up"}>
      {value < 0 ? MINUS : "+"}
      {Math.abs(value).toFixed(2)}%
    </span>
  );
}

export default function Peers({ peers = [], onOpen }) {
  const others = peers.filter((peer) => !peer.is_current);
  if (others.length === 0) {
    return (
      <section className="card peers">
        <h3>Peers</h3>
        <p className="peers-empty">No other stocks from this sector to compare against yet.</p>
      </section>
    );
  }

  const rows = peers.slice().sort((a, b) => (b.score ?? 0) - (a.score ?? 0));

  const open = (symbol) => {
    if (onOpen) onOpen(symbol);
  };

  const onRowKeyDown = (event, symbol) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault(); // Space would otherwise scroll the page
      open(symbol);
    }
  };

  return (
    <section className="card peers">
      <h3>Peers</h3>

      <div className="peers-scroll">
        <table className="peers-table">
          <thead>
            <tr>
              <th className="peers-left">Stock</th>
              <th>Price</th>
              <th>Today %</th>
              <th className="peers-1m">1M %</th>
              <th>Attention</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((peer) => (
              <tr
                key={peer.symbol}
                className={peer.is_current ? "peers-row is-current" : "peers-row clickable"}
                tabIndex={peer.is_current ? undefined : 0}
                aria-label={peer.is_current ? undefined : `Open ${peer.name}`}
                onClick={peer.is_current ? undefined : () => open(peer.symbol)}
                onKeyDown={peer.is_current ? undefined : (e) => onRowKeyDown(e, peer.symbol)}
              >
                <td className="peers-left">
                  <span className="peers-name">
                    {peer.name}
                    {peer.is_current && <span className="peers-tag">this stock</span>}
                  </span>
                  <span className="peers-symbol">{peer.symbol}</span>
                </td>
                <td className="peers-num">
                  {missing(peer.price) ? (
                    <span className="peers-null">{NO_DATA}</span>
                  ) : (
                    rupees(peer.price)
                  )}
                </td>
                <td className="peers-num"><Pct value={peer.move_pct} /></td>
                <td className="peers-num peers-1m"><Pct value={peer.ret_1m} /></td>
                <td className="peers-num">
                  <span className={`peers-pill ${scoreTone(peer.score)}`}>{attentionText(peer)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="peers-caption">
        If the sector moved as one today, this is sector news; if this stock moved alone, it is about the company.
      </p>
    </section>
  );
}
