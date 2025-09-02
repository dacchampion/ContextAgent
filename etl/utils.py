import pandas as pd
from sqlalchemy import text
from zoneinfo import ZoneInfo

from app.core.db import SessionLocal

def get_session():
    return SessionLocal()

def get_symbol_id(session, symbol: str) -> int:
    row = session.execute(text(
        "SELECT symbol_id FROM symbols WHERE symbol=:s"
    ), {"s": symbol}).fetchone()
    if row:
        return row[0]
    session.execute(text(
        "INSERT INTO symbols(symbol, asset_class) VALUES (:s, 'equity')"
    ), {"s": symbol})
    session.commit()
    row = session.execute(text(
        "SELECT symbol_id FROM symbols WHERE symbol=:s"
    ), {"s": symbol}).fetchone()
    return row[0]

def get_provider_id(session, name: str, base_url: str = None) -> int:
    row = session.execute(text(
        "SELECT provider_id FROM providers WHERE name=:n"
    ), {"n": name}).fetchone()
    if row:
        return row[0]
    session.execute(text(
        "INSERT INTO providers(name, base_url) VALUES (:n, :u)"
    ), {"n": name, "u": base_url})
    session.commit()
    row = session.execute(text(
        "SELECT provider_id FROM providers WHERE name=:n"
    ), {"n": name}).fetchone()
    return row[0]

def normalize_df(df: pd.DataFrame, symbol: str, candle_width: str, source: str) -> pd.DataFrame:
    d = df.copy()

    # 0) Aplanar columnas si vienen en MultiIndex (yfinance puede devolver ('Open','AAPL'), ('close_price','AAPL'), etc.)
    if isinstance(d.columns, pd.MultiIndex):
        wanted = {
            "open", "open price", "open_price",
            "high", "high price", "high_price",
            "low",  "low price",  "low_price",
            "close","close price","close_price",
            "volume"
        }
        flat_cols = []
        for col in d.columns:
            if isinstance(col, tuple):
                parts = [str(x).strip().lower() for x in col if x not in (None, "", "nan")]
                # elige la parte que parezca OHLCV; si no hay, toma la primera
                preferred = next((p for p in parts if p in wanted), (parts[0] if parts else ""))
                flat_cols.append(preferred)
            else:
                flat_cols.append(str(col).strip().lower())
        d.columns = flat_cols
    else:
        # columnas simples: pásalas a minúsculas
        d.columns = [str(c).strip().lower() for c in d.columns]

    # 1) Asegurar columna de tiempo -> 'timestamp_utc'
    if "timestamp_utc" not in d.columns:
        d = d.reset_index()
        d.columns = [str(c).strip().lower() for c in d.columns]
        for cand in ("timestamp_utc", "timestamp", "datetime", "date", "index"):
            if cand in d.columns:
                d = d.rename(columns={cand: "timestamp_utc"})
                break

    if "timestamp_utc" not in d.columns:
        # Devuelve esquema vacío para no romper aguas arriba
        return pd.DataFrame(columns=[
            "symbol","candle_width","timestamp_utc",
            "open_price","high_price","low_price","close_price","volume","source"
        ])

    d["timestamp_utc"] = pd.to_datetime(d["timestamp_utc"], utc=True, errors="coerce")

    # === DAILY (1d): fijar a medianoche UTC del mismo "trade date" ===
    if candle_width == "1d":
        ts = pd.to_datetime(d["timestamp_utc"], errors="coerce")      # sin utc=True
        # Normaliza a la fecha (descarta cualquier hora que pueda aparecer)
        trade_date = ts.dt.date
        d["timestamp_utc"] = pd.to_datetime(trade_date).dt.tz_localize("UTC")
    else:
        # intradía
        d["timestamp_utc"] = pd.to_datetime(d["timestamp_utc"], utc=True, errors="coerce")

    # 2) Renombrar OHLCV a tu esquema
    rename_ohlc = {
        "open": "open_price", "open price": "open_price", "open_price": "open_price",
        "high": "high_price", "high price": "high_price", "high_price": "high_price",
        "low":  "low_price",  "low price":  "low_price",  "low_price":  "low_price",
        "close":"close_price","close price":"close_price","close_price":"close_price",
        "volume":"volume",
    }
    d = d.rename(columns={k: v for k, v in rename_ohlc.items() if k in d.columns})

    # 3) Asegurar columnas esperadas
    for c in ["open_price","high_price","low_price","close_price","volume"]:
        if c not in d.columns:
            d[c] = pd.NA

    # 4) Tipos numéricos
    for c in ["open_price","high_price","low_price","close_price","volume"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")

    # 5) Limpiar y ordenar
    d = (
        d.dropna(subset=["timestamp_utc","open_price","high_price","low_price","close_price"])
         .sort_values("timestamp_utc")
    )

    # 6) Metadatos
    d["symbol"] = symbol
    d["candle_width"] = candle_width
    d["source"] = source

    return d[[
        "symbol","candle_width","timestamp_utc",
        "open_price","high_price","low_price","close_price","volume","source"
    ]]

def upsert_ohlcv(session, df: pd.DataFrame, symbol_id: int, provider_id: int):
    if df.empty:
        return 0
    records = []
    for r in df.to_dict(orient="records"):
        records.append({
            "symbol_id": symbol_id,
            "candle_width": r["candle_width"],
            "timestamp_utc": pd.to_datetime(r["timestamp_utc"]).to_pydatetime().replace(tzinfo=None),
            "open_price":  r["open_price"],
            "high_price":  r["high_price"],
            "low_price":   r["low_price"],
            "close_price": r["close_price"],
            "volume":      r.get("volume"),
            "provider_id": provider_id,
        })
    sql = text("""
        INSERT INTO ohlcv
        (symbol_id, candle_width, timestamp_utc, open_price, high_price, low_price, close_price, volume, provider_id)
        VALUES (:symbol_id, :candle_width, :timestamp_utc, :open_price, :high_price, :low_price, :close_price, :volume, :provider_id)
        ON DUPLICATE KEY UPDATE
          open_price=VALUES(open_price),
          high_price=VALUES(high_price),
          low_price=VALUES(low_price),
          close_price=VALUES(close_price),
          volume=VALUES(volume),
          provider_id=VALUES(provider_id)
    """)
    session.execute(sql, records)
    session.commit()
    return len(records)

def update_sync_meta(session, symbol_id: int, candle_width: str, backfill_utc=None, realtime_utc=None):
    sql = text("""
      INSERT INTO sync_meta(symbol_id, candle_width, last_backfill_utc, last_realtime_utc, updated_utc)
      VALUES (:sid, :cw, :lb, :lr, UTC_TIMESTAMP(3))
      ON DUPLICATE KEY UPDATE
        last_backfill_utc = COALESCE(VALUES(last_backfill_utc), last_backfill_utc),
        last_realtime_utc = COALESCE(VALUES(last_realtime_utc), last_realtime_utc),
        updated_utc = UTC_TIMESTAMP(3)
    """)
    session.execute(sql, {"sid": symbol_id, "cw": candle_width, "lb": backfill_utc, "lr": realtime_utc})
    session.commit()
