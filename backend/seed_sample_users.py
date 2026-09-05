"""Seed sample watchlists while keeping every displayed market price real.

Run this only for the hackathon review environment. The generated accounts are
named ``sample1`` through ``sample36`` so they cannot be mistaken for real
customers. The
``groww_judge`` account is given a watchlist and a snapshot from the previous
actual trading close, allowing the return-visit digest to be reviewed
immediately without altering quote data.
"""
import random
from datetime import datetime, time, timezone
from statistics import median
from zoneinfo import ZoneInfo

import db
import quotes
import signals
import stocks


SAMPLE_USER_COUNT = 36
COMMUNITY_POOL_SIZE = 60
SHOWCASE_POOL_SIZE = 48
SHOWCASE_SIZE = 12
SAMPLE_PREFIX = "sample"
SHOWCASE_USER = "groww_judge"


def _replace_user(session, username):
    user = session.query(db.User).filter_by(username=username).first()
    if user is None:
        user = db.User(username=username)
        session.add(user)
        session.flush()
    session.query(db.Snapshot).filter_by(user_id=user.id).delete()
    session.query(db.WatchItem).filter_by(user_id=user.id).delete()
    user.last_seen_at = None
    return user


def _remove_legacy_sample_users(session):
    """Remove accounts created by the older sample_### naming scheme."""
    legacy = [
        user for user in session.query(db.User).all()
        if user.username.startswith("sample_")
    ]
    for user in legacy:
        session.query(db.Snapshot).filter_by(user_id=user.id).delete()
        session.query(db.WatchItem).filter_by(user_id=user.id).delete()
        session.delete(user)


def _sample_portfolio(rng, universe, size):
    """Choose unique symbols with a gentle bias toward familiar companies."""
    weights = [1 / ((index + 4) ** 0.72) for index in range(len(universe))]
    chosen = []
    while len(chosen) < size:
        symbol = rng.choices(universe, weights=weights, k=1)[0]
        if symbol not in chosen:
            chosen.append(symbol)
    return chosen


def _real_move_candidates():
    """Rank liquid stocks by their actual latest close-to-close significance."""
    universe = stocks.POPULARITY[:SHOWCASE_POOL_SIZE]
    quotes.warm_cache(universe)
    ranked = []
    for symbol in universe:
        try:
            history = quotes.get_history(symbol)
            closes = history["closes"]
            volumes = history["volumes"]
            dates = history["dates"]
            if len(closes) < 35 or len(volumes) != len(closes):
                continue
            moves = signals.daily_moves(closes[:-1])[-60:]
            spread = signals.typical_spread(moves)
            turnover = median(
                price * shares for price, shares in zip(closes[-30:], volumes[-30:])
            )
            if not spread or signals.too_thin_to_trust(turnover):
                continue
            change = (closes[-1] - closes[-2]) / closes[-2] * 100
            volume_ratio = signals.volume_ratio(volumes[-1], volumes[:-1][-30:]) or 0
            landmark = signals.crossed_52w(closes[-1], closes[:-1])
            significance = abs(change / spread) + max(0, volume_ratio - 1) * 0.4
            if landmark:
                significance += 2
            ranked.append({
                "symbol": symbol,
                "history": history,
                "change": change,
                "significance": significance,
                "baseline_price": closes[-2],
                "baseline_volume": volumes[-2],
                "baseline_date": dates[-2],
            })
        except quotes.MarketDataUnavailable:
            continue
    return sorted(ranked, key=lambda item: item["significance"], reverse=True)


def seed():
    if quotes.offline_mode():
        raise RuntimeError("Unset DELTA_OFFLINE before seeding real-market review data")

    db.init_db()
    candidates = _real_move_candidates()
    if len(candidates) < SHOWCASE_SIZE:
        raise RuntimeError("Not enough live market histories were available to seed")

    session = db.SessionLocal()
    try:
        rng = random.Random(2026)
        community = stocks.POPULARITY[:COMMUNITY_POOL_SIZE]
        _remove_legacy_sample_users(session)
        for number in range(1, SAMPLE_USER_COUNT + 1):
            user = _replace_user(session, f"{SAMPLE_PREFIX}{number}")
            for symbol in _sample_portfolio(rng, community, rng.randint(7, 14)):
                session.add(db.WatchItem(user_id=user.id, symbol=symbol))

        reviewer = _replace_user(session, SHOWCASE_USER)
        seen_times = []
        for item in candidates[:SHOWCASE_SIZE]:
            session.add(db.WatchItem(user_id=reviewer.id, symbol=item["symbol"]))
            seen_at = datetime.combine(
                datetime.fromisoformat(item["baseline_date"]).date(),
                time(15, 30),
                ZoneInfo("Asia/Kolkata"),
            ).astimezone(timezone.utc)
            seen_times.append(seen_at)
            session.add(db.Snapshot(
                user_id=reviewer.id,
                symbol=item["symbol"],
                price=item["baseline_price"],
                volume=item["baseline_volume"],
                taken_at=seen_at,
            ))
        reviewer.last_seen_at = min(seen_times)
        session.commit()
    finally:
        session.close()

    print(f"Seeded {SAMPLE_USER_COUNT} sample community accounts.")
    print(f"Sign in as {SHOWCASE_USER} to review real close-to-close changes:")
    for item in candidates[:SHOWCASE_SIZE]:
        print(
            f"  {item['symbol']:<18} {item['change']:+6.2f}%  "
            f"significance {item['significance']:.2f}"
        )


if __name__ == "__main__":
    seed()
