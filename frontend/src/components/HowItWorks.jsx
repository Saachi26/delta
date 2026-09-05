const SIGNALS = [
  {
    n: "01",
    title: "Unusual price move",
    body: "Today's move measured against that stock's own last 30 days, never a fixed threshold.",
    note: "A z-score: how many ordinary days of movement today was worth.",
  },
  {
    n: "02",
    title: "Volume spike",
    body: "Volume at three times its recent average, including periods when the price is stable.",
    note: "This signal is independent of price movement.",
  },
  {
    n: "03",
    title: "52-week landmark",
    body: "The stock moved above its 52-week high or below its 52-week low.",
    note: "The comparison includes the current price.",
  },
  {
    n: "04",
    title: "Its sector, for context",
    body: "The stock's movement is compared with the median movement in its sector.",
    note: "Compared against the other stocks Delta tracks in that sector.",
  },
];

const LEVELS = [
  { tone: "calm", word: "Quiet", range: "0-29", meaning: "Within the normal range." },
  { tone: "warn", word: "Notable", range: "30-59", meaning: "Moderately unusual." },
  { tone: "alert", word: "Alert", range: "60-100", meaning: "Highly unusual." },
];

const NOPE = [
  ["No predictions", "Nothing here forecasts a price."],
  ["No buy or sell calls", "The score ranks attention, not quality."],
  ["No news sentiment", "News and social-media data are not analyzed."],
  ["No fixed price thresholds", "Price movement is normalized by recent volatility."],
];

export default function HowItWorks() {
  return (
    <div className="explain">
      <header className="hero">
        <div>
          <p className="hero-lede">
            Most watchlists tell you what moved.<br />
            Delta tells you what moved <strong>unusually</strong>.
          </p>
          <p className="muted">
            Because the same 5% means two completely different things depending
            on the stock it happened to.
          </p>
        </div>

        <div className="hero-demo">
          <div className="demo-row">
            <div>
              <strong>HDFC Bank</strong>
              <div className="muted small">usually moves ±0.9% a day</div>
            </div>
            <div className="demo-move">−4%</div>
            <span className="badge alert">Alert</span>
          </div>
          <div className="demo-row">
            <div>
              <strong>Adani Power</strong>
              <div className="muted small">usually moves ±4.1% a day</div>
            </div>
            <div className="demo-move">−4%</div>
            <span className="badge calm">Quiet</span>
          </div>
          <p className="muted small demo-foot">
            The same percentage move receives a different score because the
            stocks have different volatility.
          </p>
        </div>
      </header>

      <h3 className="explain-h">What counts as meaningful</h3>
      <div className="signal-grid">
        {SIGNALS.map((s) => (
          <article className="card signal" key={s.n}>
            <div className="signal-top">
              <span className="signal-n">{s.n}</span>
              <h4>{s.title}</h4>
            </div>
            <p>{s.body}</p>
            <p className="muted small signal-note">{s.note}</p>
          </article>
        ))}
      </div>

      <h3 className="explain-h">The attention score</h3>
      <section className="card score-band">
        <p className="band-lead">
          The four signals combine into a 0-100 attention score.
        </p>
        <p className="muted band-sub">
          The score measures unusual activity. It is not a company rating or a
          buy or sell signal.
        </p>
        <div className="band-levels">
          {LEVELS.map((l) => (
            <div className="band-level" key={l.word}>
              <span className={`badge ${l.tone}`}>{l.word}</span>
              <div className="band-range">{l.range}</div>
              <div className="muted small">{l.meaning}</div>
            </div>
          ))}
        </div>
      </section>

      <div className="explain-two">
        <section className="card">
          <h4>What "since you last checked" means</h4>
          <p>
            Marking things as seen stores a snapshot of every price and volume at
            that moment, on the server. Coming back compares against that
            snapshot, so the digest shows what <em>you</em> have not seen, not
            simply what happened today.
          </p>
          <p className="muted small">
            The snapshot belongs to your account, not your browser, so a phone
            and a laptop agree on what you have already seen.
          </p>
        </section>

        <section className="card">
          <h4>Data quality</h4>
          <ul className="tight">
            <li>Every price includes its age and live or stale status.</li>
            <li>Outside market hours, the last close is shown.</li>
            <li>A live price more than 25% from the last close is rejected as bad data, and the conflict is shown.</li>
            <li>If the source fails, the last cached value is marked as stale.</li>
          </ul>
        </section>
      </div>

      <h3 className="explain-h">What Delta deliberately does not do</h3>
      <div className="nope-grid">
        {NOPE.map(([title, why]) => (
          <div className="card nope-card" key={title}>
            <strong>{title}</strong>
            <p className="muted small">{why}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
