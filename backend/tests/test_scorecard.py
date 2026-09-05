"""Tests for scorecard calculations."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import scorecard


def rising(n=260, start=100.0, step=0.4):
    return [round(start * (1 + step / 100) ** i, 2) for i in range(n)]


def test_returns_over_each_window():
    closes = rising()
    table = scorecard.returns(closes)
    assert set(table) == {"1W", "1M", "3M", "1Y"}
    assert table["1W"] > 0 and table["1Y"] > table["1M"]  # steady climb compounds


def test_returns_are_none_when_history_is_short():
    assert scorecard.returns([100, 101, 102])["1M"] is None


def test_max_drawdown_finds_the_worst_fall():
    assert scorecard.max_drawdown([100, 120, 60, 90]) == -50.0
    assert scorecard.max_drawdown([100, 110, 120]) == 0.0
    assert scorecard.max_drawdown([100]) is None


def test_range_position():
    closes = [100, 150, 200]
    assert scorecard.range_position(200, closes) == 100
    assert scorecard.range_position(100, closes) == 0
    assert scorecard.range_position(150, closes) == 50
    assert scorecard.range_position(100, [100, 100]) is None  # flat, no range


def test_a_new_high_sits_at_100_not_above_it():
    # today's price is part of the range, so 110% can never be shown
    assert scorecard.range_position(260, [100, 150, 200]) == 100
    assert scorecard.range_position(50, [100, 150, 200]) == 0


def test_new_high_is_worded_as_a_fresh_high():
    rows = scorecard.build(base_row(price=999), rising(), [], False)
    row = next(r for r in rows if r["key"] == "range")
    assert row["badge"] == "At its high"
    assert "fresh high" in row["sentence"]


def test_moving_average_needs_enough_days():
    assert scorecard.moving_average([10] * 50) == 10
    assert scorecard.moving_average([10] * 20) is None


def test_sector_move_uses_the_median_so_one_outlier_cannot_skew_it():
    assert scorecard.sector_move([0.2, 0.3, 0.4, 40.0]) == 0.35
    assert scorecard.sector_move([]) is None


def base_row(**over):
    row = {"price": 150.0, "move_pct": 0.4, "spread": 0.5, "sector": "Technology",
           "volume_ratio": 1.0, "conflict": None, "stale": False, "basis": "close",
           "beta": None, "index_move": None, "residual_move": 0.4,
           "market_explained": False}
    row.update(over)
    return row


def grades(rows):
    return {r["key"]: r["badge"] for r in rows}


def test_a_big_move_for_a_calm_stock_is_graded_unusual():
    rows = scorecard.build(base_row(move_pct=3.0, spread=0.5), rising(), [], False)
    assert grades(rows)["unusualness"] == "Unusual"


def test_the_same_move_on_a_wild_stock_is_normal():
    rows = scorecard.build(base_row(move_pct=3.0, spread=2.6), rising(), [], False)
    assert grades(rows)["unusualness"] == "Normal"
    assert grades(rows)["risk"] == "Volatile"


def test_sector_wide_moves_are_called_out_as_sector_news():
    rows = scorecard.build(base_row(move_pct=-4.0), rising(), [-4.1, -3.9, -4.0], False)
    row = next(r for r in rows if r["key"] == "sector")
    assert row["badge"] == "Sector-wide"
    assert "sector news" in row["sentence"]


def test_a_lone_mover_is_called_out_as_company_news():
    rows = scorecard.build(base_row(move_pct=-4.0), rising(), [0.1, -0.2, 0.0], False)
    row = next(r for r in rows if r["key"] == "sector")
    assert row["badge"] == "Stock-specific"


def test_data_quality_row_always_exists_and_reports_conflicts():
    rows = scorecard.build(base_row(), rising(), [], False)
    assert grades(rows)["data"] == "Last close"
    rows = scorecard.build(base_row(basis="live"), rising(), [], True)
    assert grades(rows)["data"] == "Live"
    rows = scorecard.build(base_row(stale=True), rising(), [], True)
    assert grades(rows)["data"] == "Delayed"
    rows = scorecard.build(base_row(conflict="live price ignored"), rising(), [], True)
    assert grades(rows)["data"] == "Conflict"


def test_simulated_prices_are_never_labelled_live_or_last_close():
    rows = scorecard.build(base_row(source="simulation"), rising(), [], False)
    data = next(row for row in rows if row["key"] == "data")
    assert data["badge"] == "Simulation"
    assert "not a live market price" in data["sentence"]


def test_a_move_the_market_explains_is_labelled_as_such():
    row = base_row(move_pct=-2.0, beta=1.8, index_move=-1.1,
                   residual_move=-0.02, market_explained=True)
    card = next(r for r in scorecard.build(row, rising(), [], True) if r["key"] == "market")
    assert card["badge"] == "Market move"
    assert "not company news" in card["sentence"]


def test_a_move_the_market_does_not_explain_is_the_company_itself():
    row = base_row(move_pct=-6.0, beta=1.0, index_move=-0.2,
                   residual_move=-5.8, market_explained=False)
    card = next(r for r in scorecard.build(row, rising(), [], True) if r["key"] == "market")
    assert card["badge"] == "Its own move"
    assert "-5.8%" in card["sentence"]


def test_no_market_row_without_index_data():
    keys = [r["key"] for r in scorecard.build(base_row(), rising(), [], True)]
    assert "market" not in keys
