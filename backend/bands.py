"""Infer NSE price-band events from daily bars."""

BANDS = [2, 5, 10, 20]
TOLERANCE = 0.35  # how close to the band value counts as sitting on it


def _on_a_band(move_pct):
    """The band this move appears to be sitting on, if any."""
    for band in BANDS:
        if abs(abs(move_pct) - band) <= TOLERANCE:
            return band
    return None


def hit_price_band(move_pct, close, high, low):
    """Whether the day looks like it ended locked at a price band.

    Closing exactly at the high (or low) is what separates a stock frozen at
    its limit from one that merely happened to move about that much.
    """
    if close is None or high is None or low is None or high <= 0:
        return None
    band = _on_a_band(move_pct)
    if band is None:
        return None
    if move_pct > 0 and close >= high:
        return {"direction": "upper", "band": band}
    if move_pct < 0 and close <= low:
        return {"direction": "lower", "band": band}
    return None


def describe(flag):
    """Format a price-band flag for display."""
    if not flag:
        return None
    side = "upper" if flag["direction"] == "upper" else "lower"
    return (
        f"Looks like it closed locked at its {side} price band of {flag['band']}%. "
        "The price stopped moving because it is capped, not because it settled."
    )
