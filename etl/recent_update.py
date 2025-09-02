import argparse
import os
import sys
import logging
from datetime import datetime, timedelta, timezone
import pandas as pd
from twelvedata import TDClient
from sqlalchemy import text
from etl.utils import (
    get_session, get_symbol_id, get_provider_id,
    normalize_df, upsert_ohlcv, update_sync_meta
)

# Logger dedicado
logger = logging.getLogger("recent_update")
if not logger.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(h)
logger.setLevel(logging.DEBUG if os.getenv("RECENT_LOG") else logging.INFO)

def _estimate_needed_bars(candle_width: str, lookback_days: int) -> int:
    if candle_width == "5m":
        return lookback_days * 78 + 200
    if candle_width == "30m":
        return lookback_days * 13 + 50
    if candle_width == "1d":
        return lookback_days + 10
    return 2000

def fetch_td(symbol: str, candle_width: str, lookback_days: int = 3) -> pd.DataFrame:
    td_key = os.getenv("TWELVE_DATA_KEY")
    if not td_key:
        raise RuntimeError("TWELVE_DATA_KEY no está definido")

    td = TDClient(apikey=td_key)
    td_map = {"1d": "1day", "30m": "30min", "5m": "5min"}
    if candle_width not in td_map:
        raise ValueError("candle_width debe ser uno de: 1d, 30m, 5m")

    end_utc = datetime.now(timezone.utc)
    start_utc = end_utc - timedelta(days=lookback_days)

    # outputsize <= 5000
    needed = min(5000, max(1, _estimate_needed_bars(candle_width, lookback_days)))

    logger.info(f"TD fetch {symbol} {candle_width} days={lookback_days} start={start_utc} end={end_utc} outputsize={needed}")
    ts = td.time_series(
        symbol=symbol,
        interval=td_map[candle_width],
        start_date=start_utc.strftime("%Y-%m-%d %H:%M:%S"),
        end_date=end_utc.strftime("%Y-%m-%d %H:%M:%S"),
        outputsize=needed,
        timezone="UTC",
        order="ASC",
    )
    df = ts.as_pandas()
    if df is None or df.empty:
        return pd.DataFrame()

    # --- Normaliza índice a tz-aware UTC para evitar comparaciones inválidas ---
    idx = pd.to_datetime(df.index, errors="coerce")
    if getattr(idx.tz, "key", None) is None:   # tz-naive -> localiza a UTC
        idx = idx.tz_localize("UTC")
    else:                                      # tz-aware -> convierte a UTC
        idx = idx.tz_convert("UTC")
    df.index = idx

    # Filtro final en UTC (ambos aware)
    mask = (df.index >= start_utc) & (df.index <= end_utc)
    df = df.loc[mask]

    return df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--candle_width", default="5m", choices=["1d", "30m", "5m"])
    ap.add_argument("--days", type=int, default=3)
    args = ap.parse_args()

    logger.info(f"[recent] start | symbol={args.symbol} candle_width={args.candle_width} days={args.days}")

    try:
        df_raw = fetch_td(args.symbol, args.candle_width, args.days)
    except Exception as e:
        logger.exception(f"Error al llamar Twelve Data: {e}")
        return

    if df_raw is None or df_raw.empty:
        logger.error(f"[recent] Sin datos de Twelve Data para {args.symbol} {args.candle_width} (days={args.days}).")
        return

    df = normalize_df(df_raw, args.symbol, args.candle_width, source="twelvedata")
    if df.empty:
        logger.error(f"[recent] DataFrame normalizado vacío para {args.symbol} {args.candle_width}. df_raw.cols={list(df_raw.columns)} shape={df_raw.shape}")
        return

    with get_session() as session:
        symbol_id = get_symbol_id(session, args.symbol)
        provider_id = get_provider_id(session, "twelvedata", "https://api.twelvedata.com")
        inserted = upsert_ohlcv(session, df, symbol_id, provider_id)
        last_ts = df["timestamp_utc"].max().to_pydatetime().replace(tzinfo=None)
        update_sync_meta(session, symbol_id, args.candle_width, realtime_utc=last_ts)
        session.execute(text("""
            INSERT INTO job_runs(job_name, symbol_id, candle_width, run_status, rows_affected, log_message)
            VALUES ('recent_td', :sid, :cw, 'success', :rows, :msg)
        """), {"sid": symbol_id, "cw": args.candle_width, "rows": int(inserted), "msg": "ok"})
        session.commit()

    logger.info(f"[recent] done | rows={len(df)} range={df['timestamp_utc'].min()} → {df['timestamp_utc'].max()}")

if __name__ == "__main__":
    main()
