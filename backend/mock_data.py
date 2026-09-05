"""Deterministic simulated market data for tests and evaluation replay."""
import time
from datetime import date, datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

BASE_DAYS = 250

REPLAY_STEPS = [
    {
        "title": "A calm day",
        "detail": "All movements remain within their normal ranges.",
        "events": {},
    },
    {
        "title": "HDFC Bank drops 4.5%",
        "detail": "The move is unusual relative to this stock's recent volatility.",
        "events": {"HDFCBANK.NS": {"move": -4.5, "volume": 2.0}},
    },
    {
        "title": "Tata Steel volume explodes",
        "detail": "The price is stable while volume rises to five times its baseline.",
        "events": {"TATASTEEL.NS": {"move": 0.3, "volume": 5.0}},
    },
    {
        "title": "Reliance breaks its 52-week high",
        "detail": "A 1.5% move takes the stock through its 52-week high.",
        "events": {"RELIANCE.NS": {"move": 1.5, "volume": 1.4, "breakout": True}},
    },
]

replay_step = 0


def _rng(seed):
    """Yield a deterministic pseudo-random sequence."""
    state = seed
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648


def _seeded_walk(symbol):
    """Create deterministic daily closes and volumes."""
    seed = sum(ord(c) * (i + 1) for i, c in enumerate(symbol)) or 7
    noise = _rng(seed)
    price = 200 + (seed % 2800)
    base_volume = 500_000 + (seed % 19_500_000)
    swing = 0.25 + (seed % 14) / 12
    trend = (next(noise) - 0.35) / 6  # a gentle bias that slowly reverses

    closes, volumes = [], []
    for i in range(BASE_DAYS):
        if i % 45 == 0:
            trend = (next(noise) - 0.35) / 6
        shock = (next(noise) + next(noise) + next(noise) - 1.5) / 1.5
        price *= 1 + (trend + swing * shock * 2.5) / 100
        price = max(price, 5)
        closes.append(round(price, 2))
        volumes.append(int(base_volume * (0.55 + next(noise))))
    return closes, volumes


def _steady_climber(start):
    """Create a low-volatility upward series."""
    closes, price = [], start
    for i in range(BASE_DAYS):
        wiggle = 0.4 * (((i * 7) % 13) - 6) / 6
        price *= 1 + (0.05 + wiggle) / 100
        closes.append(round(price, 2))
    return closes


def _trading_dates(count):
    """Weekday dates ending today, so demo charts have a real time axis."""
    dates, cursor = [], date.today()
    while len(dates) < count:
        if cursor.weekday() < 5:
            dates.append(cursor.isoformat())
        cursor -= timedelta(days=1)
    return list(reversed(dates))


def mock_history(symbol):
    """Base history plus one row for each simulated replay step."""
    closes, volumes = _seeded_walk(symbol)
    if symbol == "RELIANCE.NS":
        closes = _steady_climber(2400.0)

    for step_index in range(1, replay_step + 1):
        event = REPLAY_STEPS[step_index]["events"].get(symbol)
        if event and event.get("breakout"):
            closes.append(round(max(closes) * 1.012, 2))
            volumes.append(int(volumes[-1] * event.get("volume", 1)))
        elif event:
            closes.append(round(closes[-1] * (1 + event["move"] / 100), 2))
            volumes.append(int(volumes[-1] * event.get("volume", 1)))
        else:
            drift = 0.1 if step_index % 2 else -0.1
            closes.append(round(closes[-1] * (1 + drift / 100), 2))
            volumes.append(volumes[-1])

    dates = _trading_dates(len(closes))
    as_of = datetime.combine(
        date.fromisoformat(dates[-1]), dt_time(15, 30), ZoneInfo("Asia/Kolkata")
    ).timestamp()
    return {
        "symbol": symbol,
        "closes": closes,
        "volumes": volumes,
        "dates": dates,
        "as_of": as_of,
        "fetched_at": time.time(),
        "source": "simulation",
        "stale": False,
    }
