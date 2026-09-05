# Design decisions

This document records the main implementation choices and their trade-offs.

## Signal model

Delta compares each stock with its own recent history instead of applying one
fixed percentage threshold to every symbol. The scoring inputs are:

- price-move z-score over a 30-day baseline;
- current volume relative to recent median volume;
- crossings of 52-week price extremes; and
- beta and residual movement relative to the NIFTY 50.

The number of inputs is limited so every score can be explained in the
interface and tested independently.

Median volume is used because it is less sensitive than the mean to isolated
high-volume sessions. Price volatility uses the standard deviation of daily
returns.

## Digest state

“Mark all as seen” records the current price and volume for each watched symbol.
Later digest requests compare current values with those snapshots. Snapshots are
stored per user on the server and are updated only by an explicit action.

Price beta is applied only to the current trading day. Market breadth is used
for changes spanning multiple days because a single-day beta comparison cannot
describe the entire interval. Volume and 52-week signals remain visible during
broad market moves.

## Corporate actions and data quality

A split can resemble an extreme price move. Delta first uses recorded split
data, then falls back to ratio-based detection. The fallback requires both a
supported split ratio and a move substantially larger than the stock's normal
volatility. When a split is detected, the stored snapshot is rebased.

Live and daily prices are reconciled in `quotes.reconcile`:

1. Daily closes are used outside market hours.
2. A live quote more than 25% from the last close is treated as conflicting.
3. Accepted live quotes include their age and become delayed after 15 minutes.
4. Cached values are returned as stale if an upstream refresh fails.

Normal mode never falls back to synthetic prices. If no cached value exists,
the API returns a market-data error. Synthetic data is enabled only through
`DELTA_OFFLINE=1`.

During the regular session, cumulative volume is divided by the elapsed session
fraction before comparison with full-day history. The market clock includes the
published NSE holiday calendar for 2026 and accepts additional closure dates
through `NSE_HOLIDAYS`.

Price-band detection is inferred from the daily move and whether the stock
closed at the session high or low. The interface presents it as an estimate.

## Storage and caching

SQLite is the default database for local use. SQLAlchemy also supports Postgres
through `DATABASE_URL`; Postgres is the intended option for concurrent writers.

Historical quotes are cached per symbol in the API process. This avoids
duplicating upstream requests when several users watch the same stock. A shared
cache such as Redis would be needed when running multiple API processes.

The frontend polls every 30 seconds. The update rate and one-way data flow do
not currently require WebSockets.

## User controls and authentication

Each watch item has one of three sensitivity levels: Normal, Only big, or
Muted. These are explicit thresholds rather than learned personalization.

Authentication is intentionally limited to a username header for local and
demonstration use. It is not suitable for production deployment.

## Current scope

Delta does not provide forecasts, trading recommendations, news sentiment,
WebSocket updates, or a second market-data provider.
