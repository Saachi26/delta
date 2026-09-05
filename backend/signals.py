"""Statistical signal calculations."""
from statistics import mean, median, stdev

MIN_HISTORY = 6
THIN_TURNOVER = 20_000_000


def daily_moves(closes):
    """Percent change between consecutive closes."""
    return [(b - a) / a * 100 for a, b in zip(closes, closes[1:]) if a]


def typical_spread(moves):
    """How much this stock swings on a normal day (std dev of daily moves)."""
    if len(moves) < MIN_HISTORY:
        return None
    return stdev(moves)


def zscore(move, baseline_moves):
    """How many 'normal days' worth of movement today's move is."""
    if len(baseline_moves) < MIN_HISTORY:
        return None
    average = mean(baseline_moves)
    spread = stdev(baseline_moves)
    if spread == 0:
        return None
    return (move - average) / spread


def volume_ratio(volume, baseline_volumes, elapsed_fraction=1.0):
    """Volume relative to the expected baseline at this point in the session."""
    if len(baseline_volumes) < MIN_HISTORY:
        return None
    typical = median(baseline_volumes)
    if typical == 0 or not isinstance(elapsed_fraction, (int, float)):
        return None
    fraction = max(0.05, min(float(elapsed_fraction), 1.0))
    return volume / (typical * fraction)


def crossed_52w(price, past_closes):
    """'high' or 'low' if price crossed its 52-week extreme, else None."""
    if len(past_closes) < MIN_HISTORY:
        return None
    if price > max(past_closes):  # strict: merely matching the high isn't a cross
        return "high"
    if price < min(past_closes):
        return "low"
    return None


def attention_score(z, vol_ratio, landmark):
    """Calculate the 0-100 attention score."""
    score = 0.0
    if z is not None:
        score += min(abs(z) * 20, 60)
    if vol_ratio is not None and vol_ratio > 1:
        score += min((vol_ratio - 1) * 12, 35)
    if landmark:
        score += 15
    return round(min(score, 100), 1)


def explain(move_pct, z, vol_ratio, landmark, spread):
    """Plain-language reasons this stock made the digest."""
    reasons = []
    if z is not None and abs(z) >= 2 and spread:
        verb = "fell" if move_pct < 0 else "rose"
        reasons.append(
            f"{verb} {abs(move_pct):.1f}%, unusual for this stock "
            f"(typical day: ±{spread:.1f}%)"
        )
    if vol_ratio is not None and vol_ratio >= 3:
        reasons.append(f"volume is {vol_ratio:.0f}× its recent average")
    if landmark == "high":
        reasons.append("crossed its 52-week high")
    elif landmark == "low":
        reasons.append("fell below its 52-week low")
    return reasons


def attention_label(score):
    """Map a score to its display label."""
    if score >= 60:
        return "Alert"
    if score >= 30:
        return "Notable"
    return "Quiet"


def typical_turnover(closes, volumes):
    """Median daily turnover in rupees."""
    if len(closes) < MIN_HISTORY or len(volumes) < MIN_HISTORY:
        return None
    pairs = list(zip(closes, volumes))[-30:]
    return median([price * shares for price, shares in pairs])


def too_thin_to_trust(turnover):
    """Return whether typical turnover is below the configured threshold."""
    return turnover is not None and turnover < THIN_TURNOVER
