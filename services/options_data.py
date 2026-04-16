from __future__ import annotations

import json
from datetime import datetime, timezone
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.models.gex_snapshot import GexSnapshot
from app.models.job_run import JobRun


API_KEYWORDS = (
    "gex",
    "gamma",
    "option",
    "strike",
    "exposure",
    "greeks",
    "ohlc",
    "chart",
    "level",
    "flow",
    "cluster",
)

VALID_GEX_FILTER_PRESETS = (
    "All",
    "0DTE",
    "ThisWeek",
    "Next2Weeks",
    "OpExCycle",
    "Next2OpEx",
)

REQUIRED_ANALYSIS_FIELDS = (
    "zero_gamma_level",
    "dealer_cluster_upper",
    "dealer_cluster_lower",
    "gex_map",
)

UPPER_CLUSTER_RANGE_START_KEYS = (
    "maxY1",
    "upperClusterRangeStart",
    "dealerClusterUpperRangeStart",
    "dealer_cluster_upper_range_start",
)

LOWER_CLUSTER_RANGE_START_KEYS = (
    "minY0",
    "lowerClusterRangeStart",
    "dealerClusterLowerRangeStart",
    "dealer_cluster_lower_range_start",
)

ZERO_GAMMA_KEYS = (
    "zero_gamma",
    "zeroGamma",
    "zeroGammaLevel",
    "zero_gamma_level",
    "zeroG",
    "zg",
)

UPPER_CLUSTER_KEYS = (
    "dealer_clusters_upper",
    "dealerClusterUpper",
    "upperDealerCluster",
    "upper_dealer_cluster",
    "upperClusters",
    "upper_cluster",
    "gamma_zone_add",
)

LOWER_CLUSTER_KEYS = (
    "dealer_clusters_lower",
    "dealerClusterLower",
    "lowerDealerCluster",
    "lower_dealer_cluster",
    "lowerClusters",
    "lower_cluster",
    "gamma_zone_sub",
)

GEX_MAP_COLLECTION_KEYS = (
    "gexMap",
    "gex_map",
    "gexLevels",
    "gex_levels",
    "gammaLevels",
    "gamma_levels",
    "levels",
    "strikes",
    "df_gex2",
)

STRIKE_KEYS = ("strike", "strikePrice", "price", "level")
TOTAL_GEX_KEYS = ("gex", "gammaExposure", "gamma_exposure", "netGamma", "net_gex")
CALL_GEX_KEYS = ("callGex", "callGammaExposure", "call_gamma_exposure", "callExposure")
PUT_GEX_KEYS = ("putGex", "putGammaExposure", "put_gamma_exposure", "putExposure")
GAMMA_KEYS = ("gamma", "gammaValue")


class OptionsDataError(Exception):
    pass


class OptionsDataConfigError(OptionsDataError):
    pass


class OptionsDataDependencyError(OptionsDataError):
    pass


class OptionsDataFetchError(OptionsDataError):
    pass


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _first_number(value: Any) -> float | None:
    if isinstance(value, list):
        for item in value:
            parsed = _first_number(item)
            if parsed is not None:
                return parsed
        return None
    if isinstance(value, dict):
        for item in value.values():
            parsed = _first_number(item)
            if parsed is not None:
                return parsed
        return None
    return _to_float(value)


def _extract_numeric_list(value: Any) -> list[float]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[float] = []
        for item in value:
            if isinstance(item, dict):
                for field in ("level", "strike", "price", "value"):
                    parsed = _to_float(item.get(field))
                    if parsed is not None:
                        out.append(parsed)
                        break
            else:
                parsed = _to_float(item)
                if parsed is not None:
                    out.append(parsed)
        return out
    parsed = _to_float(value)
    return [parsed] if parsed is not None else []


def _find_first_value(payload: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(payload, dict):
        for key in keys:
            if key in payload and payload[key] is not None:
                return payload[key]
        for value in payload.values():
            found = _find_first_value(value, keys)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_first_value(item, keys)
            if found is not None:
                return found
    return None


def _normalize_gex_row(row: dict[str, Any]) -> dict[str, Any] | None:
    strike = _first_number(_find_first_value(row, STRIKE_KEYS))
    gamma_exposure = _first_number(_find_first_value(row, TOTAL_GEX_KEYS))
    call_gamma_exposure = _first_number(_find_first_value(row, CALL_GEX_KEYS))
    put_gamma_exposure = _first_number(_find_first_value(row, PUT_GEX_KEYS))
    gamma = _first_number(_find_first_value(row, GAMMA_KEYS))

    has_gamma_fields = any(
        _find_first_value(row, key_group) is not None
        for key_group in (TOTAL_GEX_KEYS, CALL_GEX_KEYS, PUT_GEX_KEYS, GAMMA_KEYS)
    )

    if (
        strike is None
        or not has_gamma_fields
        or (
            gamma_exposure is None
            and call_gamma_exposure is None
            and put_gamma_exposure is None
            and gamma is None
        )
    ):
        return None

    return {
        "strike": strike,
        "net_gamma_exposure": gamma_exposure,
        "positive_gamma_exposure": call_gamma_exposure,
        "negative_gamma_exposure": put_gamma_exposure,
        "volume": _first_number(_find_first_value(row, ("volume", "Volume"))),
    }


def _iter_candidate_lists(payload: Any) -> Iterable[list[Any]]:
    if isinstance(payload, list):
        if payload:
            yield payload
        for item in payload:
            yield from _iter_candidate_lists(item)
    elif isinstance(payload, dict):
        for key, value in payload.items():
            if key in GEX_MAP_COLLECTION_KEYS and isinstance(value, list):
                yield value
            yield from _iter_candidate_lists(value)


def _capture_relevance_score(capture: dict[str, Any], ticker: str) -> int:
    normalized_ticker = ticker.upper()
    url = str(capture.get("url", "")).upper()
    payload = capture.get("data")
    score = 0

    strong_url_markers = (
        f"SELECT_TICKER={normalized_ticker}",
        f"SELECTED_TICKER={normalized_ticker}",
        f"TICKER={normalized_ticker}",
        f"/GET_DATE_GROUPS/{normalized_ticker}",
    )
    if any(marker in url for marker in strong_url_markers):
        score += 100

    if normalized_ticker in url:
        score += 25

    if isinstance(payload, dict):
        payload_ticker = payload.get("ticker")
        if isinstance(payload_ticker, str) and payload_ticker.upper() == normalized_ticker:
            score += 100

    return score


def _ordered_captures_for_ticker(captures: list[dict[str, Any]], ticker: str) -> list[dict[str, Any]]:
    return sorted(
        captures,
        key=lambda capture: (_capture_relevance_score(capture, ticker), captures.index(capture)),
        reverse=True,
    )


def _extract_columnar_gex_map(payload: dict[str, Any]) -> list[dict[str, Any]]:
    df_gex2 = payload.get("df_gex2")
    if not isinstance(df_gex2, dict):
        return []

    strikes = df_gex2.get("StrikePrice")
    call_gex = df_gex2.get("TotalCallGEX")
    put_gex = df_gex2.get("TotalPutGEX")
    if not isinstance(strikes, list) or not isinstance(call_gex, list) or not isinstance(put_gex, list):
        return []

    volume_by_strike: dict[float, float | None] = {}
    volume_table = payload.get("df_volume_table")
    if isinstance(volume_table, dict):
        volume_strikes = volume_table.get("StrikePrice")
        volumes = volume_table.get("Volume")
        if isinstance(volume_strikes, list) and isinstance(volumes, list):
            for strike_value, volume_value in zip(volume_strikes, volumes):
                strike = _to_float(strike_value)
                if strike is None:
                    continue
                volume_by_strike[strike] = _to_float(volume_value)

    rows: list[dict[str, Any]] = []
    for strike_value, call_value, put_value in zip(strikes, call_gex, put_gex):
        strike = _to_float(strike_value)
        call_gamma_exposure = _to_float(call_value)
        put_gamma_exposure = _to_float(put_value)
        if strike is None:
            continue
        net_gamma_exposure = None
        if call_gamma_exposure is not None or put_gamma_exposure is not None:
            net_gamma_exposure = (call_gamma_exposure or 0.0) + (put_gamma_exposure or 0.0)

        rows.append(
            {
                "net_gamma_exposure": net_gamma_exposure,
                "positive_gamma_exposure": call_gamma_exposure,
                "negative_gamma_exposure": put_gamma_exposure,
                "volume": volume_by_strike.get(strike),
                "_strike": strike,
            }
        )

    return rows


def _compute_gamma_totals(gex_map: list[dict[str, Any]]) -> tuple[float | None, float | None, float | None]:
    if not gex_map:
        return None, None, None

    positive = sum((row.get("positive_gamma_exposure") or 0.0) for row in gex_map)
    negative = sum((row.get("negative_gamma_exposure") or 0.0) for row in gex_map)
    net = sum((row.get("net_gamma_exposure") or 0.0) for row in gex_map)
    return positive, negative, net


def _strike_key(strike: float) -> str:
    if float(strike).is_integer():
        return str(int(strike))
    return format(strike, "g")


def _load_storage_state(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fp:
            return json.load(fp)
    except FileNotFoundError as exc:
        raise OptionsDataConfigError(f"Storage state file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise OptionsDataConfigError(f"Invalid storage state JSON: {path}") from exc


def _build_cookie_header(storage_state: dict[str, Any]) -> str:
    cookies = storage_state.get("cookies", [])
    parts: list[str] = []
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if name and value is not None:
            parts.append(f"{name}={value}")
    return "; ".join(parts)


def _build_cookie_jar(storage_state: dict[str, Any]) -> httpx.Cookies:
    jar = httpx.Cookies()
    for cookie in storage_state.get("cookies", []):
        name = cookie.get("name")
        value = cookie.get("value")
        domain = cookie.get("domain")
        path = cookie.get("path") or "/"
        if name and value is not None:
            jar.set(name, value, domain=domain, path=path)
    return jar


def _dashboard_url() -> str:
    dashboard_url = settings.OPTIONS_DASHBOARD_URL
    if not dashboard_url:
        raise OptionsDataConfigError(
            "Missing options dashboard URL. Set OPTIONS_DASHBOARD_URL."
        )
    return dashboard_url.rstrip("/")


def _api_base_url() -> str:
    if settings.OPTIONS_API_BASE_URL:
        return settings.OPTIONS_API_BASE_URL.rstrip("/")

    dashboard_url = settings.OPTIONS_DASHBOARD_URL
    if not dashboard_url:
        raise OptionsDataConfigError(
            "Missing options API base URL. Set OPTIONS_API_BASE_URL or OPTIONS_DASHBOARD_URL."
        )

    parsed = urlparse(dashboard_url)
    scheme = parsed.scheme or "https"
    host = parsed.netloc
    if host.startswith("dashboard."):
        host = "dashboard-api." + host[len("dashboard."):]
    if not host:
        raise OptionsDataConfigError(
            "Unable to derive options API base URL from OPTIONS_DASHBOARD_URL."
        )
    return f"{scheme}://{host}"


def _default_provider_headers(storage_state: dict[str, Any]) -> dict[str, str]:
    dashboard_url = _dashboard_url()
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": dashboard_url,
        "Referer": f"{dashboard_url}/",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/133.0.0.0 Safari/537.36"
        ),
    }
    return headers


async def _provider_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    captures: list[dict[str, Any]],
    **kwargs,
) -> httpx.Response:
    response = await client.request(method, url, **kwargs)
    payload: Any
    try:
        payload = response.json()
    except Exception:
        payload = {"raw_text": response.text}

    captures.append(
        {
            "url": str(response.request.url),
            "status": response.status_code,
            "method": response.request.method,
            "data": payload,
        }
    )
    return response


def _normalize_gex_filter_preset(gex_filter_preset: str | None) -> str:
    if not gex_filter_preset:
        return "All"

    normalized = gex_filter_preset.strip()
    for valid in VALID_GEX_FILTER_PRESETS:
        if normalized.lower() == valid.lower():
            return valid

    raise OptionsDataConfigError(
        "Invalid options data gex_filter_preset. "
        f"Valid values: {', '.join(VALID_GEX_FILTER_PRESETS)}"
    )


async def _api_fetch_gex_captures(ticker: str, gex_filter_preset: str = "All") -> list[dict[str, Any]]:
    storage_state_path = settings.OPTIONS_STORAGE_STATE_PATH
    if not storage_state_path:
        raise OptionsDataConfigError(
            "Missing options data storage state. Set OPTIONS_STORAGE_STATE_PATH or pass --storage-state."
        )

    normalized_preset = _normalize_gex_filter_preset(gex_filter_preset)
    storage_state = _load_storage_state(storage_state_path)
    api_base_url = _api_base_url()
    headers = _default_provider_headers(storage_state)
    cookies = _build_cookie_jar(storage_state)
    captures: list[dict[str, Any]] = []

    async with httpx.AsyncClient(
        headers=headers,
        cookies=cookies,
        timeout=30.0,
        follow_redirects=True,
    ) as client:
        me_response = await _provider_request(client, "GET", f"{api_base_url}/me", captures)
        if me_response.status_code == 401:
            await _provider_request(client, "POST", f"{api_base_url}/auth/refresh", captures)
            me_response = await _provider_request(client, "GET", f"{api_base_url}/me", captures)

        if me_response.status_code != 200:
            raise OptionsDataFetchError("Saved options data session is not authenticated anymore. Refresh the storage state.")

        await _provider_request(client, "GET", f"{api_base_url}/get_live_price_data", captures, params={"selected_ticker": ticker.upper()})
        await _provider_request(client, "GET", f"{api_base_url}/get_date_groups/{ticker.upper()}", captures)
        await _provider_request(
            client,
            "GET",
            f"{api_base_url}/get_candlestick_graph_data_v2",
            captures,
            params={
                "select_ticker": ticker.upper(),
                "gex_type": "GROSS",
                "gex_filter_preset": normalized_preset,
                "volume_filter_preset": "All",
            },
        )

    return captures


def parse_gex_payloads(
    ticker: str,
    captures: list[dict[str, Any]],
) -> dict[str, Any]:
    ordered_captures = _ordered_captures_for_ticker(captures, ticker)
    targeted_captures = [
        capture for capture in ordered_captures if _capture_relevance_score(capture, ticker) > 0
    ]
    primary_captures = targeted_captures or ordered_captures
    zero_gamma_level: float | None = None
    dealer_cluster_upper: float | None = None
    dealer_cluster_lower: float | None = None
    dealer_cluster_upper_range_start: float | None = None
    dealer_cluster_lower_range_start: float | None = None
    gex_map: list[dict[str, Any]] = []
    seen_rows: set[str] = set()

    for capture in primary_captures:
        payload = capture.get("data")
        if zero_gamma_level is None:
            zero_gamma_level = _first_number(_find_first_value(payload, ZERO_GAMMA_KEYS))
        if dealer_cluster_upper is None:
            dealer_cluster_upper = _first_number(_find_first_value(payload, UPPER_CLUSTER_KEYS))
        if dealer_cluster_lower is None:
            dealer_cluster_lower = _first_number(_find_first_value(payload, LOWER_CLUSTER_KEYS))
        if dealer_cluster_upper_range_start is None:
            dealer_cluster_upper_range_start = _first_number(_find_first_value(payload, UPPER_CLUSTER_RANGE_START_KEYS))
        if dealer_cluster_lower_range_start is None:
            dealer_cluster_lower_range_start = _first_number(_find_first_value(payload, LOWER_CLUSTER_RANGE_START_KEYS))

        if isinstance(payload, dict) and not gex_map:
            columnar_rows = _extract_columnar_gex_map(payload)
            if columnar_rows:
                gex_map.extend(columnar_rows)
                seen_rows.update(json.dumps({"strike": row["_strike"]}, sort_keys=True) for row in columnar_rows)
                continue

        for candidate_list in _iter_candidate_lists(payload):
            normalized_batch = [
                normalized
                for normalized in (
                    _normalize_gex_row(item) for item in candidate_list if isinstance(item, dict)
                )
                if normalized is not None
            ]
            if not normalized_batch:
                continue

            for row in normalized_batch:
                dedupe_key = json.dumps({"strike": row["strike"]}, sort_keys=True)
                if dedupe_key not in seen_rows:
                    seen_rows.add(dedupe_key)
                    gex_map.append(row)

    gex_map.sort(key=lambda item: (item.get("_strike") is None and item.get("strike") is None, item.get("_strike") or item.get("strike") or 0.0))
    total_positive_gamma, total_negative_gamma, total_net_gamma = _compute_gamma_totals(gex_map)
    gex_map_by_strike: dict[str, dict[str, Any]] = {}
    for row in gex_map:
        strike = row.pop("_strike", None)
        if strike is None:
            strike = row.pop("strike", None)
        if strike is None:
            continue
        gex_map_by_strike[_strike_key(float(strike))] = row

    response: dict[str, Any] = {
        "ticker": ticker.upper(),
        "zero_gamma_level": zero_gamma_level,
        "dealer_cluster_upper": dealer_cluster_upper,
        "dealer_cluster_lower": dealer_cluster_lower,
        "dealer_cluster_upper_range_start": dealer_cluster_upper_range_start,
        "dealer_cluster_lower_range_start": dealer_cluster_lower_range_start,
        "total_positive_gamma": total_positive_gamma,
        "total_negative_gamma": total_negative_gamma,
        "total_net_gamma": total_net_gamma,
        "gex_map": gex_map_by_strike,
    }
    return response


def summarize_capture_shapes(captures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for capture in captures:
        payload = capture.get("data")
        payload_type = type(payload).__name__
        top_level_keys: list[str] = []
        list_length: int | None = None

        if isinstance(payload, dict):
            top_level_keys = sorted(str(key) for key in payload.keys())[:25]
        elif isinstance(payload, list):
            list_length = len(payload)

        summaries.append(
            {
                "url": capture.get("url"),
                "method": capture.get("method"),
                "status": capture.get("status"),
                "payload_type": payload_type,
                "top_level_keys": top_level_keys,
                "list_length": list_length,
            }
        )
    return summaries


def validate_gex_payload(
    payload: dict[str, Any],
    captures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    stats = {
        "zero_gamma_level_present": payload.get("zero_gamma_level") is not None,
        "dealer_cluster_upper_present": payload.get("dealer_cluster_upper") is not None,
        "dealer_cluster_lower_present": payload.get("dealer_cluster_lower") is not None,
        "gex_map_count": len(payload.get("gex_map") or {}),
    }

    if payload.get("zero_gamma_level") is None:
        issues.append("Missing zero gamma level.")
    if payload.get("dealer_cluster_upper") is None:
        issues.append("Missing upper dealer cluster.")
    if payload.get("dealer_cluster_lower") is None:
        issues.append("Missing lower dealer cluster.")
    if not payload.get("gex_map"):
        issues.append("Missing GEX map rows.")

    gex_map = payload.get("gex_map") or {}
    strikes = []
    for strike_key in gex_map.keys():
        strike = _to_float(strike_key)
        if strike is not None:
            strikes.append(strike)
    if gex_map and not strikes:
        issues.append("GEX map rows were found but none contain a parsed strike.")

    rows_with_gamma = [
        row
        for row in gex_map.values()
        if any(
            row.get(field) is not None
            for field in ("net_gamma_exposure", "positive_gamma_exposure", "negative_gamma_exposure")
        )
    ]
    if gex_map and not rows_with_gamma:
        issues.append("GEX map rows were found but none contain parsed gamma fields.")

    if len(gex_map) == 1:
        warnings.append("Only one GEX row was parsed; this may indicate a partial capture.")
    if payload.get("zero_gamma_level") is not None and strikes:
        min_strike = min(strikes)
        max_strike = max(strikes)
        zero_gamma_level = payload["zero_gamma_level"]
        if zero_gamma_level < min_strike or zero_gamma_level > max_strike:
            warnings.append(
                f"Zero gamma level {zero_gamma_level} is outside parsed strike range [{min_strike}, {max_strike}]."
            )

    coverage = {
        "required_fields": list(REQUIRED_ANALYSIS_FIELDS),
        "missing_required_fields": [
            field
            for field in REQUIRED_ANALYSIS_FIELDS
            if not payload.get(field)
        ],
        "capture_summaries": summarize_capture_shapes(captures or []),
    }

    return {
        "ok": not issues,
        "issues": issues,
        "warnings": warnings,
        "stats": stats,
        "coverage": coverage,
    }


def persist_gex_snapshot(
    db,
    symbol_id: int,
    payload: dict[str, Any],
    source: str = "options_data",
    snapshot_utc: datetime | None = None,
) -> GexSnapshot:
    snapshot = GexSnapshot(
        symbol_id=symbol_id,
        source=source,
        snapshot_utc=snapshot_utc or _utc_now_naive(),
        zero_gamma_level=payload.get("zero_gamma_level"),
        dealer_cluster_upper=payload.get("dealer_cluster_upper"),
        dealer_cluster_lower=payload.get("dealer_cluster_lower"),
        dealer_cluster_upper_range_start=payload.get("dealer_cluster_upper_range_start"),
        dealer_cluster_lower_range_start=payload.get("dealer_cluster_lower_range_start"),
        gex_map=payload.get("gex_map") or {},
        created_utc=_utc_now_naive(),
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def create_job_run(
    db,
    *,
    job_name: str,
    symbol_id: int | None,
    run_status: str,
    rows_affected: int | None = None,
    log_message: str | None = None,
    finished_utc: datetime | None = None,
) -> JobRun:
    job = JobRun(
        job_name=job_name,
        symbol_id=symbol_id,
        candle_width=None,
        started_utc=_utc_now_naive(),
        finished_utc=finished_utc,
        run_status=run_status,
        rows_affected=rows_affected,
        log_message=log_message,
    )
    db.add(job)
    db.flush()
    return job


async def fetch_options_gex(
    ticker: str,
    gex_filter_preset: str = "All",
) -> dict[str, Any]:
    captures = await fetch_options_captures(ticker, gex_filter_preset=gex_filter_preset)
    return parse_gex_payloads(ticker=ticker, captures=captures)


async def validate_options_session(
    storage_state_path: str | None = None,
) -> dict[str, Any]:
    session_path = storage_state_path or settings.OPTIONS_STORAGE_STATE_PATH
    if not session_path:
        return {
            "ok": False,
            "status": None,
            "detail": "Missing options data storage state path.",
            "email": None,
        }

    storage_state = _load_storage_state(session_path)
    api_base_url = _api_base_url()
    headers = _default_provider_headers(storage_state)
    cookies = _build_cookie_jar(storage_state)

    async with httpx.AsyncClient(headers=headers, cookies=cookies, timeout=30.0, follow_redirects=True) as client:
        try:
            res = await client.get(f"{api_base_url}/me")
            if res.status_code == 401:
                await client.post(f"{api_base_url}/auth/refresh")
                res = await client.get(f"{api_base_url}/me")
            data = res.json() if res.content else {}
            return {
                "status": res.status_code,
                "ok": res.is_success,
                "email": data.get("email"),
                "detail": data.get("detail"),
            }
        except Exception as exc:
            return {
                "status": None,
                "ok": False,
                "email": None,
                "detail": str(exc),
            }


async def fetch_options_captures(
    ticker: str,
    gex_filter_preset: str = "All",
) -> list[dict[str, Any]]:
    captures = await _api_fetch_gex_captures(ticker, gex_filter_preset=gex_filter_preset)
    if not captures:
        raise OptionsDataFetchError(
            f"No options data was captured for ticker {ticker.upper()}."
        )
    return captures
