"""Tests for split detection."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import corporate


def calm_moves():
    """Return a low-volatility series."""
    return [0.5, -0.4, 0.6, -0.5, 0.3, -0.6, 0.4, -0.3]


def wild_moves():
    """Return a high-volatility series."""
    return [18, -15, 20, -22, 17, -19, 25, -21]


def adjusted_change(new_price, hit):
    """Calculate change after adjusting for a detected split."""
    return (new_price - hit["adjusted_old"]) / hit["adjusted_old"] * 100


# --- the bug ----------------------------------------------------------


def test_unadjusted_split_looks_like_a_price_drop():
    # RELIANCE closes at 1000, does a 4-for-1 split, opens at 250
    old, new = 1000.0, 250.0
    naive = (new - old) / old * 100
    assert naive == -75.0  # what the app confidently reported: "down 75%"

    hit = corporate.detect_split(old, new)
    assert hit is not None
    assert adjusted_change(new, hit) == 0.0


# --- clean splits -----------------------------------------------------


def test_clean_four_for_one():
    hit = corporate.detect_split(1000.0, 250.0)
    assert hit == {
        "ratio": 4.0,
        "label": "4-for-1 split",
        "kind": "split",
        "adjusted_old": 250.0,
    }


def test_two_for_one():
    hit = corporate.detect_split(3200.0, 1600.0)
    assert hit["ratio"] == 2.0
    assert hit["kind"] == "split"
    assert hit["label"] == "2-for-1 split"
    assert hit["adjusted_old"] == 1600.0


def test_ten_for_one():
    hit = corporate.detect_split(2500.0, 250.0)
    assert hit["ratio"] == 10.0
    assert hit["label"] == "10-for-1 split"
    assert hit["adjusted_old"] == 250.0


def test_twenty_for_one():
    hit = corporate.detect_split(4000.0, 200.0)
    assert hit["ratio"] == 20.0
    assert hit["adjusted_old"] == 200.0


def test_one_for_ten_reverse():
    hit = corporate.detect_split(400.0, 4000.0)
    assert hit == {
        "ratio": 0.1,
        "label": "1-for-10 reverse split",
        "kind": "reverse",
        "adjusted_old": 4000.0,
    }


def test_one_for_two_reverse():
    hit = corporate.detect_split(50.0, 100.0)
    assert hit["kind"] == "reverse"
    assert hit["label"] == "1-for-2 reverse split"
    assert hit["adjusted_old"] == 100.0
    assert adjusted_change(100.0, hit) == 0.0


# --- tolerance --------------------------------------------------------


def test_a_slightly_imperfect_ratio_still_reads_as_a_split():
    # a real split plus a real 0.4% move on the day: implied ratio 3.98
    hit = corporate.detect_split(1000.0, 251.0)
    assert hit["ratio"] == 4.0
    assert hit["adjusted_old"] == 250.0  # the EXACT ratio, not the observed one
    assert round(adjusted_change(251.0, hit), 2) == 0.40


def test_a_ratio_that_is_not_a_split_is_left_alone():
    assert corporate.detect_split(1000.0, 294.0) is None  # implied 3.40
    assert corporate.detect_split(1000.0, 600.0) is None  # implied 1.67
    assert corporate.detect_split(1000.0, 140.0) is None  # implied 7.14
    assert corporate.detect_split(1000.0, 1700.0) is None  # implied 0.59


def test_the_edge_of_the_tolerance_band():
    assert corporate.detect_split(1000.0, 262.0)["ratio"] == 4.0  # 3.82, ~4.5% off
    assert corporate.detect_split(1000.0, 270.0) is None  # 3.70, ~7.4% off


def test_near_match_requires_volatility_cross_check():
    # 1000 -> 340 is a 66% crash, but it also sits 2% from a real 3-for-1, so
    # the tolerance band alone cannot rule it out. pinned here so the
    # behaviour is a known decision rather than an accident
    hit = corporate.detect_split(1000.0, 340.0)
    assert hit["label"] == "3-for-1 split"
    # with any recent history at all, the volatility cross-check still fires
    assert corporate.detect_split(1000.0, 340.0, wild_moves()) is None


# --- ordinary days ----------------------------------------------------


def test_an_ordinary_down_move_is_never_a_split():
    assert corporate.detect_split(100.0, 95.0) is None


def test_an_ordinary_up_move_is_never_a_split():
    assert corporate.detect_split(100.0, 102.0) is None


def test_a_big_but_unsplitlike_move_is_never_a_split():
    assert corporate.detect_split(100.0, 55.0) is None  # -45%, implied 1.82


# --- the volatility cross-check ---------------------------------------


def test_large_move_on_volatile_stock_is_not_reclassified():
    assert corporate.detect_split(1000.0, 250.0, wild_moves()) is None


def test_the_same_crash_on_a_calm_stock_is_a_split():
    hit = corporate.detect_split(1000.0, 250.0, calm_moves())
    assert hit["ratio"] == 4.0
    assert hit["adjusted_old"] == 250.0


def test_too_little_history_means_the_volatility_check_abstains():
    # 5 entries is below MIN_HISTORY, so we fall back to the ratio evidence alone
    assert corporate.detect_split(1000.0, 250.0, [20, -18, 22, -19, 21]) is not None
    assert corporate.detect_split(1000.0, 250.0, []) is not None


def test_a_stock_with_no_spread_at_all_does_not_break_the_check():
    assert corporate.detect_split(1000.0, 250.0, [0.0] * 8) is not None


def test_moves_are_ignored_when_they_are_junk():
    assert corporate.detect_split(1000.0, 250.0, [None, None, None]) is not None


# --- degenerate input -------------------------------------------------


def test_missing_prices_return_none_rather_than_raising():
    assert corporate.detect_split(None, 250.0) is None
    assert corporate.detect_split(1000.0, None) is None
    assert corporate.detect_split(None, None) is None


def test_zero_and_negative_prices_return_none():
    assert corporate.detect_split(0.0, 250.0) is None
    assert corporate.detect_split(1000.0, 0.0) is None
    assert corporate.detect_split(-1000.0, -250.0) is None
    assert corporate.detect_split(1000.0, -250.0) is None


def test_non_numeric_prices_return_none():
    assert corporate.detect_split("1000", 250.0) is None
    assert corporate.detect_split(float("nan"), 250.0) is None
    assert corporate.detect_split(1000.0, float("inf")) is None


def test_identical_prices_are_not_a_split():
    assert corporate.detect_split(250.0, 250.0) is None
    assert corporate.detect_split(0.5, 0.5) is None


# --- the exchange's own split record, which beats inferring one ---


def test_a_split_recorded_after_the_snapshot_is_used():
    splits = {"2026-06-04": 1.5, "2020-01-02": 2.0}
    assert corporate.recorded_split_since(splits, "2026-01-01") == 1.5


def test_splits_before_the_snapshot_are_already_in_the_price():
    splits = {"2020-01-02": 2.0}
    assert corporate.recorded_split_since(splits, "2026-01-01") is None


def test_two_splits_since_the_snapshot_compound():
    splits = {"2026-02-01": 2.0, "2026-05-01": 3.0}
    assert corporate.recorded_split_since(splits, "2026-01-01") == 6.0


def test_no_record_at_all_is_not_a_split():
    assert corporate.recorded_split_since({}, "2026-01-01") is None
    assert corporate.recorded_split_since(None, "2026-01-01") is None
