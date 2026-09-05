import { useState } from "react";

function Row({ row }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="sc-row">
      <button className="sc-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className={`dot ${row.tone}`} />
        <span className="sc-label">{row.label}</span>
        <span className={`badge ${row.tone}`}>{row.badge}</span>
        <svg
          className={`chev ${open ? "open" : ""}`}
          viewBox="0 0 24 24"
          aria-hidden="true"
          focusable="false"
        >
          <path
            d="M9 5l7 7-7 7"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      <p className="sc-sentence">{row.sentence}</p>
      {open && row.detail && <p className="sc-detail">{row.detail}</p>}
    </div>
  );
}

export default function Scorecard({ rows }) {
  return (
    <section className="card scorecard">
      <h3 className="sc-title">Scorecard</h3>
      {rows.map((row) => (
        <Row key={row.key} row={row} />
      ))}
      <p className="sc-foot muted small">
        Every grade is measured against this stock's own history, not a fixed
        threshold.
      </p>
    </section>
  );
}
