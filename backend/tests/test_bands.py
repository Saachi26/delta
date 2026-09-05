"""Tests for price band detection."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import bands


def test_a_stock_locked_at_its_upper_band_is_flagged():
    flag = bands.hit_price_band(5.0, close=105, high=105, low=101)
    assert flag == {"direction": "upper", "band": 5}
    assert "capped" in bands.describe(flag)


def test_a_stock_locked_at_its_lower_band_is_flagged():
    flag = bands.hit_price_band(-20.0, close=80, high=99, low=80)
    assert flag == {"direction": "lower", "band": 20}
    assert "lower" in bands.describe(flag)


def test_a_band_sized_move_that_did_not_close_at_the_extreme_is_ordinary():
    # moved 5% but drifted back off the high, so it was never locked
    assert bands.hit_price_band(5.0, close=104, high=106, low=100) is None


def test_a_move_between_bands_is_ordinary():
    assert bands.hit_price_band(7.0, close=107, high=107, low=100) is None


def test_small_moves_are_never_bands():
    assert bands.hit_price_band(0.4, close=100.4, high=100.4, low=99) is None


def test_tolerance_allows_a_near_miss_on_the_band():
    assert bands.hit_price_band(4.8, close=104.8, high=104.8, low=100)["band"] == 5
    assert bands.hit_price_band(4.2, close=104.2, high=104.2, low=100) is None


def test_missing_or_broken_bar_data_is_not_a_band():
    assert bands.hit_price_band(5.0, close=None, high=105, low=100) is None
    assert bands.hit_price_band(5.0, close=105, high=None, low=100) is None
    assert bands.hit_price_band(5.0, close=0, high=0, low=0) is None
    assert bands.describe(None) is None
