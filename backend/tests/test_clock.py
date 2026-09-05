"""Tests for the NSE session clock and discovery ranking."""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

import main


IST = ZoneInfo("Asia/Kolkata")


def test_regular_session_reports_elapsed_fraction(monkeypatch):
    monkeypatch.delenv("NSE_HOLIDAYS", raising=False)
    state = main.market_state(datetime(2026, 9, 4, 10, 0, tzinfo=IST))

    assert state["open"] is True
    assert state["date"] == "2026-09-04"
    assert round(state["session_fraction"], 2) == 0.12


def test_weekends_and_exchange_holidays_are_closed(monkeypatch):
    monkeypatch.delenv("NSE_HOLIDAYS", raising=False)

    assert main.market_state(datetime(2026, 9, 5, 10, 0, tzinfo=IST))["open"] is False
    assert main.market_state(datetime(2026, 9, 14, 10, 0, tzinfo=IST))["open"] is False


def test_additional_holidays_can_be_configured(monkeypatch):
    monkeypatch.setenv("NSE_HOLIDAYS", "2027-01-04")
    state = main.market_state(datetime(2027, 1, 4, 10, 0, tzinfo=IST))

    assert state["open"] is False


def test_movers_rank_by_normalized_move(monkeypatch):
    monkeypatch.setattr(main.stocks, "POPULARITY", ["CALM.NS", "WILD.NS"])
    monkeypatch.setattr(main.quotes, "warm_cache", lambda _symbols: None)
    rows = {
        "CALM.NS": {"move_pct": 2.0, "price_z": 4.0, "volume_ratio": 1.0},
        "WILD.NS": {"move_pct": 8.0, "price_z": 0.8, "volume_ratio": 1.0},
    }
    monkeypatch.setattr(main, "build_row", lambda symbol: rows[symbol])

    assert main.ranked_symbols("movers", session=None) == ["CALM.NS", "WILD.NS"]
