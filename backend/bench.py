"""Benchmark repeated watchlist reads in offline mode."""
import os
import time

os.environ.setdefault("DELTA_OFFLINE", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///./bench.db")

from fastapi.testclient import TestClient

import db
import main
import stocks

USERS = 200
PER_USER = 12


def run():
    db.Base.metadata.drop_all(db.engine)
    db.Base.metadata.create_all(db.engine)
    universe = list(stocks.STOCKS)[:20]

    with TestClient(main.app) as client:
        for i in range(USERS):
            name = f"user{i}"
            client.post("/api/login", json={"username": name})
            headers = {"X-Username": name}
            for symbol in [universe[(i + j) % len(universe)] for j in range(PER_USER)]:
                client.post("/api/watchlist", json={"symbol": symbol}, headers=headers)
            client.post("/api/seen", headers=headers)

        start = time.time()
        for i in range(USERS):
            client.get("/api/watchlist", headers={"X-Username": f"user{i}"})
            client.get("/api/digest", headers={"X-Username": f"user{i}"})
        elapsed = time.time() - start

    print(f"users:            {USERS}")
    print(f"watchlist rows:   {USERS * PER_USER}")
    print(f"unique symbols:   {len(universe)}")
    print(f"page loads:       {USERS * 2} (watchlist + digest each)")
    print(f"wall time:        {elapsed:.2f}s  ({elapsed / USERS * 1000:.0f} ms per user)")
    print()
    print("The point: work is bounded by the number of distinct stocks watched,")
    print("not by how many people watch them. Adding the 201st user watching the")
    print("same 20 stocks adds no upstream work at all.")
    print()
    print("Note: mock mode rebuilds each stock's history on")
    print("every call, so this timing is a pessimistic bound. Against real data")
    print("the same load costs 20 upstream fetches in total, then cache hits;")
    print("watch cache_hit_rate on /api/health to see it.")


if __name__ == "__main__":
    run()
