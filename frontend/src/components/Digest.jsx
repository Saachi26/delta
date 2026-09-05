import { rupees, timeAgo } from "../api.js";

export default function Digest({ digest, onSeen }) {
  if (!digest) return null;

  if (digest.first_visit) {
    return (
      <section className="card digest">
        <h2>While you were away</h2>
        <p className="muted">
          Nothing to compare yet. Add some stocks, then mark this visit as seen.
          Next time you open Delta, anything unusual appears here first.
        </p>
        <div className="row-between digest-foot">
          <span className="muted small">Save today as your comparison point</span>
          <button onClick={onSeen}>Mark all as seen</button>
        </div>
      </section>
    );
  }

  const nothing = digest.notable.length === 0;
  const market = digest.market;
  const adjustments = digest.adjustments || [];

  return (
    <section className="card digest">
      <div className="row-between">
        <h2>While you were away</h2>
        <span className="muted small">last checked {timeAgo(digest.last_seen_at)}</span>
      </div>

      {market && (
        <div className={`market-note ${market.direction}`}>
          <strong>
            Broad {market.direction} day: {market.count} of {market.total} of your
            stocks moved together, {Math.abs(market.mean_z).toFixed(1)} times their
            normal day on average.
          </strong>
          <span className="muted small">
            {digest.followed_market > 0
              ? `${digest.followed_market} of them simply followed the market, so they are not listed separately.`
              : "Anything below moved on its own, not with the market."}
          </span>
        </div>
      )}

      {adjustments.map((a) => (
        <div className="market-note info" key={a.symbol}>
          <strong>{a.name} looks like a {a.label}.</strong>
          <span className="muted small">
            Your baseline moved from {rupees(a.old_price)} to{" "}
            {rupees(a.adjusted_price)}. The share count changed, the value did
            not, so this is not counted as a price move.
          </span>
        </div>
      ))}

      {nothing && (
        <p className="all-quiet">
          All quiet. Nothing unusual has happened since you last checked.
        </p>
      )}

      {digest.notable.map((item) => (
        <div className="digest-item" key={item.symbol}>
          <div className="row-between">
            <div>
              <strong>{item.name}</strong>
              <span className="muted small"> {item.symbol}</span>
            </div>
            <span className={item.change_since_seen < 0 ? "down" : "up"}>
              {item.change_since_seen > 0 ? "+" : ""}
              {item.change_since_seen}%
            </span>
          </div>
          <ul className="reasons">
            {item.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      ))}

      <div className="row-between digest-foot">
        <span className="muted small">
          {digest.quiet_count > 0 &&
            `${digest.quiet_count} other ${digest.quiet_count === 1 ? "stock" : "stocks"}: nothing unusual`}
          {digest.muted_count > 0 &&
            `${digest.quiet_count > 0 ? " · " : ""}${digest.muted_count} muted`}
        </span>
        <button onClick={onSeen}>Mark all as seen</button>
      </div>
    </section>
  );
}
