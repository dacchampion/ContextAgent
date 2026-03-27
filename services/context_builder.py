# -*- coding: utf-8 -*-
"""
Context Builder (ORM) – usa la Session inyectada y los modelos del proyecto.
- Models: Symbols, Ohlcv, Indicators (con bb_* en indicators)
- 1 query por timeframe (subquery de ventana OHLCV + LEFT JOIN a Indicators)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import math
import bisect

from sqlalchemy import select, and_, desc, asc
from sqlalchemy.orm import Session
from app.models.symbol import Symbol
from app.models.ohlcv import Ohlcv
from app.models.indicators import Indicators
from app.models.avwap_anchors import AvwapAnchors

# -----------------------------
# Config por timeframe
# -----------------------------
TF_MAP_IN = {"1D": "1d", "30m": "30m", "5m": "5m", "1m": "1m"}
TF_MAP_OUT = {"1d": "1D", "30m": "30m", "5m": "5m", "1m": "1m"}

TF_CFG: dict[str, dict[str, int | float]] = {
    "1d":   {"eps": 0.006,  "lookback_prev": 20, "window_rows": 220, "squeeze_window": 200},
    "30m":  {"eps": 0.003,  "lookback_prev": 20, "window_rows": 260, "squeeze_window": 240},
    "5m":   {"eps": 0.0015, "lookback_prev": 20, "window_rows": 420, "squeeze_window": 400},
    "1m":   {"eps": 0.0007, "lookback_prev": 20, "window_rows": 900, "squeeze_window": 800},
}

AVWAP_CFG = {
    "max_anchors_per_type": 3,        # top-N por tipo (más recientes)
    "lookback_days": 120,             # no mirar anchors muy antiguos
    "use_typical_price": True,        # True: (H+L+C)/3; False: close
}

# -----------------------------
# Excepciones
# -----------------------------
class ContextError(Exception): ...
class SymbolNotFound(ContextError): ...
class NoDataError(ContextError): ...

# -----------------------------
# Utils
# -----------------------------
def _iso_z(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")

def _safe_pct(num: Optional[float], den: Optional[float]) -> Optional[float]:
    if num is None or den is None or den == 0:
        return None
    try:
        val = num / den
        return val if math.isfinite(val) else None
    except Exception:
        return None
    
def _to_float(x):
    if x is None:
        return None
    if isinstance(x, Decimal):
        try:
            return float(x)
        except Exception:
            return None
    if isinstance(x, (int, float)):
        if math.isnan(x) or math.isinf(x):
            return None
        return float(x)
    try:
        return float(x)
    except Exception:
        return None

def _percentile(sorted_values: List[float], p: float) -> Optional[float]:
    if not sorted_values:
        return None
    if p <= 0: return sorted_values[0]
    if p >= 100: return sorted_values[-1]
    k = (len(sorted_values) - 1) * (p / 100.0)
    f, c = math.floor(k), math.ceil(k)
    if f == c: return sorted_values[int(k)]
    return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)

def _sanitize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float):
        return _to_float(obj)
    return obj

def _typical_price(h: float | None, l: float | None, c: float | None, fallback_close=True) -> float | None:
    if h is None or l is None or c is None:
        return c if fallback_close else None
    return (h + l + c) / 3.0

def _fetch_anchors(db: Session, symbol_id: int, cw: str, as_of: datetime) -> list[dict]:
    """Devuelve anchors recientes (dicts) acotados por tipo y lookback."""
    lookback_start = as_of - timedelta(days=int(AVWAP_CFG["lookback_days"]))
    q = (
        select(AvwapAnchors)
        .where(and_(
            AvwapAnchors.symbol_id == symbol_id,
            AvwapAnchors.candle_width == cw,
            AvwapAnchors.anchor_ts_utc >= lookback_start
        ))
        .order_by(desc(AvwapAnchors.anchor_ts_utc))
    )
    rows = db.execute(q).scalars().all()
    if not rows:
        return []
    # Mantener solo los "max_anchors_per_type" por tipo
    max_per_type = int(AVWAP_CFG["max_anchors_per_type"])
    buckets: dict[str, list] = {}
    for r in rows:
        buckets.setdefault(r.anchor_type, [])
        if len(buckets[r.anchor_type]) < max_per_type:
            buckets[r.anchor_type].append(r)
    # Flatear a lista y devolver ordenados por ts asc (para reproducibilidad)
    anchors: list[dict] = []
    for _type, lst in buckets.items():
        for r in lst:
            anchors.append({
                "type": r.anchor_type,
                "label": r.anchor_label or r.anchor_type,
                "ts": r.anchor_ts_utc,
            })
    anchors.sort(key=lambda x: x["ts"])
    return anchors

def _compute_avwap_for_anchors(
    bars: list[dict],  # [{"ts":..., "hi":..., "lo":..., "cl":..., "vol":...}, ...] ASC
    anchors: list[dict],  # [{"type":..., "label":..., "ts":...}]
) -> list[dict]:
    """Calcula AVWAP para cada anchor usando prefijos (O(1) por anchor)."""
    if not anchors or not bars:
        return []
    # Prefijos
    num = [0.0]     # sum(p*vol)
    den = [0.0]     # sum(vol)
    ts_index: list[datetime] = []
    use_typical = bool(AVWAP_CFG["use_typical_price"])
    for b in bars:
        p = _typical_price(b["hi"], b["lo"], b["cl"]) if use_typical else b["cl"]
        v = b["vol"] or 0.0

        current_tpv = p * v if p is not None and v != 0.0 else 0.0
        num.append(num[-1] + current_tpv)
        den.append(den[-1] + v)
        ts_index.append(b["ts"])

    def find_start_idx(anchor_ts: datetime) -> int:
        return bisect.bisect_left(ts_index, anchor_ts)

    out: list[dict] = []
    for a in anchors:
        i0 = find_start_idx(a["ts"])
        if i0 >= len(ts_index):
            # anchor fuera de rango (sin barras hacia adelante)
            continue
        # prefijos están 1-based (num/den), índice de barras es 0-based
        # suma desde i0 hasta fin = (num[end] - num[i0]) / (den[end] - den[i0])
        n = num[-1] - num[i0]
        d = den[-1] - den[i0]
        val = (n / d) if d and d != 0 else None
        out.append({
            "type": a["type"],
            "label": a["label"],
            "ts": a["ts"].replace(tzinfo=timezone.utc).isoformat().replace("+00:00","Z"),
            "value": val,
        })
    return out

# -----------------------------
# Snapshot
# -----------------------------
@dataclass
class Snapshot:
    as_of: datetime
    close: Optional[float]
    ema21: Optional[float]
    ema21_prev: Optional[float]
    sma50: Optional[float]
    bb_mid: Optional[float]
    bb_up: Optional[float]
    bb_dn: Optional[float]
    bb_percB: Optional[float]
    bb_bw: Optional[float]
    kc_mid: Optional[float]
    kc_up: Optional[float]
    kc_dn: Optional[float]
    vwap: Optional[float]
    prev_high: Optional[float]
    prev_low: Optional[float]
    highs: List[float]
    lows: List[float]
    bb_bw_series: List[float]

# -----------------------------
# Fetch (1 query por TF) – ORM
# -----------------------------
def _fetch_snapshot(db: Session, symbol_id: int, cw: str) -> Snapshot:
    cfg = TF_CFG[cw]
    rows_needed = int(cfg["window_rows"])

    # Subquery: últimas N velas OHLCV (orden desc, limit) → luego orden asc
    w = (
        select(
            Ohlcv.timestamp_utc.label("ts"),
            Ohlcv.high_price.label("hi"),
            Ohlcv.low_price.label("lo"),
            Ohlcv.close_price.label("cl"),
        )
        .where(and_(Ohlcv.symbol_id == symbol_id, Ohlcv.candle_width == cw))
        .order_by(desc(Ohlcv.timestamp_utc))
        .limit(rows_needed)
    ).subquery("w")

    # LEFT JOIN a indicators por timestamp (mismo sid/tf/ts)
    q = (
        select(
            w.c.ts, w.c.hi, w.c.lo, w.c.cl,
            Indicators.vwap,
            Indicators.ema21,
            Indicators.sma50,
            Indicators.bb_mid,
            Indicators.bb_up,
            Indicators.bb_dn,
            Indicators.bb_percB,
            Indicators.bb_bw,
            Indicators.kc_mid,
            Indicators.kc_up,
            Indicators.kc_dn,
        )
        .select_from(w)
        .outerjoin(
            Indicators,
            and_(
                Indicators.symbol_id == symbol_id,
                Indicators.candle_width == cw,
                Indicators.timestamp_utc == w.c.ts,
            )
        )
        .order_by(w.c.ts.asc())
    )

    rows = db.execute(q).all()
    if not rows:
        raise NoDataError(f"Sin datos para symbol_id={symbol_id} tf={cw}")

    last = rows[-1]
    ema21_prev = _to_float(rows[-2].ema21) if len(rows) >= 2 else None

    lb = int(cfg["lookback_prev"])
    prev_slice = rows[-(lb+1):-1] if len(rows) > 1 else []
    highs = [float(r.hi) for r in prev_slice if r.hi is not None]
    lows = [float(r.lo) for r in prev_slice if r.lo is not None]
    prev_high = max(highs) if highs else None
    prev_low = min(lows) if lows else None

    sq_win = int(cfg["squeeze_window"])
    bw_slice = rows[-sq_win:] if len(rows) >= sq_win else rows
    bb_bw_series = [float(r.bb_bw) for r in bw_slice if r.bb_bw is not None and math.isfinite(r.bb_bw)]

    return Snapshot(
        as_of=last.ts,
        close=_to_float(last.cl),
        ema21=_to_float(last.ema21),
        ema21_prev=ema21_prev,
        sma50=_to_float(last.sma50),
        bb_mid=_to_float(last.bb_mid),
        bb_up=_to_float(last.bb_up),
        bb_dn=_to_float(last.bb_dn),
        bb_percB=_to_float(last.bb_percB),
        bb_bw=_to_float(last.bb_bw),
        kc_mid=_to_float(last.kc_mid),
        kc_up=_to_float(last.kc_up),
        kc_dn=_to_float(last.kc_dn),
        vwap=_to_float(last.vwap),
        prev_high=_to_float(prev_high),
        prev_low=_to_float(prev_low),
        highs=[float(r.hi) for r in rows if r.hi is not None],
        lows=[float(r.lo) for r in rows if r.lo is not None],
        bb_bw_series=bb_bw_series,
    )

def _fetch_ohlcv_range(db: Session, symbol_id: int, cw: str, start_ts: datetime, end_ts: datetime) -> list[dict]:
    q = (
        select(
            Ohlcv.timestamp_utc.label("ts"),
            Ohlcv.high_price.label("hi"),
            Ohlcv.low_price.label("lo"),
            Ohlcv.close_price.label("cl"),
            Ohlcv.volume.label("vol"),
        )
        .where(and_(
            Ohlcv.symbol_id == symbol_id,
            Ohlcv.candle_width == cw,
            Ohlcv.timestamp_utc >= start_ts,
            Ohlcv.timestamp_utc <= end_ts,
        ))
        .order_by(asc(Ohlcv.timestamp_utc))
    )
    rows = db.execute(q).all()
    bars = []
    for r in rows:
        bars.append({
            "ts": r.ts,
            "hi": _to_float(r.hi),
            "lo": _to_float(r.lo),
            "cl": _to_float(r.cl),
            "vol": _to_float(r.vol),
        })
    return bars

# -----------------------------
# Lógica
# -----------------------------
def _trend_bias(s: Snapshot) -> Tuple[str, List[str]]:
    reasons: List[str] = []
    bias = "sideways"
    slope_pos = None
    if s.ema21 is not None and s.ema21_prev is not None:
        slope_pos = s.ema21 > s.ema21_prev
        reasons.append("+slope ema21" if slope_pos else "-slope ema21")
    if s.close is not None and s.ema21 is not None:
        if s.close > s.ema21 and slope_pos is True:
            reasons.insert(0, ">close vs ema21")
            bias = "up"
        elif s.close < s.ema21 and slope_pos is False:
            reasons.insert(0, "<close vs ema21")
            bias = "down"
    return bias, reasons

def _distances(s: Snapshot) -> Dict[str, Optional[float]]:
    if s.close is None:
        return {"to_ema21": None, "to_sma50": None, "to_bb_up": None, "to_bb_dn": None, "to_kc_up": None, "to_kc_dn": None}
    
    return {
        "to_ema21": _safe_pct(s.close - s.ema21, s.ema21) if s.ema21 is not None else None,
        "to_sma50": _safe_pct(s.close - s.sma50, s.sma50) if s.sma50 is not None else None,
        "to_bb_up": _safe_pct(s.close - s.bb_up, s.bb_up) if s.bb_up is not None else None,
        "to_bb_dn": _safe_pct(s.close - s.bb_dn, s.bb_dn) if s.bb_dn is not None else None,
        "to_kc_up": _safe_pct(s.close - s.kc_up, s.kc_up) if s.kc_up is not None else None,
        "to_kc_dn": _safe_pct(s.close - s.kc_dn, s.kc_dn) if s.kc_dn is not None else None,
    }

def _zones(s: Snapshot, eps: float, anchored: list[dict] | None = None) -> list[dict]:
    zones: list[dict] = []
    avwap_vals = [x["value"] for x in (anchored or []) if x.get("value") is not None]
    any_avwap_above = s.close is not None and any(v is not None and v > s.close for v in avwap_vals)
    any_avwap_below = s.close is not None and any(v is not None and v < s.close for v in avwap_vals)

    # resistencia por prev_high ± eps; confluencias: bb_up, kc_up, (ema21+AVWAP)
    if s.prev_high is not None:
        zf, zt = s.prev_high * (1 - eps), s.prev_high * (1 + eps)
        reason = ["prev_high"]
        if s.bb_up is not None and abs(s.prev_high - s.bb_up) / s.prev_high <= eps:
            reason.append("bb_up")
        if s.kc_up is not None and abs(s.prev_high - s.kc_up) / s.prev_high <= eps:
            reason.append("kc_up")
        if (s.ema21 is not None and s.close is not None
                and s.ema21 > s.close and any_avwap_above):
            reason.append("ema21+AVWAP")
        zones.append({"type": "resistance", "from": zf, "to": zt, "reason": reason})

    # soporte por prev_low ± eps; confluencias: bb_dn, kc_dn, sma50, (ema21+AVWAP inverso opcional)
    if s.prev_low is not None:
        zf, zt = s.prev_low * (1 - eps), s.prev_low * (1 + eps)
        reason = ["prev_low"]
        if s.bb_dn is not None and abs(s.prev_low - s.bb_dn) / s.prev_low <= eps:
            reason.append("bb_dn")
        if s.kc_dn is not None and abs(s.prev_low - s.kc_dn) / s.prev_low <= eps:
            reason.append("kc_dn")
        if s.sma50 is not None and abs(s.prev_low - s.sma50) / s.prev_low <= eps:
            reason.append("sma50")
        if (s.ema21 is not None and s.close is not None
                and s.ema21 < s.close and any_avwap_below):
            reason.append("ema21+AVWAP")
        zones.append({"type": "support", "from": zf, "to": zt, "reason": reason})

    if not any(z["type"] == "resistance" for z in zones):
        reasons = []
        res_levels = [(s.bb_up, "bb_up"), (s.kc_up, "kc_up")]
        valid_levels = [l for l in res_levels if l[0] is not None]
        if valid_levels:
            level = min(valid_levels, key=lambda x: x[0])[0] # mas bajo de los techos
            for lvl, name in valid_levels:
                if abs(level - lvl) / level <= eps:
                    reasons.append(name)
            zones.append({"type": "resistance",
                          "from": level * (1 - eps), "to": level * (1 + eps),
                          "reason": reasons})

    if not any(z["type"] == "support" for z in zones):
        reasons = []
        sup_levels = [(s.bb_dn, "bb_dn"), (s.kc_dn, "kc_dn")]
        valid_levels = [l for l in sup_levels if l[0] is not None]
        if valid_levels:
            level = max(valid_levels, key=lambda x: x[0])[0] # mas alto de los pisos
            for lvl, name in valid_levels:
                if abs(level - lvl) / level <= eps:
                    reasons.append(name)
            zones.append({"type": "support",
                          "from": level * (1 - eps), "to": level * (1 + eps),
                          "reason": reasons})
    return zones

def _flags(s: Snapshot, zones: List[Dict[str, Any]], eps: float) -> Dict[str, Any]:
    near_res = near_sup = False
    if s.close is not None:
        for z in zones:
            zf, zt = z.get("from"), z.get("to")
            if zf is None or zt is None:
                continue
            if z["type"] == "resistance" and zf <= s.close <= zt:
                near_res = True
            if z["type"] == "support" and zf <= s.close <= zt:
                near_sup = True

    p20 = None
    if s.bb_bw_series:
        sorted_bw = sorted([b for b in s.bb_bw_series if _to_float(b) is not None])
        p20 = _percentile(sorted_bw, 20.0)
    
    squeeze = bool(p20 is not None and s.bb_bw is not None and s.bb_bw <= p20)
    overext = bool(s.bb_percB is not None and (s.bb_percB > 1.0 or s.bb_percB < 0.0))

    # TTM Squeeze: Bollinger Bands inside Keltner Channels
    bb_inside_kc = False
    squeeze_intensity = None
    if s.bb_up is not None and s.bb_dn is not None and s.kc_up is not None and s.kc_dn is not None:
        bb_inside_kc = (s.bb_up < s.kc_up) and (s.bb_dn > s.kc_dn)
        bb_w = s.bb_up - s.bb_dn
        kc_w = s.kc_up - s.kc_dn
        if kc_w > 0:
            squeeze_intensity = bb_w / kc_w

    return {
        "near_resistance": near_res,
        "near_support": near_sup,
        "squeeze_candidate": squeeze,
        "overextended_bb": overext,
        "bb_inside_kc_squeeze": bb_inside_kc,
        "squeeze_intensity": squeeze_intensity,
    }

# -----------------------------
# API pública (ORM)
# -----------------------------
def build_context_json(db: Session, symbol: str, tfs: List[str]) -> Dict[str, Any]:
    if not tfs:
        raise ContextError("Se requiere al menos un timeframe")

    tfs_norm: List[str] = []
    for tf in tfs:
        t = tf.strip()
        if t in TF_MAP_IN:
            tfs_norm.append(TF_MAP_IN[t])
        elif t in TF_MAP_OUT:
            tfs_norm.append(t)
        else:
            raise ContextError(f"Timeframe no soportado: {t}")

    # Resolver symbol_id en 'symbols'
    sid = db.execute(
        select(Symbol.symbol_id).where(Symbol.symbol == symbol)
    ).scalar_one_or_none()
    if sid is None:
        raise SymbolNotFound(f"Ticker no existe: {symbol}")

    blocks: List[Dict[str, Any]] = []
    as_of_list: List[datetime] = []

    for cw in tfs_norm:
        cfg = TF_CFG[cw]
        eps = float(cfg["eps"])

        snap = _fetch_snapshot(db, sid, cw)
        anchors = _fetch_anchors(db, sid, cw, snap.as_of)
        bias, reason = _trend_bias(snap)

        anchored_list = []
        if anchors:
            min_anchor_ts = anchors[0]["ts"]  # están ordenados asc por ts
            bars = _fetch_ohlcv_range(db, sid, cw, start_ts=min_anchor_ts, end_ts=snap.as_of)
            anchored_list = _compute_avwap_for_anchors(bars, anchors)        

        levels = {
            "ma": {"ema21": snap.ema21, "sma50": snap.sma50},
            "bb": {"mid": snap.bb_mid, "up": snap.bb_up, "dn": snap.bb_dn,
                "percB": snap.bb_percB, "bandwidth": snap.bb_bw},
            "kc": {"mid": snap.kc_mid, "up": snap.kc_up, "dn": snap.kc_dn},
            "vwap": {"session": snap.vwap, "anchored": anchored_list},
        }

        dists = _distances(snap)
        zones = _zones(snap, eps, anchored_list)
        flags = _flags(snap, zones, eps)

        block = {
            "timeframe": TF_MAP_OUT[cw],
            "trend": {"bias": bias, "reason": reason},
            "levels": levels,
            "distance": dists,
            "zones": zones,
            "summary_flags": flags,
            "as_of": _iso_z(snap.as_of),
        }
        blocks.append(_sanitize(block))
        as_of_list.append(snap.as_of)

    out = {
        "symbol": symbol,
        "as_of": _iso_z(max(as_of_list)) if as_of_list else None,
        "timeframes": blocks,
    }
    return _sanitize(out)
