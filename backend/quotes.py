"""Market-data retrieval, caching, and quote reconciliation."""
import os
import time
import warnings
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf

from mock_data import mock_history

warnings.filterwarnings("ignore", module="yfinance")

INDEX = "^NSEI"

HISTORY_TTL = 300
LIVE_TTL = 30
DELAYED_AFTER = 900
IMPLAUSIBLE = 0.25

_history_cache = {}
_live_cache = {}

stats = {"history_fetch": 0, "history_hit": 0,
         "live_fetch": 0, "live_hit": 0, "failure": 0}


class MarketDataUnavailable(RuntimeError):
    """Raised when live mode has neither upstream data nor a cached value."""


def offline_mode():
    """Synthetic data instead of the network, for tests and offline development."""
    return os.environ.get("DELTA_OFFLINE") == "1"


def _fresh(entry, ttl):
    return entry and time.time() - entry["fetched_at"] < ttl


def _bar_timestamp(dates, fallback):
    """Return the timestamp of the newest exchange bar."""
    try:
        value = list(dates)[-1]
        if hasattr(value, "to_pydatetime"):
            value = value.to_pydatetime()
        elif not isinstance(value, datetime):
            value = datetime.fromisoformat(str(value)[:10])
        if value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        return value.timestamp()
    except (IndexError, TypeError, ValueError):
        return fallback


def _store_history(symbol, closes, volumes, dates, highs=None, lows=None, splits=None):
    fetched_at = time.time()
    date_values = list(dates)
    close_values = list(closes)
    volume_values = list(volumes)
    high_values = list(highs) if highs is not None else None
    low_values = list(lows) if lows is not None else None
    clean = []
    for index, (day, raw_close) in enumerate(zip(date_values, close_values)):
        try:
            close = float(raw_close)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(close) or close <= 0:
            continue

        raw_volume = volume_values[index] if index < len(volume_values) else 0
        try:
            volume = float(raw_volume)
        except (TypeError, ValueError):
            volume = 0
        volume = int(volume) if math.isfinite(volume) and volume >= 0 else 0

        def valid_price(values):
            if values is None or index >= len(values):
                return None
            try:
                value = float(values[index])
                return round(value, 2) if math.isfinite(value) and value > 0 else None
            except (TypeError, ValueError):
                return None

        clean.append((day, round(close, 2), volume,
                      valid_price(high_values), valid_price(low_values)))
    if not clean:
        raise ValueError(f"no finite prices for {symbol}")

    clean_dates, clean_closes, clean_volumes, clean_highs, clean_lows = zip(*clean)
    _history_cache[symbol] = {
        "symbol": symbol,
        "closes": list(clean_closes),
        "volumes": list(clean_volumes),
        "dates": [str(day)[:10] for day in clean_dates],
        "highs": list(clean_highs) if highs is not None else [],
        "lows": list(clean_lows) if lows is not None else [],
        # Exchange-reported split ratios keyed by date.
        "splits": splits or {},
        "as_of": _bar_timestamp(clean_dates, fetched_at),
        "fetched_at": fetched_at,
        "source": "yahoo",
        "stale": False,
    }
    return _history_cache[symbol]


def _splits_from(frame):
    """Dates where the exchange recorded a share split, and by what factor."""
    if "Stock Splits" not in frame:
        return {}
    column = frame["Stock Splits"].fillna(0)
    return {str(day)[:10]: float(ratio)
            for day, ratio in column.items() if ratio}


def get_history(symbol):
    """A year of daily closes + volumes, with age/source/stale metadata."""
    if offline_mode():
        return mock_history(symbol)

    cached = _history_cache.get(symbol)
    if _fresh(cached, HISTORY_TTL):
        stats["history_hit"] += 1
        return cached

    try:
        stats["history_fetch"] += 1
        frame = yf.Ticker(symbol).history(period="1y")
        if frame.empty:
            raise ValueError(f"no data for {symbol}")
        return _store_history(symbol, frame["Close"], frame["Volume"], frame.index,
                              frame.get("High"), frame.get("Low"),
                              _splits_from(frame))
    except Exception as exc:
        stats["failure"] += 1
        if cached:
            return {**cached, "stale": True}
        raise MarketDataUnavailable(f"market data unavailable for {symbol}") from exc


def warm_cache(symbols):
    """Populate the history cache with one batched request."""
    if offline_mode():
        return
    missing = [s for s in symbols if not _fresh(_history_cache.get(s), HISTORY_TTL)]
    if not missing:
        return
    try:
        stats["history_fetch"] += 1
        frame = yf.download(
            missing, period="1y", group_by="ticker",
            progress=False, auto_adjust=True, threads=True, actions=True,
        )
    except Exception:
        stats["failure"] += 1
        return
    for symbol in missing:
        try:
            data = frame[symbol] if len(missing) > 1 else frame
            data = data.dropna(subset=["Close"])
            if not data.empty:
                _store_history(symbol, data["Close"], data["Volume"], data.index,
                               data.get("High"), data.get("Low"),
                               _splits_from(data))
        except Exception:
            continue


def live_price(symbol):
    """The current intraday price, or None if we can't get one."""
    if offline_mode():
        return None
    cached = _live_cache.get(symbol)
    if _fresh(cached, LIVE_TTL):
        stats["live_hit"] += 1
        return cached
    try:
        stats["live_fetch"] += 1
        info = yf.Ticker(symbol).fast_info
        price = float(info["last_price"])
        if not math.isfinite(price) or price <= 0:
            raise ValueError("invalid live price")
        volume = info.get("last_volume")
        try:
            volume = float(volume) if volume is not None else None
        except (TypeError, ValueError):
            volume = None
        if volume is not None and (not math.isfinite(volume) or volume < 0):
            volume = None
        _live_cache[symbol] = {
            "price": round(price, 2),
            "volume": int(volume) if volume is not None else None,
            "fetched_at": time.time(),
        }
        return _live_cache[symbol]
    except Exception:
        stats["failure"] += 1
        return cached


def reconcile(history, live, market_open, now=None):
    """Select a daily or live quote and attach data-quality metadata."""
    closes = history["closes"]
    volumes = history.get("volumes") or []
    last_close = closes[-1] if closes else None
    prev_close = closes[-2] if len(closes) > 1 else None
    zone = ZoneInfo("Asia/Kolkata")
    now = now or datetime.now(zone)
    now = now.replace(tzinfo=zone) if now.tzinfo is None else now.astimezone(zone)
    current_bar = (
        market_open
        and bool(history.get("dates"))
        and history["dates"][-1] == now.date().isoformat()
    )
    completed_close = prev_close if current_bar else last_close
    quote = {
        "price": last_close,
        "compare_to": prev_close,
        "volume": volumes[-1] if volumes else None,
        "basis": "close",
        "as_of": history.get("as_of", history["fetched_at"]),
        "stale": history["stale"],
        "conflict": None,
    }
    if not market_open or live is None or last_close is None:
        return quote
    if not math.isfinite(live.get("price", float("nan"))):
        return quote

    if completed_close and abs(live["price"] - completed_close) / completed_close > IMPLAUSIBLE:
        quote["conflict"] = "live price ignored: implausibly far from the last close"
        return quote

    quote.update(
        price=live["price"],
        compare_to=completed_close,
        volume=live.get("volume", quote["volume"]),
        basis="live",
        as_of=live["fetched_at"],
        stale=time.time() - live["fetched_at"] > DELAYED_AFTER,
    )
    return quote


def get_quote(symbol, market_open):
    """History plus the reconciled current price for one stock."""
    history = get_history(symbol)
    live = live_price(symbol) if market_open else None
    return history, reconcile(history, live, market_open)


def index_history():
    """A year of NIFTY 50 closes, cached like any other symbol."""
    return get_history(INDEX)
