"""Share-split detection and snapshot adjustment."""
import math
from statistics import stdev

MIN_MOVE_PCT = 30.0
RATIO_TOLERANCE = 0.06
OUTLIER_MULTIPLE = 8
MIN_HISTORY = 6
SPLIT_RATIOS = [2, 3, 4, 5, 10, 20]


def _is_price(value):
    """True when value is a real, positive number we can divide by."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) and value > 0  # isfinite also rejects NaN


def _candidates():
    """Every supported ratio as (exact_ratio, kind, label)."""
    out = []
    for n in SPLIT_RATIOS:
        out.append((float(n), "split", f"{n}-for-1 split"))
        out.append((1.0 / n, "reverse", f"1-for-{n} reverse split"))
    return out


def _match_ratio(ratio):
    """The real-world ratio this implied ratio is within tolerance of, else None."""
    for exact, kind, label in _candidates():
        # Apply tolerance relative to the candidate ratio.
        if abs(ratio - exact) / exact <= RATIO_TOLERANCE:
            return exact, kind, label
    return None


def _is_outlier(change_pct, moves):
    """True when the move dwarfs this stock's normal day, or we cannot tell."""
    clean = [m for m in (moves or []) if isinstance(m, (int, float)) and not isinstance(m, bool)]
    if len(clean) < MIN_HISTORY:
        return True  # no baseline to argue with, so this check abstains
    spread = stdev(clean)
    if spread <= 0:
        return True  # a stock that never moves: any jump is an outlier
    return abs(change_pct) >= OUTLIER_MULTIPLE * spread


def detect_split(old_price, new_price, moves=None):
    """Split details when the price change is better explained by a split, else None."""
    if not _is_price(old_price) or not _is_price(new_price):
        return None
    if old_price == new_price:
        return None
    change_pct = (new_price - old_price) / old_price * 100
    if abs(change_pct) < MIN_MOVE_PCT:
        return None
    match = _match_ratio(old_price / new_price)
    if match is None:
        return None
    if not _is_outlier(change_pct, moves):
        return None
    exact, kind, label = match
    return {
        "ratio": round(exact, 4),
        "label": label,
        "kind": kind,
        # Preserve any same-day price movement by using the exact split ratio.
        "adjusted_old": round(old_price / exact, 4),
    }


def recorded_split_since(splits, since_date):
    """The split factor the exchange recorded after a given date, if any.

    Preferred over detect_split: this is the reported corporate action rather
    than a guess from two prices. detect_split stays as the fallback for bonus
    issues, which are common in India and are not always recorded as splits.
    """
    factor = 1.0
    for day, ratio in (splits or {}).items():
        if ratio and day > since_date:
            factor *= float(ratio)
    return factor if factor != 1.0 else None
