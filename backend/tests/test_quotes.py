"""Tests for market-data failure and timestamp handling."""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import quotes


class BrokenTicker:
    def history(self, **_kwargs):
        raise OSError("upstream unavailable")


@pytest.fixture(autouse=True)
def reset_quote_cache():
    quotes._history_cache.clear()
    quotes._live_cache.clear()
    yield
    quotes._history_cache.clear()
    quotes._live_cache.clear()


def test_live_mode_never_substitutes_synthetic_prices(monkeypatch):
    monkeypatch.delenv("DELTA_OFFLINE", raising=False)
    monkeypatch.setattr(quotes.yf, "Ticker", lambda _symbol: BrokenTicker())

    with pytest.raises(quotes.MarketDataUnavailable):
        quotes.get_history("INFY.NS")


def test_failed_refresh_returns_an_existing_value_as_stale(monkeypatch):
    monkeypatch.delenv("DELTA_OFFLINE", raising=False)
    monkeypatch.setattr(quotes.yf, "Ticker", lambda _symbol: BrokenTicker())
    cached = quotes._store_history(
        "INFY.NS",
        [100.0, 101.0],
        [1000, 1100],
        ["2026-09-03", "2026-09-04"],
    )
    cached["fetched_at"] = 0

    history = quotes.get_history("INFY.NS")

    assert history["source"] == "yahoo"
    assert history["stale"] is True
    assert history["closes"] == [100.0, 101.0]


def test_daily_quote_uses_the_exchange_bar_timestamp():
    bar_time = datetime(2026, 9, 4, tzinfo=ZoneInfo("Asia/Kolkata"))
    history = quotes._store_history(
        "INFY.NS",
        [100.0, 101.0],
        [1000, 1100],
        [datetime(2026, 9, 3), bar_time],
    )

    quote = quotes.reconcile(history, live=None, market_open=False)

    assert quote["as_of"] == bar_time.timestamp()
    assert quote["as_of"] != history["fetched_at"]


def test_history_discards_non_finite_prices_and_keeps_rows_aligned():
    history = quotes._store_history(
        "INFY.NS",
        [100.0, float("nan"), 102.0],
        [1000, 1100, float("nan")],
        ["2026-09-02", "2026-09-03", "2026-09-04"],
    )

    assert history["closes"] == [100.0, 102.0]
    assert history["volumes"] == [1000, 0]
    assert history["dates"] == ["2026-09-02", "2026-09-04"]


def test_non_finite_live_price_is_ignored(monkeypatch):
    class Ticker:
        fast_info = {"last_price": float("nan"), "last_volume": 1000}

    monkeypatch.delenv("DELTA_OFFLINE", raising=False)
    monkeypatch.setattr(quotes.yf, "Ticker", lambda _symbol: Ticker())

    assert quotes.live_price("INFY.NS") is None


def test_live_quote_uses_previous_close_when_history_contains_today():
    now = datetime(2026, 9, 4, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    history = {
        "closes": [100.0, 101.0, 103.0],
        "volumes": [1000, 1100, 400],
        "dates": ["2026-09-02", "2026-09-03", "2026-09-04"],
        "as_of": now.timestamp(),
        "fetched_at": now.timestamp(),
        "stale": False,
    }
    live = {"price": 104.0, "volume": 500, "fetched_at": now.timestamp()}

    quote = quotes.reconcile(history, live, market_open=True, now=now)

    assert quote["price"] == 104.0
    assert quote["compare_to"] == 101.0
    assert quote["volume"] == 500
