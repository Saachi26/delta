"""Tests for statistical signals."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import signals


def steady_moves(n=30, size=0.5):
    """Return alternating daily changes."""
    return [size if i % 2 == 0 else -size for i in range(n)]


def test_daily_moves_basic():
    assert signals.daily_moves([100, 110, 99]) == [10.0, -10.0]


def test_same_move_scores_differently_per_stock():
    calm = steady_moves(size=0.5)
    wild = [8, -7, 6, -9, 7, -6, 8, -8, 5, -7] * 3
    z_calm = signals.zscore(5.0, calm)
    z_wild = signals.zscore(5.0, wild)
    assert abs(z_calm) > 2
    assert abs(z_wild) < 1


def test_no_baseline_means_no_signal():
    assert signals.zscore(5.0, [1.0, -1.0, 0.5]) is None
    assert signals.typical_spread([1.0, -1.0]) is None
    assert signals.volume_ratio(1000, [500]) is None


def test_zero_variance_baseline_is_handled():
    assert signals.zscore(2.0, [0.0] * 30) is None


def test_volume_ratio():
    assert signals.volume_ratio(3000, [1000] * 30) == 3.0
    assert signals.volume_ratio(1000, [0] * 30) is None


def test_intraday_volume_is_compared_at_equal_session_progress():
    baseline = [1000] * 30
    assert signals.volume_ratio(500, baseline, elapsed_fraction=0.5) == 1.0
    assert signals.volume_ratio(1000, baseline, elapsed_fraction=0.5) == 2.0


def test_intraday_volume_fraction_is_bounded_and_validated():
    baseline = [1000] * 30
    assert signals.volume_ratio(50, baseline, elapsed_fraction=0) == 1.0
    assert signals.volume_ratio(1000, baseline, elapsed_fraction=2) == 1.0
    assert signals.volume_ratio(1000, baseline, elapsed_fraction=None) is None


def test_52_week_landmarks():
    closes = [100, 105, 110, 95, 102, 108, 99]
    assert signals.crossed_52w(111, closes) == "high"
    assert signals.crossed_52w(94, closes) == "low"
    assert signals.crossed_52w(103, closes) is None


def test_flat_history_is_not_a_landmark():
    assert signals.crossed_52w(100, [100] * 40) is None


def test_attention_score_ranges():
    assert signals.attention_score(None, None, None) == 0
    assert signals.attention_score(0.1, 1.0, None) < 30
    big = signals.attention_score(4.0, 5.0, "high")
    assert 60 < big <= 100


def test_quiet_stock_produces_no_reasons():
    assert signals.explain(0.3, 0.4, 1.1, None, 0.8) == []


def test_unusual_drop_is_explained_in_plain_words():
    reasons = signals.explain(-4.2, -3.5, 1.0, None, 1.1)
    assert len(reasons) == 1
    assert "fell 4.2%" in reasons[0]
    assert "unusual" in reasons[0]


def test_volume_spike_is_explained():
    reasons = signals.explain(0.2, 0.1, 4.0, None, 1.0)
    assert any("volume" in r for r in reasons)


def test_turnover_uses_price_times_shares():
    assert signals.typical_turnover([100] * 30, [1000] * 30) == 100_000


def test_a_thinly_traded_stock_is_not_worth_a_card():
    thin = signals.typical_turnover([10] * 30, [500] * 30)      # Rs 5,000 a day
    liquid = signals.typical_turnover([1000] * 30, [200_000] * 30)  # Rs 20 crore
    assert signals.too_thin_to_trust(thin) is True
    assert signals.too_thin_to_trust(liquid) is False
    assert signals.too_thin_to_trust(None) is False


def test_turnover_needs_history():
    assert signals.typical_turnover([100, 200], [10, 20]) is None
