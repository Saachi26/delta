"""Delta API."""
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

import bands
import corporate
import db
import market
import quotes
import scorecard
import signals
import stocks
from schemas import AddSymbolIn, LoginIn, SensitivityIn

app = FastAPI(
    title="Delta",
    description="Smart market watchlist, Groww Code hackathon",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Username"],
)
db.init_db()
SNAPSHOT_ROWS = quotes.load_snapshot()

SPARK_DAYS = 30
DIGEST_LIMIT = 5
PAGE_LIMIT = 24
SCORED_POOL = 48
PEER_LIMIT = 8

# Source: https://www.nseindia.com/resources/exchange-communication-holidays
NSE_HOLIDAYS_2026 = {
    "2026-01-15", "2026-01-26", "2026-02-19", "2026-03-03",
    "2026-03-19", "2026-03-26", "2026-03-31", "2026-04-01",
    "2026-04-03", "2026-04-14", "2026-05-01", "2026-05-28",
    "2026-06-26", "2026-08-26", "2026-09-14", "2026-10-02",
    "2026-10-20", "2026-11-10", "2026-11-24", "2026-12-25",
}

DISCOVER_TABS = [
    {"id": "trending", "label": "Trending",
     "hint": "Most saved across watchlists in this prototype"},
    {"id": "movers", "label": "Biggest movers",
     "hint": "Furthest from their own normal day, not just the largest percent"},
    {"id": "active", "label": "Unusual volume",
     "hint": "Trading far above their usual volume, whatever the price did"},
    {"id": "all", "label": "All stocks",
     "hint": "Everything Delta tracks, most familiar first"},
]


def get_session():
    session = db.SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_user(x_username: str | None = Header(default=None), session=Depends(get_session)):
    """Resolve the request user from the username header."""
    if not x_username:
        raise HTTPException(401, "missing X-Username header")
    user = session.query(db.User).filter_by(username=x_username.lower()).first()
    if not user:
        raise HTTPException(401, "unknown user, log in first")
    return user


def market_state(now=None):
    """Return the NSE regular-session state and elapsed session fraction."""
    zone = ZoneInfo("Asia/Kolkata")
    now = now or datetime.now(zone)
    now = now.replace(tzinfo=zone) if now.tzinfo is None else now.astimezone(zone)
    configured = {
        value.strip()
        for value in os.environ.get("NSE_HOLIDAYS", "").split(",")
        if value.strip()
    }
    holidays = NSE_HOLIDAYS_2026 | configured
    today = now.date().isoformat()
    trading_day = now.weekday() < 5 and today not in holidays
    minute = now.hour * 60 + now.minute
    session_start = 9 * 60 + 15
    session_end = 15 * 60 + 30
    if trading_day and session_start <= minute < session_end:
        progress = (minute - session_start) / (session_end - session_start)
        return {
            "open": True,
            "label": "Market open",
            "date": today,
            "session_fraction": max(0.05, min(progress, 1.0)),
        }
    if trading_day and (now.hour, now.minute) < (9, 15):
        label = "Market opens at 9:15 · showing last close"
    else:
        label = "Market closed · showing last close"
    return {"open": False, "label": label, "date": today, "session_fraction": 1.0}


def market_context(history, move_today):
    """Calculate beta and residual movement against the market index."""
    blank = {"beta": None, "residual": move_today, "explained": False,
             "index_move": None}
    if symbol_is_index(history):
        return blank
    try:
        index = quotes.index_history()
    except quotes.MarketDataUnavailable:
        return blank
    dates, closes = history.get("dates"), history["closes"]
    idx_dates, idx_closes = index.get("dates"), index["closes"]
    if not dates or not idx_dates:
        return blank

    by_date = dict(zip(idx_dates, idx_closes))
    shared = [(d, c, by_date[d]) for d, c in zip(dates, closes) if d in by_date]
    if len(shared) < 40:
        return blank

    stock_moves = signals.daily_moves([c for _, c, _ in shared])
    index_moves = signals.daily_moves([i for _, _, i in shared])
    beta = market.beta(stock_moves[-250:], index_moves[-250:])
    if beta is None:
        return blank

    # Measure the residual against its own recent spread.
    residuals = [market.residual_move(s, i, beta)
                 for s, i in zip(stock_moves[-60:], index_moves[-60:])]
    residual_spread = signals.typical_spread(residuals)
    index_move = index_moves[-1] if index_moves else 0.0
    return {
        "beta": round(beta, 2),
        "residual": round(market.residual_move(move_today, index_move, beta), 2),
        "explained": market.explains_the_move(move_today, index_move, beta, residual_spread),
        "index_move": round(index_move, 2),
    }


def symbol_is_index(history):
    """The index itself has no market to be compared against."""
    return history.get("symbol") == quotes.INDEX


def build_row(symbol):
    """Build the stock summary returned to the UI."""
    state = market_state()
    try:
        history, quote = quotes.get_quote(symbol, state["open"])
    except quotes.MarketDataUnavailable as exc:
        raise HTTPException(502, str(exc)) from exc
    closes, volumes = history["closes"], history["volumes"]
    if not closes:
        raise HTTPException(502, f"no market data for {symbol}")
    price = quote["price"]
    volume = quote.get("volume")
    if volume is None:
        volume = volumes[-1] if volumes else 0

    current_bar = bool(history.get("dates")) and history["dates"][-1] == state["date"]
    target_in_history = quote["basis"] == "close" or current_bar
    baseline_closes = closes[:-1] if target_in_history else closes
    baseline_volumes = volumes[-31:-1] if target_in_history else volumes[-30:]
    baseline_moves = signals.daily_moves(baseline_closes)[-30:]
    move_today = 0.0
    if quote["compare_to"]:
        move_today = (price - quote["compare_to"]) / quote["compare_to"] * 100

    z = signals.zscore(move_today, baseline_moves)
    price_z = z
    spread = signals.typical_spread(baseline_moves)
    elapsed = state["session_fraction"] if state["open"] and current_bar else 1.0
    can_score_volume = quote["basis"] != "live" or quote.get("volume") is not None or current_bar
    vol_ratio = (
        signals.volume_ratio(volume, baseline_volumes, elapsed)
        if can_score_volume else None
    )
    landmark = signals.crossed_52w(price, baseline_closes)

    highs, lows = history.get("highs") or [], history.get("lows") or []
    band = bands.hit_price_band(
        move_today, price,
        highs[-1] if highs else None,
        lows[-1] if lows else None,
    )
    turnover = signals.typical_turnover(closes, volumes)

    context = market_context(history, move_today)
    if context["explained"]:
        z = None  # the market moved it, so it is not this company's news

    score = signals.attention_score(z, vol_ratio, landmark)
    return {
        "symbol": symbol,
        "name": stocks.name_of(symbol),
        "sector": stocks.sector_of(symbol),
        "price": price,
        "volume": volume,
        "move_pct": round(move_today, 2),
        "price_z": round(price_z, 2) if price_z is not None else None,
        "spread": round(spread, 2) if spread else None,
        "volume_ratio": round(vol_ratio, 2) if vol_ratio else None,
        "week52_high": max(baseline_closes) if baseline_closes else None,
        "week52_low": min(baseline_closes) if baseline_closes else None,
        "spark": closes[-SPARK_DAYS:],
        "basis": quote["basis"],
        "conflict": quote["conflict"],
        "band": band,
        "band_note": bands.describe(band),
        "turnover": round(turnover) if turnover else None,
        "thin": signals.too_thin_to_trust(turnover),
        "beta": context["beta"],
        "residual_move": context["residual"],
        "index_move": context["index_move"],
        "market_explained": context["explained"],
        "score": score,
        "score_label": signals.attention_label(score),
        "reasons": signals.explain(move_today, z, vol_ratio, landmark, spread),
        "as_of": datetime.fromtimestamp(quote["as_of"], timezone.utc).isoformat(),
        "source": history["source"],
        "stale": quote["stale"],
    }


@app.post("/api/login")
def login(body: LoginIn, session=Depends(get_session)):
    username = body.username.lower()
    user = session.query(db.User).filter_by(username=username).first()
    if not user:
        user = db.User(username=username)
        session.add(user)
        session.commit()
    return {"id": user.id, "username": user.username}


@app.get("/api/stocks/search")
def search_stocks(q: str = ""):
    return stocks.search(q)


def watcher_counts(session):
    """Return watch counts grouped by symbol."""
    rows = (session.query(db.WatchItem.symbol, func.count(db.WatchItem.id))
            .group_by(db.WatchItem.symbol).all())
    return {symbol: count for symbol, count in rows}


def ranked_symbols(tab, session):
    """Return the symbol order for a discovery tab."""
    if tab == "trending":
        counts = watcher_counts(session)
        return sorted(stocks.POPULARITY,
                      key=lambda s: (-counts.get(s, 0), stocks.POPULARITY.index(s)))
    if tab in ("movers", "active"):
        # Limit live-data ranking to the configured candidate pool.
        pool = stocks.POPULARITY[:SCORED_POOL]
        quotes.warm_cache(pool)
        scored = []
        for symbol in pool:
            try:
                row = build_row(symbol)
            except Exception:
                continue
            key = abs(row["price_z"] or 0) if tab == "movers" else (row["volume_ratio"] or 0)
            scored.append((key, symbol))
        return [symbol for _, symbol in sorted(scored, reverse=True)]
    return stocks.POPULARITY


@app.get("/api/discover")
def discover(tab: str = "trending", offset: int = 0, limit: int = PAGE_LIMIT,
             user=Depends(get_user), session=Depends(get_session)):
    """Return one page of discovery results."""
    if tab not in {t["id"] for t in DISCOVER_TABS}:
        tab = "trending"
    limit = max(1, min(limit, 48))
    offset = max(0, offset)

    ordered = ranked_symbols(tab, session)
    page = ordered[offset:offset + limit]
    quotes.warm_cache(page)  # one upstream request per page, not one per stock

    owned = {item.symbol for item in
             session.query(db.WatchItem).filter_by(user_id=user.id).all()}
    counts = watcher_counts(session)
    rows = []
    for symbol in page:
        try:
            row = build_row(symbol)
        except Exception:
            continue  # a stock we cannot price is skipped, never fatal
        rows.append({**row, "in_watchlist": symbol in owned,
                     "watchers": counts.get(symbol, 0)})

    next_offset = offset + limit
    return {
        "tabs": DISCOVER_TABS,
        "tab": tab,
        "rows": rows,
        "next_offset": next_offset if next_offset < len(ordered) else None,
        "total": len(ordered),
    }


@app.get("/api/watchlist")
def get_watchlist(user=Depends(get_user), session=Depends(get_session)):
    items = session.query(db.WatchItem).filter_by(user_id=user.id).all()
    quotes.warm_cache([item.symbol for item in items])
    rows = [{**build_row(item.symbol), "sensitivity": item.sensitivity}
            for item in items]
    rows.sort(key=lambda r: r["score"], reverse=True)
    return {"market": market_state(), "rows": rows, "mix": sector_mix(rows)}


@app.post("/api/watchlist")
def add_symbol(body: AddSymbolIn, user=Depends(get_user), session=Depends(get_session)):
    symbol = body.symbol.upper()
    if not stocks.exists(symbol):
        raise HTTPException(404, f"unknown symbol {symbol}")
    already = session.query(db.WatchItem).filter_by(user_id=user.id, symbol=symbol).first()
    if already:
        raise HTTPException(409, f"{stocks.name_of(symbol)} is already on your watchlist")
    session.add(db.WatchItem(user_id=user.id, symbol=symbol))
    try:
        session.commit()
    except IntegrityError:  # two simultaneous adds raced past the check above
        session.rollback()
        raise HTTPException(409, f"{stocks.name_of(symbol)} is already on your watchlist")
    return build_row(symbol)


@app.delete("/api/watchlist/{symbol}")
def remove_symbol(symbol: str, user=Depends(get_user), session=Depends(get_session)):
    symbol = symbol.upper()
    session.query(db.WatchItem).filter_by(user_id=user.id, symbol=symbol).delete()
    session.query(db.Snapshot).filter_by(user_id=user.id, symbol=symbol).delete()
    session.commit()
    return {"removed": symbol}


@app.post("/api/seen")
def mark_seen(user=Depends(get_user), session=Depends(get_session)):
    """Store the user's current watchlist state."""
    items = session.query(db.WatchItem).filter_by(user_id=user.id).all()
    session.query(db.Snapshot).filter_by(user_id=user.id).delete()
    for item in items:
        row = build_row(item.symbol)
        session.add(
            db.Snapshot(
                user_id=user.id,
                symbol=item.symbol,
                price=row["price"],
                volume=row["volume"],
            )
        )
    user.last_seen_at = db.utcnow()  # even with an empty watchlist, "seen" counts
    session.commit()
    return {"snapshotted": len(items)}


@app.get("/api/digest")
def digest(user=Depends(get_user), session=Depends(get_session)):
    """Return notable changes since the user's latest snapshot."""
    if user.last_seen_at is None:
        return {"first_visit": True, "notable": [], "quiet_count": 0,
                "muted_count": 0, "last_seen_at": None}
    snaps = {
        s.symbol: s
        for s in session.query(db.Snapshot).filter_by(user_id=user.id).all()
    }

    notable, quiet_count, muted_count = [], 0, 0
    too_new, thin_count, unexplained = 0, 0, 0
    scored, adjustments = [], []
    for item in session.query(db.WatchItem).filter_by(user_id=user.id).all():
        if item.sensitivity == "muted":
            muted_count += 1
            continue
        snap = snaps.get(item.symbol)
        if snap is None or not snap.price:
            too_new += 1
            continue
        row = build_row(item.symbol)
        move_bar, volume_bar = (4, 6) if item.sensitivity == "low" else (2, 3)

        # Prefer reported split data, then use ratio-based detection.
        history = quotes.get_history(item.symbol)
        seen_on = str(snap.taken_at)[:10]
        baseline = signals.daily_moves(history["closes"][:-1])[-30:]
        was = snap.price
        factor = corporate.recorded_split_since(history.get("splits"), seen_on)
        label = f"{factor:g}-for-1 split" if factor else None
        if not factor:
            guess = corporate.detect_split(snap.price, row["price"], baseline)
            if guess:
                factor, label = guess["ratio"], "looks like a " + guess["label"]
        if factor:
            snap.price = snap.price / factor
            adjustments.append({
                "symbol": item.symbol, "name": row["name"], "label": label,
                "old_price": was, "adjusted_price": round(snap.price, 2),
            })

        change = (row["price"] - snap.price) / snap.price * 100
        spread = row["spread"] or 1.0
        change_z = change / spread
        scored.append((item.symbol, change_z))
        vol_since = row["volume"] / snap.volume if snap.volume else None
        crossed = None
        if row["week52_high"] and snap.price < row["week52_high"] <= row["price"]:
            crossed = "high"
        elif row["week52_low"] and snap.price > row["week52_low"] >= row["price"]:
            crossed = "low"

        # Suppress extreme gaps that cannot be validated as corporate actions.
        if abs(change) > 30 and not factor:
            unexplained += 1
            continue

        if row["thin"]:
            thin_count += 1
            continue

        reasons = []
        if row["band"]:
            reasons.append(row["band_note"])
        if abs(change_z) >= move_bar:
            verb = "down" if change < 0 else "up"
            reasons.append(
                f"{verb} {abs(change):.1f}% since you last checked "
                f"(typical day: ±{spread:.1f}%)"
            )
        if vol_since is not None and vol_since >= volume_bar:
            reasons.append(f"volume is {vol_since:.0f}× what it was when you last checked")
        if crossed == "high":
            reasons.append("crossed its 52-week high since you last checked")
        elif crossed == "low":
            reasons.append("fell below its 52-week low since you last checked")

        if reasons:
            score = signals.attention_score(change_z, vol_since, crossed)
            notable.append({
                **row,
                "change_since_seen": round(change, 2),
                "reasons": reasons,
                "score": score,
                "score_label": signals.attention_label(score),
                # Breadth filtering applies only to price-only alerts.
                "price_only": all(r.startswith(("up ", "down ")) for r in reasons),
            })
        else:
            quiet_count += 1

    broad = market.breadth([z for _, z in scored])
    followed = 0
    if broad:
        standouts = set(market.outliers(scored, broad["mean_z"]))
        kept = [n for n in notable
                if n["symbol"] in standouts or not n["price_only"]]
        followed = len(notable) - len(kept)
        notable = kept
        quiet_count += followed

    notable.sort(key=lambda r: r["score"], reverse=True)
    also_moved = max(0, len(notable) - DIGEST_LIMIT)
    notable = notable[:DIGEST_LIMIT]
    last_seen = user.last_seen_at
    if last_seen.tzinfo is None:  # SQLite drops the timezone; it was stored as UTC
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    session.commit()
    return {
        "first_visit": False,
        "notable": notable,
        "quiet_count": quiet_count,
        "muted_count": muted_count,
        "market": broad,
        "followed_market": followed,
        "also_moved": also_moved,
        "too_new": too_new,
        "thin_count": thin_count,
        "unexplained": unexplained,
        "adjustments": adjustments,
        "last_seen_at": last_seen.isoformat(),
    }


def sector_mix(rows):
    """Summarize the watchlist by sector."""
    counts = {}
    for row in rows:
        counts[row["sector"]] = counts.get(row["sector"], 0) + 1
    total = len(rows) or 1
    return sorted(
        ({"sector": s, "count": c, "percent": round(c / total * 100)}
         for s, c in counts.items()),
        key=lambda m: m["count"], reverse=True,
    )


def sector_peers(symbol):
    """Return a capped set of stocks from the same sector."""
    group = stocks.by_sector().get(stocks.sector_of(symbol), [])
    group = sorted(group, key=lambda s: stocks.POPULARITY.index(s))[:PEER_LIMIT]
    if symbol not in group:
        group = [symbol] + group[:PEER_LIMIT - 1]
    quotes.warm_cache(group)  # one batched request for the whole sector
    peers = []
    for peer in group:
        try:
            row = build_row(peer)
        except Exception:
            continue  # a peer we cannot price should never break the page
        peers.append({
            "symbol": peer,
            "name": row["name"],
            "price": row["price"],
            "move_pct": row["move_pct"],
            "ret_1m": scorecard.pct_change(quotes.get_history(peer)["closes"], 21),
            "score": row["score"],
            "score_label": row["score_label"],
            "is_current": peer == symbol,
        })
    return peers


@app.get("/api/stock/{symbol}")
def stock_detail(symbol: str, user=Depends(get_user), session=Depends(get_session)):
    """Return stock detail, scorecard, peers, and chart series."""
    symbol = symbol.upper()
    if not stocks.exists(symbol):
        raise HTTPException(404, f"unknown symbol {symbol}")
    row = build_row(symbol)
    history = quotes.get_history(symbol)
    closes = history["closes"]
    dates = history.get("dates") or [""] * len(closes)
    item = session.query(db.WatchItem).filter_by(user_id=user.id, symbol=symbol).first()
    peers = sector_peers(symbol)

    return {
        **row,
        "in_watchlist": item is not None,
        "sensitivity": item.sensitivity if item else None,
        "returns": scorecard.returns(closes),
        "scorecard": scorecard.build(
            row, closes,
            [p["move_pct"] for p in peers if not p["is_current"]],
            market_state()["open"],
        ),
        "peers": peers,
        "series": [{"date": d, "close": c} for d, c in zip(dates, closes)],
    }


@app.patch("/api/watchlist/{symbol}")
def set_sensitivity(symbol: str, body: SensitivityIn,
                    user=Depends(get_user), session=Depends(get_session)):
    """Update a watch item's sensitivity."""
    item = session.query(db.WatchItem).filter_by(
        user_id=user.id, symbol=symbol.upper()).first()
    if not item:
        raise HTTPException(404, f"{symbol.upper()} is not on your watchlist")
    item.sensitivity = body.level
    session.commit()
    return {"symbol": item.symbol, "sensitivity": item.sensitivity}


@app.get("/api/health")
def health(session=Depends(get_session)):
    """Return database and quote-cache metrics."""
    users = session.query(db.User).count()
    rows = session.query(db.WatchItem).count()
    unique = session.query(db.WatchItem.symbol).distinct().count()
    served = quotes.stats["history_hit"] + quotes.stats["history_fetch"]
    return {
        "users": users,
        "watchlist_rows": rows,
        "unique_symbols": unique,
        "upstream_fetches": quotes.stats["history_fetch"],
        "cache_hits": quotes.stats["history_hit"],
        "cache_hit_rate": round(quotes.stats["history_hit"] / served, 3) if served else 0,
        "upstream_failures": quotes.stats["failure"],
    }


# A single-container deployment ships the built frontend beside the API. Mounted
# last so every /api route still wins, and skipped entirely in local development
# where Vite serves the frontend itself.
STATIC_DIR = os.environ.get("STATIC_DIR", "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
