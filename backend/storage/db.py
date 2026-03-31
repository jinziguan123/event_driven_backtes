from __future__ import annotations

import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path('event_driven_backtest/backend/storage/backtests.db')


def connect_db(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    with connect_db(db_path) as conn:
        conn.executescript(
            '''
            CREATE TABLE IF NOT EXISTS backtest_runs (
                run_id TEXT PRIMARY KEY,
                name TEXT,
                strategy_name TEXT,
                status TEXT,
                params_json TEXT,
                error_message TEXT,
                created_at TEXT,
                started_at TEXT,
                finished_at TEXT
            );

            CREATE TABLE IF NOT EXISTS backtest_metrics (
                run_id TEXT PRIMARY KEY,
                total_return REAL,
                annual_return REAL,
                sharpe_ratio REAL,
                max_drawdown REAL,
                win_rate REAL,
                trade_count INTEGER,
                payload_json TEXT,
                FOREIGN KEY (run_id) REFERENCES backtest_runs(run_id)
            );

            CREATE TABLE IF NOT EXISTS backtest_artifacts (
                run_id TEXT,
                artifact_type TEXT,
                artifact_path TEXT,
                PRIMARY KEY (run_id, artifact_type),
                FOREIGN KEY (run_id) REFERENCES backtest_runs(run_id)
            );

            CREATE TABLE IF NOT EXISTS stock_pools (
                pool_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS stock_pool_symbols (
                pool_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (pool_id, symbol),
                FOREIGN KEY (pool_id) REFERENCES stock_pools(pool_id) ON DELETE CASCADE
            );
            '''
        )
