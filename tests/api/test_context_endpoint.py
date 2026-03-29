# backend/tests/test_context_endpoint.py
# -*- coding: utf-8 -*-
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from fastapi import FastAPI
from fastapi.testclient import TestClient
import sqlite3
from datetime import datetime

from app.api.v1.context import router
from app.core.db import get_db

sqlite3.register_adapter(datetime, lambda dt: dt.isoformat())

def get_test_db():
    url = "sqlite+pysqlite:///:memory:"
    engine = create_engine(url, future=True, connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE symbols (symbol_id INTEGER PRIMARY KEY, symbol TEXT UNIQUE NOT NULL)"))
        conn.execute(text("""CREATE TABLE ohlcv(
            symbol_id INTEGER, candle_width TEXT, timestamp_utc DATETIME(3),
            open_price REAL, high_price REAL, low_price REAL, close_price REAL, volume REAL, provider_id INTEGER)"""))
        conn.execute(text("""CREATE TABLE indicators(
            symbol_id INTEGER, candle_width TEXT, timestamp_utc DATETIME(3),
            vwap REAL, ema8 REAL, ema21 REAL, ema50 REAL, sma20 REAL, sma50 REAL,
            bb_mid REAL, bb_up REAL, bb_dn REAL, bb_percB REAL, bb_bw REAL,
            updated_utc DATETIME(3),
            kc_mid REAL, kc_up REAL, kc_dn REAL
            )"""))
        conn.execute(text("""CREATE TABLE avwap_anchors(
            anchor_id INTEGER PRIMARY KEY,
            symbol_id INTEGER,
            candle_width TEXT,
            anchor_ts_utc DATETIME,
            anchor_type TEXT,
            anchor_label TEXT,
            created_utc DATETIME)"""))
        conn.execute(text("INSERT INTO symbols(symbol_id,symbol) VALUES (1,'AAPL')"))
        conn.execute(text("""
            INSERT INTO ohlcv VALUES (1,'5m','2025-09-17 19:30:00',100,101,99,100.5,1000,1)
        """))
        conn.execute(text("""
            INSERT INTO indicators VALUES (
                1,'5m','2025-09-17 19:30:00',
                100.2,0,100.1,0,0,99.5, 100.0,102.0,98.0,0.5,0.08,'2025-09-17 19:30:00',
                100.0,101.5,98.5
            )
        """))
    with Session(engine) as session:
        yield session

app = FastAPI()
app.include_router(router)
app.dependency_overrides[get_db] = get_test_db

client = TestClient(app)

def test_endpoint_ok():
    r = client.get("/context", params={"symbol":"AAPL","tfs":"5m"})
    assert r.status_code == 200
    assert r.json()["timeframes"][0]["timeframe"] == "5m"

def test_endpoint_404():
    r = client.get("/context", params={"symbol":"AAPL","tfs":"30m"})
    assert r.status_code == 400

def test_endpoint_symbol_not_found():
    r = client.get("/context", params={"symbol":"NOPE","tfs":"5m"})
    assert r.status_code == 404
