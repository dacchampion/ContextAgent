# backend/etl/backfill.py
import argparse
import os
import sys
import logging
from datetime import timedelta
import pandas as pd
import pytz
import yfinance as yf
from sqlalchemy import text
from etl.utils import (
    get_session, get_symbol_id, get_provider_id,
    normalize_df, upsert_ohlcv, update_sync_meta
)

# --- Logger dedicado, sin depender de basicConfig ---
logger = logging.getLogger("backfill")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
# Nivel por env var (o INFO por defecto)
logger.setLevel(logging.DEBUG if os.getenv("BACKFILL_LOG") else logging.INFO)

def clamp_range_inclusive(df, start=None, end=None, market_tz="US/Eastern"):
    """Filtra por [start, end] inclusivo en la tz del mercado y vuelve a UTC."""
    if df is None or df.empty or (start is None and end is None):
        return df
    tz = pytz.timezone(market_tz)
    d = df.copy()
    d["ts_local"] = d["timestamp_utc"].dt.tz_convert(tz)
    if start:
        start_local = pd.Timestamp(start).tz_localize(tz)
        d = d[d["ts_local"] >= start_local]
    if end:
        end_local = pd.Timestamp(end).tz_localize(tz)
        d = d[d["ts_local"] <= end_local]   # inclusivo al final
    return d.drop(columns=["ts_local"])

def clamp_daily_by_date(df, start=None, end=None):
    if df.empty or (not start and not end):
        return df
    d = df.copy()
    d["trade_date"] = d["timestamp_utc"].dt.date  # la misma fecha de mercado
    if start:
        d = d[d["trade_date"] >= pd.to_datetime(start).date()]
    if end:
        d = d[d["trade_date"] <= pd.to_datetime(end).date()]
    return d.drop(columns=["trade_date"])

def fetch_yf(symbol: str, candle_width: str, start: str = None, end: str = None) -> pd.DataFrame:
    yf_map = {"1d": "1d", "30m": "30m", "5m": "5m"}
    if candle_width not in yf_map:
        raise ValueError("candle_width debe ser uno de: 1d, 30m, 5m")

    if candle_width in ("5m", "30m"):
        # Intradía: usa period (más confiable) y cap a 59d
        if start and end:
            start_dt = pd.to_datetime(start)
            end_dt = pd.to_datetime(end)
            days = max(1, (end_dt - start_dt).days)
        else:
            days = 30
        days = min(days, 59)
        period = f"{days}d"
        logger.info(f"Descargando {symbol} intradía {candle_width} con period={period} (yfinance)")
        df = yf.download(symbol, period=period, interval=yf_map[candle_width], progress=False, auto_adjust=True)
    else:
        adj_end = None
        if end:
            adj_end = (pd.to_datetime(end) + timedelta(days=1)).strftime("%Y-%m-%d")
        logger.info(f"Descargando {symbol} diario 1d start={start} end={end} (ajustado end={adj_end}) (yfinance)")
        df = yf.download(symbol,
                         start=start,
                         end=adj_end,             # <— aquí el +1 día
                         interval=yf_map[candle_width],
                         progress=False,
                         auto_adjust=True)

    if df is None or df.empty:
        logger.warning("yfinance devolvió DataFrame vacío.")
        return pd.DataFrame()

    df = df.rename(columns={
        "Open": "open_price",
        "High": "high_price",
        "Low": "low_price",
        "Close": "close_price",
        "Volume": "volume",
    })
    return df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--candle_width", default="5m", choices=["1d", "30m", "5m"])
    ap.add_argument("--start", help="YYYY-MM-DD")
    ap.add_argument("--end", help="YYYY-MM-DD")
    args = ap.parse_args()

    logger.info(f"[backfill] start | symbol={args.symbol} candle_width={args.candle_width} start={args.start} end={args.end}")

    df_raw = fetch_yf(args.symbol, args.candle_width, args.start, args.end)
    if df_raw is None or df_raw.empty:
        logger.error("Sin datos de yfinance. Para intradía (>60d), usa diario 1d para histórico y recent_update (Twelve Data) para el tramo reciente.")
        return

    df = normalize_df(df_raw, args.symbol, args.candle_width, source="yfinance")
    if args.candle_width == "1d":
        df = clamp_daily_by_date(df, start=args.start, end=args.end)
    else:
        df = clamp_range_inclusive(df, start=args.start, end=args.end, market_tz="US/Eastern")
    if df.empty:
        logger.error(f"DataFrame normalizado vacío. df_raw.columns={list(df_raw.columns)} shape={df_raw.shape}")
        return

    with get_session() as session:
        symbol_id = get_symbol_id(session, args.symbol)
        provider_id = get_provider_id(session, "yfinance", "https://finance.yahoo.com")
        inserted = upsert_ohlcv(session, df, symbol_id, provider_id)
        last_ts = df["timestamp_utc"].max().to_pydatetime().replace(tzinfo=None)

        update_sync_meta(session, symbol_id, args.candle_width, backfill_utc=last_ts)
        session.execute(text("""
            INSERT INTO job_runs(job_name, symbol_id, candle_width, run_status, rows_affected, log_message)
            VALUES ('backfill_yf', :sid, :cw, 'success', :rows, :msg)
        """), {"sid": symbol_id, "cw": args.candle_width, "rows": int(inserted), "msg": "ok"})
        session.commit()

    logger.info(f"[backfill] done | rows={len(df)} range={df['timestamp_utc'].min()} → {df['timestamp_utc'].max()}")

if __name__ == "__main__":
    main()
