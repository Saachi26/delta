"""Tests for beta, residuals, and market breadth."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import market


def index_series(n=40):
    """Return a repeating symmetric series."""
    return [float((i % 5) - 2) for i in range(n)]


def scaled(moves, factor, drift=0.0):
    return [m * factor + drift for m in moves]


# --- beta -------------------------------------------------------------


def test_beta_of_a_stock_that_tracks_the_index_is_one():
    index = index_series()
    assert abs(market.beta(scaled(index, 1), index) - 1.0) < 1e-9


def test_beta_of_a_stock_that_moves_twice_as_hard_is_two():
    index = index_series()
    assert abs(market.beta(scaled(index, 2), index) - 2.0) < 1e-9


def test_beta_of_a_stock_that_moves_opposite_is_minus_one():
    index = index_series()
    assert abs(market.beta(scaled(index, -1), index) + 1.0) < 1e-9


def test_a_steady_drift_does_not_change_beta():
    # beta is about co-movement, not level: adding 0.3% every day changes nothing
    index = index_series()
    assert abs(market.beta(scaled(index, 1.5, drift=0.3), index) - 1.5) < 1e-9


def test_uncorrelated_series_has_beta_of_zero():
    # index flips every day, stock flips every two: the products cancel exactly
    index = [1.0 if i % 2 == 0 else -1.0 for i in range(40)]
    stock = [1.0 if i % 4 < 2 else -1.0 for i in range(40)]
    assert abs(market.beta(stock, index)) < 1e-9


def test_beta_needs_thirty_days():
    index = index_series(29)
    assert market.beta(scaled(index, 2), index) is None
    index = index_series(30)
    assert market.beta(scaled(index, 2), index) is not None


def test_beta_refuses_mismatched_lengths():
    assert market.beta(index_series(40), index_series(35)) is None


def test_beta_of_a_flat_index_is_none():
    assert market.beta(index_series(40), [0.0] * 40) is None


def test_beta_survives_empty_and_single_and_none_entries():
    assert market.beta([], []) is None
    assert market.beta([1.0], [1.0]) is None
    index = index_series(40)
    holes = scaled(index, 2)
    holes[0] = None  # one missing day drops that pair, 39 left, still enough
    assert abs(market.beta(holes, index) - 2.0) < 1e-9
    assert market.beta([None] * 40, index) is None


# --- residual_move ----------------------------------------------------


def test_residual_move_strips_out_the_market_part():
    assert abs(market.residual_move(-4.0, -4.0, 1.0)) < 1e-9
    assert abs(market.residual_move(-6.0, -2.0, 1.5) - -3.0) < 1e-9


def test_residual_move_without_a_beta_returns_the_raw_move():
    assert market.residual_move(-4.0, -4.0, None) == -4.0


# --- explains_the_move ------------------------------------------------


def test_market_driven_move_is_explained():
    # down 4% on a day the index is down 4%, beta 1: nothing left to explain
    assert market.explains_the_move(-4.0, -4.0, 1.0, 1.0) is True


def test_a_genuinely_company_specific_move_is_not_explained():
    # index down 1%, this stock down 8%: the market cannot take the blame
    assert market.explains_the_move(-8.0, -1.0, 1.0, 1.0) is False


def test_a_move_against_the_market_is_never_explained_by_it():
    # small residual, but the stock rose while the index fell
    assert market.explains_the_move(3.0, -3.0, -1.0, 5.0) is False


def test_no_residual_spread_means_we_cannot_excuse_the_move():
    assert market.explains_the_move(-4.0, -4.0, 1.0, 0) is False
    assert market.explains_the_move(-4.0, -4.0, 1.0, None) is False


def test_explains_the_move_survives_missing_inputs():
    assert market.explains_the_move(None, -4.0, 1.0, 1.0) is False
    assert market.explains_the_move(-4.0, None, 1.0, 1.0) is False


# --- breadth ----------------------------------------------------------


def test_broad_selloff_is_detected():
    result = market.breadth([-2.5, -2.0, -3.0, -2.2, -1.8, -2.6, -2.1, -1.4, 0.5, 1.2])
    assert result["direction"] == "down"
    assert result["count"] == 8
    assert result["total"] == 10
    assert result["share"] == 0.8
    assert result["mean_z"] < 0  # signed, so the digest can say "down"
    assert abs(result["mean_z"] - -2.2) < 1e-9


def test_an_up_day_keeps_a_positive_mean_z():
    result = market.breadth([2.0, 2.5, 1.8, 2.2, 3.0, -0.4])
    assert result["direction"] == "up"
    assert result["mean_z"] > 0
    assert result["share"] == 0.83


def test_a_mixed_day_is_not_a_market_day():
    assert market.breadth([2.5, -2.0, 3.1, -2.8, 2.2, -3.0]) is None


def test_three_stocks_are_too_few_to_call_the_market():
    assert market.breadth([-2.5, -3.0, -2.8]) is None


def test_everyone_agreeing_but_barely_moving_is_not_news():
    # eight stocks all down, but only a normal day's worth: stay quiet
    assert market.breadth([-0.4, -0.5, -0.3, -0.6, -0.2, -0.5, -0.4, -0.3]) is None


def test_missing_z_scores_are_ignored():
    result = market.breadth([-2.5, None, -2.0, None, -3.0, -2.5, 0.8])
    assert result["total"] == 5  # the two Nones never counted
    assert result["count"] == 4


def test_breadth_survives_empty_and_single_lists():
    assert market.breadth([]) is None
    assert market.breadth([-3.0]) is None
    assert market.breadth([None, None, None, None]) is None
    assert market.breadth([0.0, 0.0, 0.0, 0.0]) is None


# --- outliers ---------------------------------------------------------


def test_outliers_picks_the_stock_that_bucked_the_trend():
    scored = [("TCS", -2.1), ("INFY", -2.3), ("WIPRO", -2.0), ("YESBANK", 1.5)]
    assert market.outliers(scored, -2.2) == ["YESBANK"]


def test_nothing_stands_out_when_everything_moved_together():
    scored = [("TCS", -2.1), ("INFY", -2.3), ("WIPRO", -2.0)]
    assert market.outliers(scored, -2.2) == []


def test_outliers_keeps_input_order_and_ignores_missing_scores():
    scored = [("A", -5.0), ("B", None), ("C", -2.0), ("D", 4.0)]
    assert market.outliers(scored, -2.0) == ["A", "D"]


def test_outliers_min_gap_is_inclusive_and_adjustable():
    scored = [("A", 0.0), ("B", -3.5)]
    assert market.outliers(scored, -1.5) == ["A", "B"]   # both exactly 1.5 away
    # raise the bar to 2.0 and A (1.5 away) drops out, B (2.0 away) still counts
    assert market.outliers(scored, -1.5, min_gap=2.0) == ["B"]


def test_outliers_survives_empty_input_and_missing_mean():
    assert market.outliers([], -2.0) == []
    assert market.outliers([("A", -2.0)], None) == []
