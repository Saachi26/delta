import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import StockCard from "./StockCard.jsx";
import "./Discover.css";

const PAGE_SIZE = 24;

function forCard(row) {
  return row.reasons ? row : { ...row, reasons: [] };
}

function discoverPath(tab, offset) {
  const tabPart = tab ? `tab=${encodeURIComponent(tab)}&` : "";
  return `/discover?${tabPart}offset=${offset}&limit=${PAGE_SIZE}`;
}

export default function Discover({ onAdd, onOpen }) {
  const [tabs, setTabs] = useState([]);
  const [tab, setTab] = useState(null);
  const [rows, setRows] = useState([]);
  const [nextOffset, setNextOffset] = useState(0); // 0 = nothing fetched yet, null = no more pages
  const [total, setTotal] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  // Prevent duplicate observer requests before state updates.
  const inFlight = useRef(false);
  // Ignore responses superseded by a newer request.
  const requestId = useRef(0);
  const lastAsk = useRef({ tab: null, offset: 0 });
  const sentinel = useRef(null);

  const load = useCallback(async (tabId, offset, force = false) => {
    if (inFlight.current && !force) return; // one page at a time
    inFlight.current = true;
    const id = ++requestId.current;
    lastAsk.current = { tab: tabId, offset };
    setBusy(true);
    setError(null);
    try {
      const data = await api(discoverPath(tabId, offset));
      if (id !== requestId.current) return; // a newer request already took over
      setTabs(data.tabs || []);
      setTab(data.tab);
      setTotal(data.total ?? null);
      setNextOffset(data.next_offset ?? null);
      const page = data.rows || [];
      setRows((prev) => (offset === 0 ? page : prev.concat(page)));
    } catch (err) {
      if (id !== requestId.current) return;
      setError(err.message || "Could not load stocks.");
    } finally {
      if (id === requestId.current) {
        inFlight.current = false;
        setBusy(false);
      }
    }
  }, []);

  useEffect(() => {
    load(null, 0);
  }, [load]);

  const loadMore = useCallback(() => {
    if (nextOffset === null || error || inFlight.current) return;
    load(tab, nextOffset);
  }, [load, tab, nextOffset, error]);

  useEffect(() => {
    const node = sentinel.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) loadMore();
      },
      { rootMargin: "300px" } // start fetching just before the user reaches the end
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [loadMore]);

  function selectTab(id) {
    if (id === tab) return;
    setTab(id);
    setRows([]);
    setNextOffset(0);
    load(id, 0, true);
  }

  function retry() {
    load(lastAsk.current.tab, lastAsk.current.offset, true);
  }

  async function addOne(symbol) {
    try {
      await onAdd(symbol);
      setRows((prev) =>
        prev.map((row) => (row.symbol === symbol ? { ...row, in_watchlist: true } : row))
      );
    } catch {
      // The parent owns mutation errors.
    }
  }

  const selected = tabs.find((t) => t.id === tab);
  const firstLoad = rows.length === 0 && busy;
  const done = nextOffset === null && rows.length > 0;

  return (
    <>
      {tabs.length > 0 && (
        <div className="dsc-bar">
          <div className="dsc-tabs">
            {tabs.map((t) => (
              <button
                key={t.id}
                className={`dsc-tab ${t.id === tab ? "on" : ""}`}
                aria-pressed={t.id === tab}
                onClick={() => selectTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
          {total !== null && <span className="dsc-total">{total} stocks</span>}
        </div>
      )}

      {selected && selected.hint && <p className="dsc-hint">{selected.hint}</p>}

      <div className="grid">
        {rows.map((row) => (
          <StockCard key={row.symbol} row={forCard(row)} onAdd={addOne} onOpen={onOpen} />
        ))}
        {firstLoad &&
          Array.from({ length: 6 }, (_, i) => <div className="dsc-skeleton" key={`skeleton-${i}`} />)}
      </div>

      {rows.length === 0 && !busy && !error && <p className="dsc-note">No stocks to show here yet.</p>}

      <div className="dsc-foot" ref={sentinel} aria-live="polite">
        {error && (
          <span className="dsc-note">
            {rows.length > 0 ? "Could not load more stocks." : "Could not load stocks."}{" "}
            <button className="dsc-retry" onClick={retry}>
              Try again
            </button>
          </span>
        )}
        {!error && busy && rows.length > 0 && <span className="dsc-note">Loading more…</span>}
        {!error && !busy && done && <span className="dsc-note">That's all {total} stocks.</span>}
      </div>
    </>
  );
}
