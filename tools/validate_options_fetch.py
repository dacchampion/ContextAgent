from __future__ import annotations

import argparse
import asyncio
import json
import sys
import traceback
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
BACKEND_DIR = THIS_FILE.parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from services.options_data import (  # noqa: E402
    OptionsDataError,
    fetch_options_captures,
    parse_gex_payloads,
    validate_options_session,
    validate_gex_payload,
)


async def _run(
    symbol: str,
    output_path: str | None,
    parsed_only: bool,
    gex_filter_preset: str,
) -> int:
    session_check = await validate_options_session()
    if not session_check["ok"]:
        result = {"ok": False, "session": session_check}
        if output_path:
            Path(output_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 2

    captures = await fetch_options_captures(symbol, gex_filter_preset=gex_filter_preset)
    parsed = parse_gex_payloads(ticker=symbol, captures=captures)
    validation = validate_gex_payload(parsed, captures=captures)

    report = {
        "ticker": symbol.upper(),
        "session": session_check,
        "validation": validation,
        "parsed": parsed,
    }
    output_payload = parsed if parsed_only else report

    if output_path:
        Path(output_path).write_text(json.dumps(output_payload, indent=2), encoding="utf-8")

    print(json.dumps(output_payload, indent=2))
    return 0 if validation["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a live options data fetch and validate whether the expected GEX content was returned."
    )
    parser.add_argument("--symbol", required=True, help="Ticker to fetch, for example SPY")
    parser.add_argument(
        "--output",
        help="Optional path to write the JSON output.",
    )
    parser.add_argument(
        "--parsed-only",
        action="store_true",
        help="Print only the parsed payload instead of the full validation report.",
    )
    parser.add_argument(
        "--gex-filter-preset",
        default="All",
        help="GEX filter preset: All, 0DTE, ThisWeek, Next2Weeks, OpExCycle, or Next2OpEx.",
    )
    parser.add_argument(
        "--traceback",
        action="store_true",
        help="Print the full traceback when the fetch fails.",
    )
    parser.add_argument(
        "--storage-state",
        help="Optional Playwright storage_state JSON file for an already authenticated session.",
    )
    args = parser.parse_args()

    try:
        from app.core.config import settings

        if args.storage_state:
            settings.OPTIONS_STORAGE_STATE_PATH = args.storage_state
        return asyncio.run(
            _run(
                symbol=args.symbol.upper(),
                output_path=args.output,
                parsed_only=args.parsed_only,
                gex_filter_preset=args.gex_filter_preset,
            )
        )
    except OptionsDataError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        if args.traceback:
            traceback.print_exc()
        return 2
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                indent=2,
            )
        )
        if args.traceback:
            traceback.print_exc()
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
