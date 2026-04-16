import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

from etl.utils import get_session, get_symbol_id
from services.options_data import (
    OptionsDataError,
    create_job_run,
    fetch_options_gex,
    persist_gex_snapshot,
)


logger = logging.getLogger("gex_snapshot")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.DEBUG if os.getenv("GEX_SNAPSHOT_LOG") else logging.INFO)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument(
        "--gex-filter-preset",
        default="All",
        help="GoF GEX filter preset: All, 0DTE, ThisWeek, Next2Weeks, OpExCycle, or Next2OpEx.",
    )
    args = ap.parse_args()

    symbol = args.symbol.upper()
    logger.info(f"[gex_snapshot] start | symbol={symbol}")

    with get_session() as session:
        symbol_id = get_symbol_id(session, symbol)
        job = create_job_run(
            session,
            job_name="gex_options_data",
            symbol_id=symbol_id,
            run_status="warning",
            log_message="running",
        )
        session.commit()

        try:
            payload = asyncio.run(
                fetch_options_gex(
                    ticker=symbol,
                    gex_filter_preset=args.gex_filter_preset,
                )
            )
            snapshot = persist_gex_snapshot(session, symbol_id=symbol_id, payload=payload)
            job.finished_utc = _utc_now_naive()
            job.run_status = "success"
            job.rows_affected = len(payload.get("gex_map") or [])
            job.log_message = f"snapshot_id={snapshot.snapshot_id}"
            session.add(job)
            session.commit()
            logger.info(
                "[gex_snapshot] done | symbol=%s snapshot_id=%s rows=%s",
                symbol,
                snapshot.snapshot_id,
                job.rows_affected,
            )
        except OptionsDataError as exc:
            session.rollback()
            job.finished_utc = _utc_now_naive()
            job.run_status = "error"
            job.rows_affected = 0
            job.log_message = str(exc)
            session.add(job)
            session.commit()
            logger.exception("[gex_snapshot] failed | symbol=%s error=%s", symbol, exc)
            raise
        except Exception as exc:
            session.rollback()
            job.finished_utc = _utc_now_naive()
            job.run_status = "error"
            job.rows_affected = 0
            job.log_message = f"Unexpected error: {exc}"
            session.add(job)
            session.commit()
            logger.exception("[gex_snapshot] failed | symbol=%s error=%s", symbol, exc)
            raise


if __name__ == "__main__":
    main()
