"""Database setup. SQLite by default, Postgres when DATABASE_URL is set."""
import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///delta.db")
# Hosted Postgres often hands out a postgres:// URL, which SQLAlchemy no longer accepts.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    last_seen_at = Column(DateTime, nullable=True)  # set by "mark all as seen"


class WatchItem(Base):
    """A stock on someone's list.

    Sensitivity is how loudly it may interrupt: normal, low (only bigger
    moves), or muted (never).
    """
    __tablename__ = "watch_items"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    symbol = Column(String, nullable=False)
    sensitivity = Column(String, nullable=False, default="normal")
    added_at = Column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "symbol"),)


class Snapshot(Base):
    """What the user last saw for a symbol: price and volume at that moment."""
    __tablename__ = "snapshots"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    symbol = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    taken_at = Column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "symbol"),)


def init_db():
    Base.metadata.create_all(engine)
