"""Market-relative movement and watchlist breadth calculations."""
from statistics import mean

MIN_PAIRS = 30
RESIDUAL_TOLERANCE = 1.0
MIN_STOCKS = 4
MIN_SHARE_PERCENT = 60
MIN_MEAN_Z = 1.5


def beta(stock_moves, index_moves):
    """How much this stock moves for each 1% the index moves, or None."""
    if not stock_moves or not index_moves:
        return None
    # Series must already be aligned by date.
    if len(stock_moves) != len(index_moves):
        return None
    pairs = [(s, i) for s, i in zip(stock_moves, index_moves)
             if s is not None and i is not None]
    if len(pairs) < MIN_PAIRS:
        return None
    stock_avg = mean(s for s, _ in pairs)
    index_avg = mean(i for _, i in pairs)
    covariance = sum((s - stock_avg) * (i - index_avg) for s, i in pairs)
    index_variance = sum((i - index_avg) ** 2 for _, i in pairs)
    if index_variance == 0:  # a flat index explains nothing
        return None
    # The common covariance/variance normalization factor cancels.
    return covariance / index_variance


def residual_move(stock_move, index_move, stock_beta):
    """The part of today's move the market does not explain."""
    if stock_beta is None or stock_move is None or index_move is None:
        return stock_move
    return stock_move - stock_beta * index_move


def explains_the_move(stock_move, index_move, stock_beta, residual_spread):
    """True when today's move is essentially just the market carrying this stock."""
    if not residual_spread:  # None or 0: no yardstick, so we don't excuse anything
        return False
    if stock_move is None or index_move is None:
        return False
    residual = residual_move(stock_move, index_move, stock_beta)
    if residual is None:
        return False
    same_direction = stock_move * index_move > 0
    return abs(residual) < RESIDUAL_TOLERANCE * abs(residual_spread) and same_direction


def breadth(z_scores):
    """Detect a market-wide day across one watchlist, or None if it isn't one."""
    if not z_scores:
        return None
    values = [z for z in z_scores if z is not None]
    total = len(values)
    if total < MIN_STOCKS:
        return None
    ups = [z for z in values if z > 0]
    downs = [z for z in values if z < 0]
    majority = ups if len(ups) >= len(downs) else downs
    # Use integer arithmetic at the percentage boundary.
    if len(majority) * 100 < total * MIN_SHARE_PERCENT:
        return None
    mean_z = mean(majority)
    if abs(mean_z) < MIN_MEAN_Z:
        return None
    return {
        "direction": "up" if mean_z > 0 else "down",
        "share": round(len(majority) / total, 2),
        "count": len(majority),
        "total": total,
        "mean_z": round(mean_z, 2),
    }


def outliers(scored, mean_z, min_gap=1.5):
    """The stocks that did NOT just follow the market, in input order."""
    if not scored or mean_z is None:
        return []
    return [key for key, z in scored
            if z is not None and abs(z - mean_z) >= min_gap]
