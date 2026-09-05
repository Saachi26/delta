import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import "./SearchBox.css";

const DEBOUNCE_MS = 180;
const ADDED_MS = 1200;
const LIST_ID = "sb-listbox";

const IS_MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || "");

function splitOnMatch(name, query) {
  const at = name.toLowerCase().indexOf(query.toLowerCase());
  if (!query || at < 0) return [name, "", ""];
  return [name.slice(0, at), name.slice(at, at + query.length), name.slice(at + query.length)];
}

function Magnifier() {
  return (
    <svg className="sb-icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <circle cx="9" cy="9" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <line x1="13" y1="13" x2="17" y2="17" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export default function SearchBox({ onPick, onOpen }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [status, setStatus] = useState("idle");
  const [open, setOpen] = useState(false);
  const [focused, setFocused] = useState(false);
  const [active, setActive] = useState(0);
  const [note, setNote] = useState(null);
  const [pending, setPending] = useState("");

  const wrapRef = useRef(null);
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const requestId = useRef(0);
  const noteTimer = useRef(0);

  const typed = query.trim();
  const panelOpen = open && status !== "idle";

  // Sequence requests so stale responses cannot replace newer results.
  useEffect(() => {
    setNote(null);
    if (!typed && !open) {
      requestId.current += 1;
      setResults([]);
      setStatus("idle");
      return;
    }
    const timer = setTimeout(async () => {
      const id = ++requestId.current;
      setStatus("loading");
      try {
        const rows = await api(`/stocks/search?q=${encodeURIComponent(typed)}`);
        if (id !== requestId.current) return;
        setResults(rows);
        setActive(0);
        setStatus("ready");
      } catch {
        if (id !== requestId.current) return;
        setResults([]);
        setStatus("error");
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [typed, open]);

  useEffect(() => {
    function onHotkey(e) {
      if (!(e.metaKey || e.ctrlKey) || !e.key || e.key.toLowerCase() !== "k") return;
      e.preventDefault();
      setOpen(true);
      inputRef.current?.focus();
      inputRef.current?.select();
    }
    document.addEventListener("keydown", onHotkey);
    return () => document.removeEventListener("keydown", onHotkey);
  }, []);

  useEffect(() => {
    function onDown(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  useEffect(() => () => clearTimeout(noteTimer.current), []);

  useEffect(() => {
    if (!panelOpen) return;
    listRef.current?.children[active]?.scrollIntoView({ block: "nearest" });
  }, [active, panelOpen]);

  function flash(symbol, text, kind) {
    clearTimeout(noteTimer.current);
    setNote({ symbol, text, kind });
    if (kind === "ok") noteTimer.current = setTimeout(() => setNote(null), ADDED_MS);
  }

  function openStock(symbol) {
    setOpen(false);
    onOpen(symbol);
  }

  async function addStock(symbol) {
    setPending(symbol);
    try {
      await onPick(symbol);
      flash(symbol, "added ✓", "ok");
    } catch (err) {
      flash(symbol, err.message || "could not add", "err");
    } finally {
      setPending("");
    }
  }

  function reset() {
    setQuery("");
    setResults([]);
    setStatus("idle");
    setOpen(false);
    setNote(null);
    inputRef.current?.blur();
  }

  function onKeyDown(e) {
    if (e.key === "Escape") {
      reset();
      return;
    }
    if (!panelOpen) return;
    const count = results.length;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (count === 0) return;
      const step = e.key === "ArrowDown" ? 1 : -1;
      setActive((i) => (i + step + count) % count);
      return;
    }
    if (e.key === "Enter" && count > 0) {
      e.preventDefault();
      openStock(results[active].symbol);
    }
  }

  function onBlur(e) {
    setFocused(false);
    if (!wrapRef.current || !wrapRef.current.contains(e.relatedTarget)) setOpen(false);
  }

  const showHint = !focused && query === "";

  return (
    <div className="sb-wrap" ref={wrapRef}>
      <div className="sb-field">
        <Magnifier />
        <input
          ref={inputRef}
          className="sb-input"
          type="text"
          value={query}
          placeholder="Search a company or symbol"
          autoComplete="off"
          spellCheck="false"
          role="combobox"
          aria-expanded={panelOpen}
          aria-controls={LIST_ID}
          aria-autocomplete="list"
          aria-activedescendant={panelOpen && results.length > 0 ? `sb-opt-${active}` : undefined}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => {
            setFocused(true);
            setOpen(true);
          }}
          onBlur={onBlur}
          onKeyDown={onKeyDown}
        />
        {showHint && (
          <span className="sb-kbd" aria-hidden="true">
            {IS_MAC ? "⌘K" : "Ctrl K"}
          </span>
        )}
      </div>

      {panelOpen && (
        <div className="sb-panel" onMouseDown={(e) => e.preventDefault()}>
          {status === "loading" && <div className="sb-msg">Searching…</div>}
          {status === "error" && <div className="sb-msg">Search is unavailable right now.</div>}
          {status === "ready" && typed === "" && results.length > 0 && (
            <div className="sb-head">Popular on Delta</div>
          )}
          {status === "ready" && results.length === 0 && (
            <div className="sb-msg">
              <div className="sb-msg-main">No stock matches "{typed}"</div>
              <div className="sb-msg-sub">Delta covers stocks listed on the NSE.</div>
            </div>
          )}

          <div className="sb-list" id={LIST_ID} role="listbox" ref={listRef}>
            {status === "ready" &&
              results.map((r, i) => {
                const [before, hit, after] = splitOnMatch(r.name, typed);
                const rowNote = note && note.symbol === r.symbol ? note : null;
                return (
                  <div
                    key={r.symbol}
                    id={`sb-opt-${i}`}
                    role="option"
                    aria-selected={i === active}
                    className={`sb-row ${i === active ? "on" : ""}`}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => openStock(r.symbol)}
                  >
                    <span className="sb-text">
                      <span className="sb-name">
                        {before}
                        {hit && <span className="sb-hit">{hit}</span>}
                        {after}
                      </span>
                      <span className="sb-meta">
                        {r.symbol} · {r.sector}
                      </span>
                    </span>
                    {rowNote ? (
                      <span className={`sb-note ${rowNote.kind}`}>{rowNote.text}</span>
                    ) : (
                      <button
                        type="button"
                        className="sb-add"
                        disabled={pending === r.symbol}
                        onClick={(e) => {
                          e.stopPropagation();
                          addStock(r.symbol);
                        }}
                      >
                        {pending === r.symbol ? "adding…" : "+ watch"}
                      </button>
                    )}
                  </div>
                );
              })}
          </div>
        </div>
      )}
    </div>
  );
}
