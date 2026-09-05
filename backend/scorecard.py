"""Build the stock-detail scorecard."""
from statistics import mean, median

TRADING_DAYS = {"1W": 5, "1M": 21, "3M": 63, "1Y": 250}


def pct_change(closes, days):
    """Percent change over the last N trading days, or None if too short."""
    if len(closes) <= days or not closes[-days - 1]:
        return None
    return round((closes[-1] - closes[-days - 1]) / closes[-days - 1] * 100, 2)


def returns(closes):
    """Return changes for the configured time windows."""
    return {label: pct_change(closes, days) for label, days in TRADING_DAYS.items()}


def max_drawdown(closes):
    """The worst peak-to-trough fall in the window, as a negative percent."""
    if len(closes) < 2:
        return None
    peak, worst = closes[0], 0.0
    for price in closes:
        peak = max(peak, price)
        if peak:
            worst = min(worst, (price - peak) / peak * 100)
    return round(worst, 1)


def range_position(price, closes):
    """Where the price sits between the 52-week low and high, 0-100.

    Today's price is part of the range: a stock making a new high sits at
    100, never above it.
    """
    if not closes:
        return None
    window = list(closes) + [price]
    low, high = min(window), max(window)
    if high == low:
        return None
    return round((price - low) / (high - low) * 100)


def moving_average(closes, days=50):
    """The average close over the last N days, or None if history is short."""
    if len(closes) < days:
        return None
    return round(mean(closes[-days:]), 2)


def sector_move(peer_moves):
    """The typical move across a stock's sector today."""
    return round(median(peer_moves), 2) if peer_moves else None


def _row(key, label, badge, tone, sentence, detail=None):
    return {"key": key, "label": label, "badge": badge, "tone": tone,
            "sentence": sentence, "detail": detail}


def build(row, closes, peer_moves, market_open):
    """The five-or-six row scorecard for one stock."""
    price = row["price"]
    move = row["move_pct"]
    spread = row["spread"]
    rows = []

    # Price movement
    if spread:
        ratio = abs(move) / spread
        if ratio >= 3:
            badge, tone = "Unusual", "alert"
        elif ratio >= 1.5:
            badge, tone = "Notable", "warn"
        else:
            badge, tone = "Normal", "calm"
        rows.append(_row(
            "unusualness", "Today's move", badge, tone,
            f"Moved {abs(move):.1f}%, about {ratio:.1f}× its normal day.",
            f"A normal day for this stock is ±{spread}%. Measured against its own "
            f"last 30 days, not a fixed threshold.",
        ))

    # Volume
    volume_ratio = row.get("volume_ratio")
    if volume_ratio:
        if volume_ratio >= 3:
            badge, tone = "Spike", "alert"
        elif volume_ratio >= 1.5:
            badge, tone = "Busy", "warn"
        else:
            badge, tone = "Normal", "calm"
        rows.append(_row(
            "volume", "Trading volume", badge, tone,
            f"Trading at {volume_ratio:.1f}× its recent average volume.",
            "Volume often moves before price does: heavy trading on a flat price "
            "means people are taking positions.",
        ))

    # Risk
    drawdown = max_drawdown(closes)
    if spread:
        if spread >= 2.5:
            badge, tone = "Volatile", "alert"
        elif spread >= 1.2:
            badge, tone = "Average", "warn"
        else:
            badge, tone = "Steady", "calm"
        drop = f" Its worst fall this year was {drawdown}%." if drawdown else ""
        rows.append(_row(
            "risk", "How bumpy it is", badge, tone,
            f"Swings about ±{spread}% on a typical day.{drop}",
            "Two plain measures instead of a risk rating: the size of an ordinary "
            "day, and the deepest peak-to-trough fall in the last year.",
        ))

    # 52-week range
    position = range_position(price, closes[:-1] or closes)
    if position is not None:
        if position == 100:
            badge, tone = "At its high", "warn"
            sentence = "At the top of its 52-week range, a fresh high."
        elif position == 0:
            badge, tone = "At its low", "warn"
            sentence = "At the bottom of its 52-week range, a fresh low."
        elif position >= 90:
            badge, tone = "Near high", "warn"
            sentence = f"Sitting {position}% of the way up its 52-week range."
        elif position <= 10:
            badge, tone = "Near low", "warn"
            sentence = f"Sitting {position}% of the way up its 52-week range."
        else:
            badge, tone = "Mid-range", "calm"
            sentence = f"Sitting {position}% of the way up its 52-week range."
        window = list(closes) + [price]
        rows.append(_row(
            "range", "52-week range", badge, tone, sentence,
            f"Low ₹{min(window):,.2f} · high ₹{max(window):,.2f} over the last year, "
            "today's price included.",
        ))

    # Trend
    average = moving_average(closes)
    if average:
        above = price >= average
        badge, tone = ("Rising", "calm") if above else ("Falling", "warn")
        gap = abs(price - average) / average * 100
        rows.append(_row(
            "trend", "Recent trend", badge, tone,
            f"Trading {gap:.1f}% {'above' if above else 'below'} its 50-day average.",
            f"50-day average is ₹{average:,.2f}. A rough read on direction, not a "
            "prediction.",
        ))

    # Sector comparison
    peer = sector_move(peer_moves)
    if peer is not None:
        gap = move - peer
        if abs(gap) < 0.5:
            badge, tone, verdict = "Sector-wide", "calm", (
                f"The whole {row['sector']} sector moved about {peer:+.1f}% too, "
                "so this looks like sector news, not company news."
            )
        else:
            badge, tone, verdict = "Stock-specific", "warn", (
                f"Its sector moved {peer:+.1f}% while this moved {move:+.1f}%, "
                "something is happening to this company in particular."
            )
        rows.append(_row(
            "sector", "Versus its sector", badge, tone, verdict,
            "Compared against the median move of the other stocks Delta tracks in "
            "the same sector today.",
        ))

    # Market comparison
    beta = row.get("beta")
    index_move = row.get("index_move")
    if beta is not None and index_move is not None:
        expected = beta * index_move
        if row.get("market_explained"):
            badge, tone = "Market move", "calm"
            verdict = (
                f"The market moved {index_move:+.1f}% today and this stock "
                f"normally moves about {beta}x the market, so today looks like "
                "the market, not company news."
            )
        else:
            badge, tone = "Its own move", "warn"
            verdict = (
                f"The market moved {index_move:+.1f}%, which explains about "
                f"{expected:+.1f}% of today. The rest, {row['residual_move']:+.1f}%, "
                "is this company on its own."
            )
        rows.append(_row(
            "market", "Versus the market", badge, tone, verdict,
            f"Beta {beta} means that when the NIFTY 50 moves 1%, this stock has "
            f"historically moved about {beta}%. What beta cannot explain is the "
            "part worth reading.",
        ))

    # Data quality
    if row.get("source") == "simulation":
        badge, tone, sentence = "Simulation", "calm", (
            "This is deterministic evaluation data, not a live market price."
        )
    elif row["conflict"]:
        badge, tone, sentence = "Conflict", "alert", row["conflict"]
    elif row["stale"]:
        badge, tone, sentence = "Delayed", "warn", "This price is more than 15 minutes old."
    elif row["basis"] == "live":
        badge, tone, sentence = "Live", "calm", "Live intraday price, refreshed every 30 seconds."
    else:
        badge, tone, sentence = "Last close", "calm", (
            "The market is shut, so this is the last closing price."
            if not market_open else "Showing the last close for this stock."
        )
    rows.append(_row(
        "data", "Data quality", badge, tone, sentence,
        "Every price says where it came from and how old it is. Nothing stale is "
        "shown as if it were live.",
    ))

    return rows
