# Delta

A stock watchlist that tells you what changed while you were away, and what is
worth your attention now.

Most watchlists use fixed price thresholds. Delta instead compares each stock
with its own recent trading history so that alerts account for the stock's
normal volatility.

Delta scores every stock against its own history instead.

## What counts as a meaningful change

Four signals, each measured against the stock itself:

1. **An unusual price move.** Today's move divided by how much this stock
   normally moves (a z-score). Not a fixed percentage.
2. **A volume spike.** Volume against the median of recent days, which limits
   the effect of isolated high-volume sessions.
3. **A 52-week landmark.** A price crossing a line it has not crossed all year,
   even if the move itself is small.
4. **The market, as context.** Beta against the NIFTY 50 separates broad-market
   movement from stock-specific movement.

These combine into an **attention score** from 0 to 100, shown as Quiet, Notable
or Alert. It is an activity score, not a company rating or trading signal.

## What "since you last checked" means

Pressing **Mark all as seen** stores a snapshot of every price and volume at
that moment, against your account on the server. When you return, the digest
compares today against that snapshot, so it shows what *you* have not seen
rather than what merely happened today.

The snapshot lives on the server so it is shared across devices. Updating it is
an explicit action rather than a side effect of rendering the page.

## Screens

- **Watchlist.** Your stocks, ranked by attention score, each with a 30-day
  sparkline, its typical daily range, and the reasons it stands out.
- **Discover.** All 2,288 NSE stocks, paged in as you scroll, ordered by
  Trending, Biggest movers, Unusual volume or All.
- **Stock detail.** A price chart with 1M/3M/6M/1Y ranges, returns, a peer
  comparison inside its sector, and a scorecard that breaks the attention score
  into its parts, each in one sentence.
- **How it works.** The scoring explained inside the product.

## Running it

### Docker Compose

With Docker Desktop running, build and start the complete application:

```bash
docker compose up --build
```

Open http://localhost:5173. The frontend is served by Nginx, `/api` requests
are proxied to FastAPI, and SQLite data persists in the `delta-data` Docker
volume.

To populate the persistent volume with the sample watchlists and the
`groww_judge` review account, run this once while the stack is up:

```bash
docker compose --profile tools run --rm seed
```

Useful overrides:

```bash
DELTA_PORT=8080 docker compose up --build       # frontend on port 8080
DELTA_OFFLINE=1 docker compose up --build       # synthetic offline data
docker compose down                             # stop containers, keep data
docker compose down --volumes                   # also remove persisted data
```

### Local development

Backend, needs Python 3.11 or newer:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --port 8010
```

Frontend, needs Node 18 or newer, in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and pick a username. There is no password: the
username identifies you so your watchlist can live on the server.

### Seeded review account

To populate the prototype with clearly named sample accounts and immediately
exercise the return-visit flow using real market history:

```bash
cd backend
.venv/bin/python seed_sample_users.py
```

Then sign in as `groww_judge`, or as any of `sample1` through `sample36`, which
also exercise watch-count ranking. Every seeded account gets a baseline, so the
return-visit digest has something real to show immediately. It gives the review account a watchlist selected
from the latest real NSE closes and stores the close from `BASELINE_DAYS`
trading days earlier, five by default, as its baseline. That is a realistic gap
between visits and gives the digest a real change to describe. It never changes
or invents a quote. Re-running it replaces only
these explicitly named sample accounts.

### Offline mode

```bash
cd backend
DELTA_OFFLINE=1 .venv/bin/uvicorn main:app --port 8010
```

Serves deterministic synthetic data instead of calling Yahoo, so the app still
runs with no network. This is never presented as live market information.

## Tests

```bash
cd backend
.venv/bin/python -m pytest tests/
```

121 tests. They cover the signal maths (the same move scoring differently on a
calm and a volatile stock, thin history producing no false alarms, divide by
zero guards), the API end to end (auth, duplicates, cross-user isolation,
muting, the scripted week surfacing exactly the right stocks in the right
order), split detection, the market clock, quote failures, timestamp handling,
and the market maths.

## Stale, delayed and conflicting data

Two sources are read per stock: a year of daily closes, which every signal is
measured against, and during market hours the live intraday price. They can
disagree, so the rules live in one function, `quotes.reconcile`:

1. Market closed means the daily close wins, and every card says "last close".
2. A live price more than 25% away from the last close is bad data, not news.
   The close is kept and the conflict is shown on the card.
3. Otherwise the newer value wins, and its age is always displayed.
4. A quote older than 15 minutes is labelled delayed.
5. If a fetch fails, the last known value is served and visibly marked. With no
   cached value, the API reports that market data is unavailable; synthetic
   prices are never substituted in normal mode.

Intraday cumulative volume is normalized by the elapsed share of the regular
session before it is compared with historical full-day volume. Market status
includes the published 2026 NSE equity holidays. Extra closure dates can be
provided through the comma-separated `NSE_HOLIDAYS` environment variable.

For deployments on a different origin, set `CORS_ORIGINS` to a comma-separated
list of allowed frontend origins. It defaults to `http://localhost:5173`.

A share split is handled separately, in `corporate.py`. A stock that quarters
overnight looks like a 75% crash to a naive diff. Delta checks whether the
change matches a real split ratio and is far outside that stock's own
volatility, and if so re-bases the stored snapshot instead of raising an alarm.

## Scale

Cost grows with the number of distinct stocks being watched, not with the
number of users. Quotes are cached per symbol, so a hundred people watching
Reliance cause one fetch, and each page of Discover costs one batched request
rather than one per stock.

The health endpoint and benchmark expose the relevant cache metrics:

```bash
curl localhost:8010/api/health          # unique symbols, fetches, cache hit rate
DELTA_OFFLINE=1 python bench.py         # 200 users over 2,400 watchlist rows
```

The next steps, with the trigger for each: concurrent writers means Postgres
(one environment variable, no code change); a second API server means Redis for
the shared quote cache; a much larger stock universe means sharding the fetches
by symbol.

## Built with

Python, FastAPI and SQLAlchemy on the backend, with SQLite by default and
Postgres available through `DATABASE_URL`. React and Vite on the frontend, plain
CSS, no UI framework and no charting library. Market data from Yahoo Finance
through yfinance.

See DECISIONS.md for why each of those was chosen, and what was rejected.
