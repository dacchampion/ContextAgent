import argparse
import pandas as pd
import sys
from sqlalchemy import text
from etl.utils import get_session, get_symbol_id

def get_last_indicator_ts(session, symbol_id: int, candle_width: str):
    row = session.execute(text("""
      SELECT MAX(timestamp_utc) AS last_ts
      FROM indicators
      WHERE symbol_id=:sid AND candle_width=:cw
    """), {"sid": symbol_id, "cw": candle_width}).fetchone()
    return row[0] if row and row[0] else None

def fetch_ohlcv_auto(session, symbol_id: int, candle_width: str, warmup: int = 300) -> pd.DataFrame:
    # Toma un bloque suficientemente grande (warmup + 2000 p.ej.) y luego filtra en RAM
    rows = session.execute(text("""
      SELECT timestamp_utc, open_price, high_price, low_price, close_price, volume
      FROM ohlcv
      WHERE symbol_id=:sid AND candle_width=:cw
      ORDER BY timestamp_utc ASC
    """), {"sid": symbol_id, "cw": candle_width}).mappings().all()
    return pd.DataFrame(rows)

def fetch_ohlcv_since(session, symbol_id: int, candle_width: str, since_ts, warmup: int = 300) -> pd.DataFrame:
    # Trae un poco antes del since_ts para continuidad de EMA/SMA
    rows = session.execute(text("""
      SELECT timestamp_utc, open_price, high_price, low_price, close_price, volume
      FROM ohlcv
      WHERE symbol_id=:sid AND candle_width=:cw
        AND timestamp_utc >= (
          SELECT COALESCE(MAX(t2.timestamp_utc), :since) FROM (
            SELECT timestamp_utc FROM ohlcv
            WHERE symbol_id=:sid AND candle_width=:cw AND timestamp_utc < :since
            ORDER BY timestamp_utc DESC
            LIMIT :warmup
          ) AS t2
        )
      ORDER BY timestamp_utc ASC
    """), {"sid": symbol_id, "cw": candle_width, "since": since_ts, "warmup": warmup}).mappings().all()
    return pd.DataFrame(rows)

def fetch_ohlcv_range(session, symbol_id: int, candle_width: str, start: str, end: str, warmup: int = 300) -> pd.DataFrame:
    # Igual que since pero con ventana explícita y warmup previo
    rows = session.execute(text("""
      SELECT timestamp_utc, open_price, high_price, low_price, close_price, volume
      FROM ohlcv
      WHERE symbol_id=:sid AND candle_width=:cw
        AND timestamp_utc >= (
          SELECT COALESCE(MAX(t2.timestamp_utc), :start) FROM (
            SELECT timestamp_utc FROM ohlcv
            WHERE symbol_id=:sid AND candle_width=:cw AND timestamp_utc < :start
            ORDER BY timestamp_utc DESC
            LIMIT :warmup
          ) AS t2
        )
        AND timestamp_utc <= :end
      ORDER BY timestamp_utc ASC
    """), {"sid": symbol_id, "cw": candle_width, "start": start, "end": end, "warmup": warmup}).mappings().all()
    return pd.DataFrame(rows)

def compute_core(df: pd.DataFrame) -> pd.DataFrame:
    d = df.sort_values("timestamp_utc").copy()

    # Asegura dtype float por si llegan NaN/inf
    for c in ["open_price","high_price","low_price","close_price","volume"]:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce").astype("float64")

    # SMA
    d["sma20"] = d["close_price"].rolling(20, min_periods=1).mean()
    d["sma50"] = d["close_price"].rolling(50, min_periods=1).mean()

    # VWAP (precio típico * volumen acumulado / volumen acumulado)
    tp = (d["high_price"] + d["low_price"] + d["close_price"]) / 3.0
    vol = d["volume"].fillna(0.0)
    tpv_cum = (tp * vol).cumsum()
    v_cum = vol.cumsum()
    # Evita división por cero
    d["vwap"] = tpv_cum.where(v_cum == 0, tpv_cum / v_cum)
    d.loc[v_cum == 0, "vwap"] = pd.NA

    # EMAs
    d["ema8"]  = d["close_price"].ewm(span=8,  adjust=False).mean()
    d["ema21"] = d["close_price"].ewm(span=21, adjust=False).mean()
    d["ema50"] = d["close_price"].ewm(span=50, adjust=False).mean()
    return d

def upsert_indicators_wide(session, symbol_id: int, candle_width: str, df: pd.DataFrame):
    if df.empty:
        return 0
    cols = ["vwap","ema8","ema21","ema50","sma20","sma50"]
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")

    recs = []
    for r in df.to_dict(orient="records"):
        recs.append({
            "symbol_id": symbol_id, "candle_width": candle_width, "timestamp_utc": r["timestamp_utc"],
            "vwap": r.get("vwap"),
            "ema8": r.get("ema8"), "ema21": r.get("ema21"), "ema50": r.get("ema50"),
            "sma20": r.get("sma20"), "sma50": r.get("sma50"),
        })
    session.execute(text("""
      INSERT INTO indicators(symbol_id, candle_width, timestamp_utc, vwap, ema8, ema21, ema50, sma20, sma50, updated_utc)
      VALUES (:symbol_id, :candle_width, :timestamp_utc, :vwap, :ema8, :ema21, :ema50, :sma20, :sma50, UTC_TIMESTAMP(3))
      ON DUPLICATE KEY UPDATE
        vwap=VALUES(vwap),
        ema8=VALUES(ema8), ema21=VALUES(ema21), ema50=VALUES(ema50),
        sma20=VALUES(sma20), sma50=VALUES(sma50),
        updated_utc=UTC_TIMESTAMP(3)
    """), recs)
    session.commit()
    return len(recs)

# (Opcional) grabar en indicator_series si quieres periodos adicionales
def upsert_indicator_series(session, symbol_id: int, candle_width: str, df: pd.DataFrame, name: str, window: int, values_col: str, method: str = None):
    if values_col not in df.columns or df[values_col].isna().all():
        return 0
    recs = []
    for r in df[["timestamp_utc", values_col]].dropna().to_dict(orient="records"):
        recs.append({
            "symbol_id": symbol_id,
            "candle_width": candle_width,
            "timestamp_utc": r["timestamp_utc"],
            "indicator_name": name,
            "window_size": window,
            "indicator_value": r[values_col],
            "indicator_method": method
        })
    session.execute(text("""
      INSERT INTO indicator_series(symbol_id, candle_width, timestamp_utc, indicator_name, window_size, indicator_value, indicator_method, updated_utc)
      VALUES (:symbol_id, :candle_width, :timestamp_utc, :indicator_name, :window_size, :indicator_value, :indicator_method, UTC_TIMESTAMP(3))
      ON DUPLICATE KEY UPDATE
        indicator_value=VALUES(indicator_value),
        indicator_method=VALUES(indicator_method),
        updated_utc=UTC_TIMESTAMP(3)
    """), recs)
    session.commit()
    return len(recs)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--candle_width", default="5m", choices=["1d","30m","5m"])
    ap.add_argument("--mode", choices=["auto","full","range"], default="auto")
    ap.add_argument("--warmup", type=int, default=300)
    ap.add_argument("--start")
    ap.add_argument("--end")
    args = ap.parse_args()

    with get_session() as session:
        symbol_id = get_symbol_id(session, args.symbol)

        if args.mode == "full":
            ohlcv = fetch_ohlcv_auto(session, symbol_id, args.candle_width, args.warmup)
        elif args.mode == "range":
            if not args.start or not args.end:
                print("[indicators] --mode range requiere --start y --end (YYYY-MM-DD o ISO)."); 
                sys.exit(1)
            ohlcv = fetch_ohlcv_range(session, symbol_id, args.candle_width, args.start, args.end, args.warmup)
        else:  # auto
            last_ts = get_last_indicator_ts(session, symbol_id, args.candle_width)
            if last_ts is None:
                ohlcv = fetch_ohlcv_auto(session, symbol_id, args.candle_width, args.warmup)
            else:
                ohlcv = fetch_ohlcv_since(session, symbol_id, args.candle_width, last_ts, args.warmup)
        
        core = compute_core(ohlcv)
        n_wide = upsert_indicators_wide(session, symbol_id, args.candle_width, core)

        upsert_indicator_series(session, symbol_id, args.candle_width, core, "EMA", 8,  "ema8",  "PandasEWM")
        upsert_indicator_series(session, symbol_id, args.candle_width, core, "EMA", 21, "ema21", "PandasEWM")
        upsert_indicator_series(session, symbol_id, args.candle_width, core, "EMA", 50, "ema50", "PandasEWM")
        upsert_indicator_series(session, symbol_id, args.candle_width, core, "SMA", 20, "sma20", "RollingMean")
        upsert_indicator_series(session, symbol_id, args.candle_width, core, "SMA", 50, "sma50", "RollingMean")
        # VWAP suele tener window 0 ó 1 para “no-parametrizado”
        upsert_indicator_series(session, symbol_id, args.candle_width, core, "VWAP", 0, "vwap", "CumulativeTPV/Vol")

        session.execute(text("""
            INSERT INTO job_runs(job_name, symbol_id, candle_width, run_status, rows_affected, log_message)
            VALUES ('calc_indicators', :sid, :cw, 'success', :rows, :msg)
        """), {"sid": symbol_id, "cw": args.candle_width, "rows": int(n_wide), "msg":"ok"})
        session.commit()

    print(f"[indicators] {args.symbol} {args.candle_width} filas procesadas: {len(core)} (wide={n_wide})")

if __name__ == "__main__":
    main()
