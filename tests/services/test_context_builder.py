# backend/tests/test_context_builder.py
# -*- coding: utf-8 -*-
import os
import sys
from datetime import datetime, timedelta
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from services.context_builder import build_context_json, SymbolNotFound

@pytest.fixture
def db_session():
    url = "sqlite+pysqlite:///:memory:"
    engine = create_engine(url, future=True)
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE symbols (
          symbol_id INTEGER PRIMARY KEY AUTOINCREMENT,
          symbol TEXT UNIQUE NOT NULL
        );"""))
        conn.execute(text("""
        CREATE TABLE ohlcv (
          symbol_id INTEGER NOT NULL,
          candle_width TEXT NOT NULL,
          timestamp_utc DATETIME(3) NOT NULL,
          open_price REAL NOT NULL,
          high_price REAL NOT NULL,
          low_price  REAL NOT NULL,
          close_price REAL NOT NULL,
          volume REAL NULL,
          provider_id INTEGER NOT NULL
        );"""))
        conn.execute(text("""
        CREATE TABLE indicators (
          symbol_id INTEGER NOT NULL,
          candle_width TEXT NOT NULL,
          timestamp_utc DATETIME(3) NOT NULL,
          vwap REAL, ema8 REAL, ema21 REAL, ema50 REAL, sma20 REAL, sma50 REAL,
          bb_mid REAL, bb_up REAL, bb_dn REAL, bb_percB REAL, bb_bw REAL,
          kc_mid REAL, kc_up REAL, kc_dn REAL,
          updated_utc DATETIME(3) NOT NULL
        );"""))
        conn.execute(text("""CREATE TABLE avwap_anchors(
            anchor_id INTEGER PRIMARY KEY,
            symbol_id INTEGER,
            candle_width TEXT,
            anchor_ts_utc DATETIME,
            anchor_type TEXT,
            anchor_label TEXT,
            created_utc DATETIME)"""))
        conn.execute(text("INSERT INTO symbols(symbol, symbol_id) VALUES ('AAPL',1)"))

        # Semilla 30m (40 velas con BB y KC en indicators)
        base = datetime(2025, 9, 17, 0, 0, 0)
        for i in range(40):
            ts = base + timedelta(minutes=30*i)
            close = 200 + i * 0.5
            hi, lo = close + 0.4, close - 0.4
            conn.execute(text("""
                INSERT INTO ohlcv VALUES (1,'30m',:ts,:op,:hi,:lo,:cl,1000,1)
            """), dict(ts=ts, op=close-0.2, hi=hi, lo=lo, cl=close))
            conn.execute(text("""
                INSERT INTO indicators VALUES (
                    1,'30m',:ts,:vwap,0,:ema21,0,0,:sma50,
                    :bb_mid,:bb_up,:bb_dn,:percB,:bw,
                    :kc_mid,:kc_up,:kc_dn,
                    :upd
                )
            """), dict(
                ts=ts, vwap=close-0.1, ema21=199+i*0.4, sma50=198+i*0.2,
                bb_mid=close, bb_up=close+1.5, bb_dn=close-1.5, percB=0.5, bw=0.05,
                kc_mid=close, kc_up=close+2.0, kc_dn=close-2.0, # BB mas estrecho que KC (TTM Squeeze)
                upd=ts
            ))

        # 1D minimal (faltan BBs/EMA/KC para probar None)
        for i in range(3):
            ts = datetime(2025, 9, 15+i)
            close = 220 + i
            conn.execute(text("""
                INSERT INTO ohlcv VALUES (1,'1d',:ts,:op,:hi,:lo,:cl,1000,1)
            """), dict(ts=ts, op=close-0.5, hi=close+0.7, lo=close-0.7, cl=close))
            conn.execute(text("""
                INSERT INTO indicators VALUES (
                    1,'1d',:ts,:vwap,0,NULL,0,0,NULL,
                    NULL,NULL,NULL,NULL,NULL,
                    NULL,NULL,NULL,
                    :upd
                )
            """), dict(ts=ts, vwap=close-0.3, upd=ts))
    with Session(engine) as session:
        yield session

def test_build_ok(db_session):
    out = build_context_json(db_session, "AAPL", ["30m","1D"])
    assert out["symbol"] == "AAPL"
    tf30 = next(t for t in out["timeframes"] if t["timeframe"] == "30m")
    
    # Niveles
    assert "levels" in tf30
    assert "bb" in tf30["levels"] and tf30["levels"]["bb"]["up"] is not None
    assert "kc" in tf30["levels"] and tf30["levels"]["kc"]["up"] is not None

    # Distancias
    assert set(tf30["distance"].keys()) == {"to_ema21","to_sma50","to_bb_up","to_bb_dn", "to_kc_up", "to_kc_dn"}
    assert tf30["distance"]["to_kc_up"] is not None

    # Flags
    assert "summary_flags" in tf30
    assert "bb_inside_kc_squeeze" in tf30["summary_flags"]
    # Con la semilla de datos (BB < KC), el flag debe ser True
    assert tf30["summary_flags"]["bb_inside_kc_squeeze"] is True
    assert "squeeze_intensity" in tf30["summary_flags"]
    assert tf30["summary_flags"]["squeeze_intensity"] == 0.75


def test_symbol_not_found(db_session):
    with pytest.raises(SymbolNotFound):
        build_context_json(db_session, "NOPE", ["30m"])

def test_none_levels_on_missing(db_session):
    out = build_context_json(db_session, "AAPL", ["1D"])
    tf1d = out["timeframes"][0]
    assert tf1d["levels"]["ma"]["ema21"] is None
    assert tf1d["levels"]["bb"]["mid"] is None
    assert tf1d["levels"]["kc"]["mid"] is None
