import Logo from "./Logo.jsx";

function Exit() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <path d="M8.5 4H5.5a1.5 1.5 0 0 0-1.5 1.5v9A1.5 1.5 0 0 0 5.5 16h3"
        fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M12.5 7l3 3-3 3" fill="none" stroke="currentColor"
        strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <line x1="15" y1="10" x2="8.5" y2="10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

const NAV = [
  { id: "watchlist", label: "Watchlist" },
  { id: "discover", label: "Discover" },
  { id: "how", label: "How it works" },
];

export default function Sidebar({ view, setView, counts, user, onLogout }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <Logo />
        Delta
      </div>

      <nav>
        {NAV.map((item) => (
          <button
            key={item.id}
            className={`nav ${view === item.id ? "active" : ""}`}
            onClick={() => setView(item.id)}
          >
            {item.label}
            {item.id === "watchlist" && counts.watching > 0 && (
              <span className="count">{counts.watching}</span>
            )}
            {item.id === "watchlist" && counts.notable > 0 && (
              <span className="count alert">{counts.notable} new</span>
            )}
          </button>
        ))}
      </nav>

      <div className="sidebar-foot">
        <div className="muted small">watching as</div>
        <div className="row-between">
          <strong>{user}</strong>
          <button className="icon-btn" title="Switch user" aria-label="Switch user" onClick={onLogout}>
            <Exit />
          </button>
        </div>
      </div>
    </aside>
  );
}
