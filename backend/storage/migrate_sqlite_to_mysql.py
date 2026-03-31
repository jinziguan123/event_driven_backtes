from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from event_driven_backtest.backend.data.db_clients import close_safely, connect_mysql
from event_driven_backtest.backend.storage.result_store import ResultStore


def _read_sqlite_rows(sqlite_path: Path, table: str, columns: list[str]) -> list[dict]:
    if not sqlite_path.exists():
        raise FileNotFoundError(f'未找到 SQLite 文件: {sqlite_path}')
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(f"SELECT {', '.join(columns)} FROM {table}")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def migrate(sqlite_path: Path) -> dict[str, int]:
    ResultStore(db_backend='mysql')
    mysql_conn = connect_mysql()
    try:
        run_rows = _read_sqlite_rows(
            sqlite_path,
            'backtest_runs',
            ['run_id', 'name', 'strategy_name', 'status', 'params_json', 'error_message', 'created_at', 'started_at', 'finished_at'],
        )
        metric_rows = _read_sqlite_rows(
            sqlite_path,
            'backtest_metrics',
            ['run_id', 'total_return', 'annual_return', 'sharpe_ratio', 'max_drawdown', 'win_rate', 'trade_count', 'payload_json'],
        )
        artifact_rows = _read_sqlite_rows(
            sqlite_path,
            'backtest_artifacts',
            ['run_id', 'artifact_type', 'artifact_path'],
        )

        with mysql_conn.cursor() as cursor:
            if run_rows:
                cursor.executemany(
                    '''
                    INSERT INTO backtest_runs(run_id, name, strategy_name, status, params_json, error_message, created_at, started_at, finished_at)
                    VALUES(%(run_id)s, %(name)s, %(strategy_name)s, %(status)s, %(params_json)s, %(error_message)s, %(created_at)s, %(started_at)s, %(finished_at)s)
                    ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        strategy_name = VALUES(strategy_name),
                        status = VALUES(status),
                        params_json = VALUES(params_json),
                        error_message = VALUES(error_message),
                        started_at = VALUES(started_at),
                        finished_at = VALUES(finished_at)
                    ''',
                    run_rows,
                )

            if metric_rows:
                cursor.executemany(
                    '''
                    INSERT INTO backtest_metrics(run_id, total_return, annual_return, sharpe_ratio, max_drawdown, win_rate, trade_count, payload_json)
                    VALUES(%(run_id)s, %(total_return)s, %(annual_return)s, %(sharpe_ratio)s, %(max_drawdown)s, %(win_rate)s, %(trade_count)s, %(payload_json)s)
                    ON DUPLICATE KEY UPDATE
                        total_return = VALUES(total_return),
                        annual_return = VALUES(annual_return),
                        sharpe_ratio = VALUES(sharpe_ratio),
                        max_drawdown = VALUES(max_drawdown),
                        win_rate = VALUES(win_rate),
                        trade_count = VALUES(trade_count),
                        payload_json = VALUES(payload_json)
                    ''',
                    metric_rows,
                )

            if artifact_rows:
                cursor.executemany(
                    '''
                    INSERT INTO backtest_artifacts(run_id, artifact_type, artifact_path)
                    VALUES(%(run_id)s, %(artifact_type)s, %(artifact_path)s)
                    ON DUPLICATE KEY UPDATE artifact_path = VALUES(artifact_path)
                    ''',
                    artifact_rows,
                )

        mysql_conn.commit()
        return {
            'backtest_runs': len(run_rows),
            'backtest_metrics': len(metric_rows),
            'backtest_artifacts': len(artifact_rows),
        }
    except Exception:
        mysql_conn.rollback()
        raise
    finally:
        close_safely(mysql_conn)


def main() -> int:
    parser = argparse.ArgumentParser(description='将 event_driven_backtest 的 SQLite 回测元数据迁移到 MySQL')
    parser.add_argument(
        '--sqlite-path',
        default='event_driven_backtest/backend/storage/backtests.db',
        help='SQLite 文件路径，默认 event_driven_backtest/backend/storage/backtests.db',
    )
    args = parser.parse_args()

    summary = migrate(Path(args.sqlite_path))
    print(summary)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
