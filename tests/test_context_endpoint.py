# backend/tests/test_context_endpoint.py
# -*- coding: utf-8 -*-
import os
import pytest
from sqlalchemy import create_engine, text
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.context import router

@pytest.fixture(autouse=True)
def _db(monkeypatch):
    url = "sqlite+pysqlite:///:memory:"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url, future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE symbols (symbol_id INTEGER PRIMARY KEY, symbol TEXT UNIQUE NOT NULL)"))
        conn.execute(text("""CREATE TABLE ohlcv(
            symbol_id INTEGER, candle_width TEXT, timestamp_utc DATETIME(3),
            open_price REAL, high_price REAL, low_price REAL, close_price REAL, volume REAL, provider_id INTEGER)"""))
        conn.execute(text("""CREATE TABLE indicators(
            symbol_id INTEGER, candle_width TEXT, timestamp_utc DATETIME(3),
            vwap REAL, ema8 REAL, ema21 REAL, ema50 REAL, sma20 REAL, sma50 REAL,
            bb_mid REAL, bb_up REAL, bb_dn REAL, bb_percB REAL, bb_bw REAL,
            updated_utc DATETIME(3))"""))
        conn.execute(text("INSERT INTO symbols(symbol_id,symbol) VALUES (1,'AAPL')"))
        conn.execute(text("""
            INSERT INTO ohlcv VALUES (1,'5m','2025-09-17 19:30:00',100,101,99,100.5,1000,1)
        """))
        conn.execute(text("""
            INSERT INTO indicators VALUES (
                1,'5m','2025-09-17 19:30:00',
                100.2,0,100.1,0,0,99.5, 100.0,102.0,98.0,0.5,0.08,'2025-09-17 19:30:00'
            )
        """))
    yield

def test_endpoint_ok():
    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    r = c.get("/context", params={"symbol":"AAPL","tfs":"5m"})
    assert r.status_code == 200
    assert r.json()["timeframes"][0]["timeframe"] == "5m"

def test_endpoint_404():
    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    r = c.get("/context", params={"symbol":"AAPL","tfs":"30m"})
    assert r.status_code == 404
