"""Write a snapshot of real market history so a deployed server starts warm.

Run this where Yahoo answers, which in practice means a laptop rather than a
datacentre, then ship the file. The server still prefers live data; this only
gives the existing fallback something to serve when the source refuses us.

    python dump_snapshot.py            # the whole universe
    python dump_snapshot.py 400        # the 400 most popular symbols
"""
import gzip
import json
import os
import sys
import time

import quotes
import stocks

BATCH = 40
PAUSE = 1.0
DEFAULT_PATH = "data/market_snapshot.json.gz"


def dump(symbols, path=DEFAULT_PATH):
    """Fetch every symbol in batches, then write one compressed file."""
    for start in range(0, len(symbols), BATCH):
        quotes.warm_cache(symbols[start:start + BATCH])
        done = min(start + BATCH, len(symbols))
        print(f"  {done}/{len(symbols)} symbols", flush=True)
        time.sleep(PAUSE)
    entries = quotes.snapshot_entries()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with gzip.open(path, "wt") as handle:
        json.dump(entries, handle)
    return entries, os.path.getsize(path)


if __name__ == "__main__":
    if quotes.offline_mode():
        raise SystemExit("Unset DELTA_OFFLINE before writing a real snapshot")
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(stocks.POPULARITY)
    wanted = [quotes.INDEX] + stocks.POPULARITY[:limit]
    print(f"Fetching {len(wanted)} symbols in batches of {BATCH}")
    entries, size = dump(wanted)
    missing = [s for s in wanted if s not in entries]
    print(f"Wrote {len(entries)} symbols to {DEFAULT_PATH} ({size / 1e6:.1f} MB)")
    if missing:
        print(f"{len(missing)} had no usable history, for example {missing[:5]}")
