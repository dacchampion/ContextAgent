from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from services.options_data import create_job_run, persist_gex_snapshot


def test_persist_gex_snapshot_and_job_run():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE symbols (symbol_id INTEGER PRIMARY KEY, symbol TEXT UNIQUE NOT NULL)"))
        conn.execute(
            text(
                """
                CREATE TABLE gex_snapshots (
                    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol_id INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    snapshot_utc DATETIME NOT NULL,
                    zero_gamma_level REAL NULL,
                    dealer_cluster_upper REAL NULL,
                    dealer_cluster_lower REAL NULL,
                    dealer_cluster_upper_range_start REAL NULL,
                    dealer_cluster_lower_range_start REAL NULL,
                    gex_map JSON NOT NULL,
                    created_utc DATETIME NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE job_runs (
                    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_name TEXT NOT NULL,
                    symbol_id INTEGER NULL,
                    candle_width TEXT NULL,
                    started_utc DATETIME NOT NULL,
                    finished_utc DATETIME NULL,
                    run_status TEXT NOT NULL,
                    rows_affected INTEGER NULL,
                    log_message TEXT NULL
                )
                """
            )
        )
        conn.execute(text("INSERT INTO symbols(symbol_id, symbol) VALUES (1, 'SPY')"))

    payload = {
        "ticker": "SPY",
        "zero_gamma_level": 512.25,
        "dealer_cluster_upper": 515.0,
        "dealer_cluster_lower": 508.0,
        "dealer_cluster_upper_range_start": 520.0,
        "dealer_cluster_lower_range_start": 500.0,
        "gex_map": {"510": {"net_gamma_exposure": 123.0}},
    }

    with Session(engine) as session:
        snapshot = persist_gex_snapshot(
            session,
            symbol_id=1,
            payload=payload,
            snapshot_utc=datetime(2026, 3, 31, 12, 0, 0),
        )
        job = create_job_run(
            session,
            job_name="gex_options_data",
            symbol_id=1,
            run_status="success",
            rows_affected=1,
            log_message=f"snapshot_id={snapshot.snapshot_id}",
            finished_utc=datetime(2026, 3, 31, 12, 0, 1),
        )
        session.commit()

        assert snapshot.snapshot_id == 1
        assert snapshot.zero_gamma_level == payload["zero_gamma_level"]
        assert snapshot.dealer_cluster_upper == payload["dealer_cluster_upper"]
        assert snapshot.dealer_cluster_lower == payload["dealer_cluster_lower"]
        assert snapshot.dealer_cluster_upper_range_start == payload["dealer_cluster_upper_range_start"]
        assert snapshot.dealer_cluster_lower_range_start == payload["dealer_cluster_lower_range_start"]
        assert snapshot.gex_map == payload["gex_map"]
        assert job.job_id == 1
        assert job.run_status == "success"
