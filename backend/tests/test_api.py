"""End-to-end API tests. Mock mode keeps them deterministic and offline."""
import os
import sys
from pathlib import Path

os.environ["DELTA_OFFLINE"] = "1"
os.environ["DATABASE_URL"] = "sqlite:////tmp/delta_test.db"
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

import db
import main
import mock_data
import quotes
import signals

WATCHED = ["HDFCBANK.NS", "TATASTEEL.NS", "RELIANCE.NS", "INFY.NS"]


def quotes_reset():
    for key in quotes.stats:
        quotes.stats[key] = 0


@pytest.fixture()
def client():
    # drop/create rather than deleting the file: open pooled connections would
    # still point at the deleted one
    db.Base.metadata.drop_all(db.engine)
    db.Base.metadata.create_all(db.engine)
    mock_data.replay_step = 0
    quotes_reset()
    with TestClient(main.app) as c:
        yield c


def login(client, name):
    client.post("/api/login", json={"username": name})
    return {"X-Username": name}


def add_all(client, headers, symbols=WATCHED):
    for s in symbols:
        client.post("/api/watchlist", json={"symbol": s}, headers=headers)


def advance(client, days):
    mock_data.replay_step = min(
        mock_data.replay_step + days, len(mock_data.REPLAY_STEPS) - 1
    )


def test_login_creates_user_and_is_case_insensitive(client):
    a = client.post("/api/login", json={"username": "Saachi"}).json()
    b = client.post("/api/login", json={"username": "SAACHI"}).json()
    assert a["id"] == b["id"] == 1


def test_auth_is_required(client):
    assert client.get("/api/watchlist").status_code == 401
    assert client.get("/api/watchlist", headers={"X-Username": "ghost"}).status_code == 401


def test_add_remove_and_duplicate(client):
    h = login(client, "saachi")
    assert client.post("/api/watchlist", json={"symbol": "infy.ns"}, headers=h).status_code == 200
    assert client.post("/api/watchlist", json={"symbol": "INFY.NS"}, headers=h).status_code == 409
    assert client.post("/api/watchlist", json={"symbol": "NOPE.NS"}, headers=h).status_code == 404
    assert client.delete("/api/watchlist/INFY.NS", headers=h).status_code == 200
    assert client.get("/api/watchlist", headers=h).json()["rows"] == []


def test_digest_is_empty_before_and_after_marking_seen(client):
    h = login(client, "saachi")
    add_all(client, h)
    assert client.get("/api/digest", headers=h).json()["first_visit"] is True
    client.post("/api/seen", headers=h)
    body = client.get("/api/digest", headers=h).json()
    assert body["first_visit"] is False
    assert body["notable"] == []          # nothing has happened yet
    assert body["quiet_count"] == len(WATCHED)


def test_scripted_days_surface_exactly_the_right_stocks(client):
    h = login(client, "saachi")
    add_all(client, h)
    client.post("/api/seen", headers=h)
    advance(client, 3)

    body = client.get("/api/digest", headers=h).json()
    surfaced = {r["symbol"]: r["reasons"] for r in body["notable"]}
    assert set(surfaced) == {"HDFCBANK.NS", "TATASTEEL.NS", "RELIANCE.NS"}
    assert "INFY.NS" not in surfaced           # the calm stock stays quiet
    assert any("unusual" in r or "down" in r for r in surfaced["HDFCBANK.NS"])
    assert any("volume" in r for r in surfaced["TATASTEEL.NS"])
    assert any("52-week" in r for r in surfaced["RELIANCE.NS"])
    scores = [r["score"] for r in body["notable"]]
    assert scores == sorted(scores, reverse=True)  # most unusual first


def test_muting_a_stock_keeps_it_out_of_the_digest(client):
    h = login(client, "saachi")
    add_all(client, h)
    client.post("/api/seen", headers=h)
    client.patch("/api/watchlist/HDFCBANK.NS", json={"level": "muted"}, headers=h)
    advance(client, 3)

    body = client.get("/api/digest", headers=h).json()
    assert "HDFCBANK.NS" not in {r["symbol"] for r in body["notable"]}
    assert body["muted_count"] == 1


def test_low_sensitivity_raises_the_bar(client):
    h = login(client, "saachi")
    add_all(client, h)
    client.post("/api/seen", headers=h)
    client.patch("/api/watchlist/TATASTEEL.NS", json={"level": "low"}, headers=h)
    advance(client, 3)

    body = client.get("/api/digest", headers=h).json()
    # a 5x volume spike clears the normal bar (3x) but not the "low" bar (5x+)
    assert "TATASTEEL.NS" not in {r["symbol"] for r in body["notable"]}


def test_sensitivity_rejects_junk_and_unknown_symbols(client):
    h = login(client, "saachi")
    add_all(client, h, ["INFY.NS"])
    assert client.patch("/api/watchlist/INFY.NS", json={"level": "loud"}, headers=h).status_code == 422
    assert client.patch("/api/watchlist/TCS.NS", json={"level": "muted"}, headers=h).status_code == 404


def test_users_cannot_see_each_other(client):
    a = login(client, "saachi")
    b = login(client, "aarya")
    add_all(client, a, ["INFY.NS", "TCS.NS"])
    add_all(client, b, ["ITC.NS"])
    client.post("/api/seen", headers=a)

    assert {r["symbol"] for r in client.get("/api/watchlist", headers=a).json()["rows"]} == {"INFY.NS", "TCS.NS"}
    assert {r["symbol"] for r in client.get("/api/watchlist", headers=b).json()["rows"]} == {"ITC.NS"}
    assert client.get("/api/digest", headers=b).json()["first_visit"] is True  # a's snapshot is a's alone


def test_seen_survives_an_empty_watchlist(client):
    h = login(client, "saachi")
    client.post("/api/seen", headers=h)
    assert client.get("/api/digest", headers=h).json()["first_visit"] is False


def test_every_row_reports_its_age_and_basis(client):
    h = login(client, "saachi")
    add_all(client, h, ["INFY.NS"])
    row = client.get("/api/watchlist", headers=h).json()["rows"][0]
    assert row["as_of"] and row["basis"] in ("live", "close")
    assert len(row["spark"]) == main.SPARK_DAYS


def test_a_broad_market_day_collapses_followers_but_keeps_real_signals(client):
    h = login(client, "saachi")
    add_all(client, h)
    client.post("/api/seen", headers=h)
    advance(client, 3)

    # Market breadth compares normalized rather than absolute movement.
    rows = {r["symbol"]: r for r in client.get("/api/watchlist", headers=h).json()["rows"]}
    session = db.SessionLocal()
    for snap in session.query(db.Snapshot).all():
        spread = rows[snap.symbol]["spread"] or 1.0
        sigmas = 6.0 if snap.symbol == "INFY.NS" else 2.5  # INFY is the outlier
        snap.price = rows[snap.symbol]["price"] / (1 - sigmas * spread / 100)
    session.commit()
    session.close()

    body = client.get("/api/digest", headers=h).json()
    surfaced = {r["symbol"] for r in body["notable"]}

    assert body["market"] is not None
    assert body["market"]["direction"] == "down"
    assert body["followed_market"] >= 1          # some cards became the headline
    assert "INFY.NS" in surfaced                 # fell far harder than the rest
    assert "TATASTEEL.NS" in surfaced            # volume spike is not a price move


def test_a_thinly_traded_stock_never_earns_a_card(client):
    h = login(client, "saachi")
    add_all(client, h, ["INFY.NS"])
    client.post("/api/seen", headers=h)

    # Create a normally notable difference from the snapshot.
    session = db.SessionLocal()
    snap = session.query(db.Snapshot).filter_by(symbol="INFY.NS").first()
    snap.price = snap.price * 1.25
    session.commit()
    session.close()

    # ...but the stock barely trades, so it is noise rather than signal
    real = signals.typical_turnover
    signals.typical_turnover = lambda closes, volumes: 1_000.0
    try:
        body = client.get("/api/digest", headers=h).json()
    finally:
        signals.typical_turnover = real

    assert body["notable"] == []
    assert body["thin_count"] == 1


def test_unexplained_extreme_gap_is_suppressed(client):
    h = login(client, "saachi")
    add_all(client, h, ["INFY.NS"])
    client.post("/api/seen", headers=h)

    # half the price overnight, matching no split ratio: bad data or an
    # unrecorded action. either way, do not claim a 50% crash
    session = db.SessionLocal()
    snap = session.query(db.Snapshot).filter_by(symbol="INFY.NS").first()
    snap.price = snap.price / 0.46
    session.commit()
    session.close()

    body = client.get("/api/digest", headers=h).json()
    assert body["notable"] == []
    assert body["unexplained"] == 1


def test_the_digest_is_capped_so_it_cannot_become_a_wall(client):
    h = login(client, "saachi")
    symbols = ["HDFCBANK.NS", "TATASTEEL.NS", "RELIANCE.NS", "INFY.NS",
               "ITC.NS", "SBIN.NS", "TCS.NS", "WIPRO.NS"]
    add_all(client, h, symbols)
    client.post("/api/seen", headers=h)

    rows = {r["symbol"]: r for r in client.get("/api/watchlist", headers=h).json()["rows"]}
    session = db.SessionLocal()
    for snap in session.query(db.Snapshot).all():
        spread = rows[snap.symbol]["spread"] or 1.0
        # every stock moves a different number of sigmas, so none of this is
        # a market-wide day: eight separate, genuinely unusual moves
        sigmas = 3 + symbols.index(snap.symbol) * 2
        snap.price = rows[snap.symbol]["price"] / (1 + sigmas * spread / 100)
    session.commit()
    session.close()

    body = client.get("/api/digest", headers=h).json()
    assert len(body["notable"]) <= 5
    assert body["also_moved"] >= 1
