import { useCallback, useEffect, useState } from "react";
import { api, currentUser } from "./api.js";
import Sidebar from "./components/Sidebar.jsx";
import Digest from "./components/Digest.jsx";
import Discover from "./components/Discover.jsx";
import HowItWorks from "./components/HowItWorks.jsx";
import Login from "./components/Login.jsx";
import SearchBox from "./components/SearchBox.jsx";
import StockCard from "./components/StockCard.jsx";
import StockDetail from "./components/StockDetail.jsx";

const POLL_MS = 30_000;
const SAVED_MS = 4000;
const TITLES = {
  watchlist: "Your watchlist",
  discover: "Discover",
  how: "How Delta decides what matters",
  stock: "Stock detail",
};

export default function App() {
  const [user, setUser] = useState(currentUser());
  const [view, setView] = useState("watchlist");
  const [openSymbol, setOpenSymbol] = useState(null);
  const [watchlist, setWatchlist] = useState(null);
  const [digest, setDigest] = useState(null);
  const [justSaved, setJustSaved] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [wl, dg] = await Promise.all([api("/watchlist"), api("/digest")]);
      if (!currentUser()) return; // logged out while this request was in flight
      setWatchlist(wl);
      setDigest(dg);
      setError("");
    } catch (e) {
      if (e.status === 401) {
        localStorage.removeItem("delta_user");
        setUser("");
        return;
      }
      setError(e.message); // keep showing the last good data underneath
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    refresh();
    const timer = setInterval(refresh, POLL_MS);
    return () => clearInterval(timer);
  }, [user, refresh]);

  if (!user) return <Login onLogin={setUser} />;

  const run = async (fn) => {
    try {
      await fn();
      setError("");
    } catch (e) {
      setError(e.message);
    }
  };

  const addStock = async (symbol) => {
    await api("/watchlist", "POST", { symbol });
    refresh();
  };

  const removeStock = (symbol) =>
    run(async () => {
      await api(`/watchlist/${symbol}`, "DELETE");
      refresh();
    });

  const openStock = (symbol) => {
    setOpenSymbol(symbol);
    setView("stock");
  };

  const goTo = (next) => {
    setOpenSymbol(null);
    setView(next);
  };

  const setSensitivity = (symbol, level) =>
    run(async () => {
      await api(`/watchlist/${symbol}`, "PATCH", { level });
      refresh();
    });

  const markSeen = () =>
    run(async () => {
      await api("/seen", "POST");
      setJustSaved(true);
      setTimeout(() => setJustSaved(false), SAVED_MS);
      refresh();
    });

  const logout = () => {
    localStorage.removeItem("delta_user");
    setUser("");
    setWatchlist(null);
    setDigest(null);
  };

  return (
    <div className="app">
      <Sidebar
        view={view}
        setView={goTo}
        counts={{
          watching: watchlist?.rows.length || 0,
          notable: digest?.notable.length || 0,
        }}
        user={user}
        onLogout={logout}
      />

      <main>
        <header className="topbar">
          <div>
            <h1>{TITLES[view]}</h1>
            {watchlist && view !== "how" ? (
              <span className={`chip ${watchlist.market.open ? "open" : ""}`}>
                {watchlist.market.label}
              </span>
            ) : null}
          </div>
          {view !== "how" && <SearchBox onPick={addStock} onOpen={openStock} />}
        </header>

        {error && (
          <div className="banner error" role="alert">
            Something went wrong: {error}
          </div>
        )}

        {view === "watchlist" && (
          <>
            <Digest digest={digest} onSeen={markSeen} justSaved={justSaved} />
            {watchlist?.rows.length === 0 && (
              <div className="card empty">
                <strong>Your watchlist is empty.</strong>
                <p className="muted">
                  Search above, or open Discover to browse popular stocks.
                </p>
                <button onClick={() => setView("discover")}>Browse stocks</button>
              </div>
            )}
            {watchlist?.mix?.length > 1 && (
              <p className="mix muted small">
                Your list leans {watchlist.mix[0].sector.toLowerCase()}:{" "}
                {watchlist.mix[0].percent}% of it. Concentrated lists move together.
              </p>
            )}
            <div className="grid">
              {watchlist?.rows.map((row) => (
                <StockCard
                  key={row.symbol}
                  row={row}
                  onRemove={removeStock}
                  onOpen={openStock}
                />
              ))}
            </div>
          </>
        )}

        {view === "discover" && <Discover onAdd={addStock} onOpen={openStock} />}
        {view === "how" && <HowItWorks />}
        {view === "stock" && (
          <StockDetail
            symbol={openSymbol}
            onOpen={openStock}
            onAdd={addStock}
            onSensitivity={setSensitivity}
          />
        )}
      </main>
    </div>
  );
}
