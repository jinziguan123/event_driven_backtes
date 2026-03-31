from __future__ import annotations

import json
from datetime import datetime
import os
from pathlib import Path
import shutil
from uuid import uuid4
import warnings

import pandas as pd

from event_driven_backtest.backend.data.db_clients import close_safely, connect_mysql

from .db import DEFAULT_DB_PATH, connect_db as connect_sqlite_db
from .db import init_db as init_sqlite_db

_RESULT_DB_FALLBACK_WARNING_EMITTED = False

MYSQL_RESULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS backtest_runs (
    run_id VARCHAR(64) NOT NULL,
    name VARCHAR(255) NULL,
    strategy_name VARCHAR(255) NULL,
    status VARCHAR(32) NOT NULL,
    params_json LONGTEXT NULL,
    error_message TEXT NULL,
    created_at DATETIME(6) NOT NULL,
    started_at DATETIME(6) NULL,
    finished_at DATETIME(6) NULL,
    PRIMARY KEY (run_id),
    KEY idx_created_at (created_at),
    KEY idx_status_created_at (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS backtest_metrics (
    run_id VARCHAR(64) NOT NULL,
    total_return DOUBLE NOT NULL DEFAULT 0,
    annual_return DOUBLE NOT NULL DEFAULT 0,
    sharpe_ratio DOUBLE NOT NULL DEFAULT 0,
    max_drawdown DOUBLE NOT NULL DEFAULT 0,
    win_rate DOUBLE NOT NULL DEFAULT 0,
    trade_count INT NOT NULL DEFAULT 0,
    payload_json LONGTEXT NULL,
    PRIMARY KEY (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS backtest_artifacts (
    run_id VARCHAR(64) NOT NULL,
    artifact_type VARCHAR(64) NOT NULL,
    artifact_path VARCHAR(500) NOT NULL,
    PRIMARY KEY (run_id, artifact_type),
    KEY idx_run_id (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
""".strip()


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _normalize_backend(value: str | None) -> str:
    backend = (value or os.environ.get('EVENT_BT_RESULT_DB_BACKEND', 'mysql')).strip().lower()
    if backend not in {'mysql', 'sqlite'}:
        raise ValueError(f'不支持的回测存储后端: {backend}')
    return backend


class ResultStore:
    def __init__(
        self,
        base_dir: str | Path = 'event_driven_backtest/backend/storage/results',
        db_path: str | Path = DEFAULT_DB_PATH,
        db_backend: str | None = None,
        mysql_connection_factory=None,
    ):
        self.base_dir = Path(base_dir)
        self.db_path = Path(db_path)
        self.db_backend = _normalize_backend(db_backend)
        self._mysql_connection_factory = mysql_connection_factory or connect_mysql
        self.base_dir.mkdir(parents=True, exist_ok=True)

        if self.db_backend == 'mysql':
            try:
                self._init_mysql_schema()
            except Exception as exc:
                allow_fallback = _to_bool(
                    os.environ.get('EVENT_BT_RESULT_DB_ALLOW_SQLITE_FALLBACK'),
                    default=False,
                )
                if not allow_fallback:
                    raise RuntimeError('MySQL 回测元数据存储不可用，且未允许 SQLite 回退') from exc
                global _RESULT_DB_FALLBACK_WARNING_EMITTED
                if not _RESULT_DB_FALLBACK_WARNING_EMITTED:
                    warnings.warn(
                        f'MySQL 回测元数据存储不可用，已自动回退 SQLite: {exc}',
                        RuntimeWarning,
                        stacklevel=2,
                    )
                    _RESULT_DB_FALLBACK_WARNING_EMITTED = True
                self.db_backend = 'sqlite'

        if self.db_backend == 'sqlite':
            init_sqlite_db(self.db_path)

    def _get_mysql_connection(self):
        return self._mysql_connection_factory()

    def _init_mysql_schema(self) -> None:
        connection = self._get_mysql_connection()
        try:
            with connection.cursor() as cursor:
                for statement in [item.strip() for item in MYSQL_RESULT_SCHEMA.split(';') if item.strip()]:
                    cursor.execute(statement)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            close_safely(connection)

    @staticmethod
    def _row_to_dict(row) -> dict:
        if row is None:
            return {}
        if isinstance(row, dict):
            return dict(row)
        return dict(row)

    def create_run_directory(self) -> str:
        run_id = datetime.now().strftime('%Y%m%d%H%M%S') + '_' + uuid4().hex[:8]
        (self.base_dir / run_id).mkdir(parents=True, exist_ok=True)
        return run_id

    def register_run(
        self,
        run_id: str,
        name: str = '',
        strategy_name: str = '',
        status: str = 'PENDING',
        params: dict | None = None,
        error_message: str | None = None,
    ) -> None:
        params_json = json.dumps(params or {}, ensure_ascii=False)
        if self.db_backend == 'mysql':
            now = datetime.now()
            connection = self._get_mysql_connection()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        '''
                        INSERT INTO backtest_runs(run_id, created_at, status)
                        VALUES(%s, %s, %s)
                        ON DUPLICATE KEY UPDATE run_id = run_id
                        ''',
                        (run_id, now, status),
                    )
                    cursor.execute(
                        '''
                        UPDATE backtest_runs
                        SET name = %s,
                            strategy_name = %s,
                            status = %s,
                            params_json = %s,
                            error_message = %s
                        WHERE run_id = %s
                        ''',
                        (name, strategy_name, status, params_json, error_message, run_id),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                close_safely(connection)
            return

        with connect_sqlite_db(self.db_path) as conn:
            conn.execute(
                '''
                INSERT OR REPLACE INTO backtest_runs(run_id, name, strategy_name, status, params_json, error_message, created_at)
                VALUES(?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM backtest_runs WHERE run_id = ?), ?))
                ''',
                (run_id, name, strategy_name, status, params_json, error_message, run_id, datetime.now().isoformat()),
            )
            conn.commit()

    def mark_running(self, run_id: str) -> None:
        if self.db_backend == 'mysql':
            now = datetime.now()
            connection = self._get_mysql_connection()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        '''
                        UPDATE backtest_runs
                        SET status = %s, error_message = NULL, started_at = COALESCE(started_at, %s), finished_at = NULL
                        WHERE run_id = %s
                        ''',
                        ('RUNNING', now, run_id),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                close_safely(connection)
            return

        now = datetime.now().isoformat()
        with connect_sqlite_db(self.db_path) as conn:
            conn.execute(
                '''
                UPDATE backtest_runs
                SET status = ?, error_message = NULL, started_at = COALESCE(started_at, ?), finished_at = NULL
                WHERE run_id = ?
                ''',
                ('RUNNING', now, run_id),
            )
            conn.commit()

    def update_status(self, run_id: str, status: str, error_message: str | None = None) -> None:
        if self.db_backend == 'mysql':
            finished_at = datetime.now() if status in {'SUCCESS', 'FAILED'} else None
            connection = self._get_mysql_connection()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        'UPDATE backtest_runs SET status = %s, error_message = %s, finished_at = %s WHERE run_id = %s',
                        (status, error_message, finished_at, run_id),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                close_safely(connection)
            return

        finished_at = datetime.now().isoformat() if status in {'SUCCESS', 'FAILED'} else None
        with connect_sqlite_db(self.db_path) as conn:
            conn.execute(
                'UPDATE backtest_runs SET status = ?, error_message = ?, finished_at = ? WHERE run_id = ?',
                (status, error_message, finished_at, run_id),
            )
            conn.commit()

    def save_json(self, run_id: str, artifact_type: str, payload: dict) -> Path:
        path = self.base_dir / run_id / f'{artifact_type}.json'
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        self._register_artifact(run_id, artifact_type, path)
        return path

    def save_summary(self, run_id: str, summary: dict) -> Path:
        return self.save_json(run_id, 'summary', summary)

    def save_metrics(self, run_id: str, metrics: dict) -> None:
        payload_json = json.dumps(metrics, ensure_ascii=False)
        values = (
            run_id,
            metrics.get('total_return', 0.0),
            metrics.get('annual_return', 0.0),
            metrics.get('sharpe_ratio', 0.0),
            metrics.get('max_drawdown', 0.0),
            metrics.get('win_rate', 0.0),
            metrics.get('trade_count', 0),
            payload_json,
        )
        if self.db_backend == 'mysql':
            connection = self._get_mysql_connection()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        '''
                        INSERT INTO backtest_metrics(run_id, total_return, annual_return, sharpe_ratio, max_drawdown, win_rate, trade_count, payload_json)
                        VALUES(%s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            total_return = VALUES(total_return),
                            annual_return = VALUES(annual_return),
                            sharpe_ratio = VALUES(sharpe_ratio),
                            max_drawdown = VALUES(max_drawdown),
                            win_rate = VALUES(win_rate),
                            trade_count = VALUES(trade_count),
                            payload_json = VALUES(payload_json)
                        ''',
                        values,
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                close_safely(connection)
            return

        with connect_sqlite_db(self.db_path) as conn:
            conn.execute(
                '''
                INSERT OR REPLACE INTO backtest_metrics(run_id, total_return, annual_return, sharpe_ratio, max_drawdown, win_rate, trade_count, payload_json)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                values,
            )
            conn.commit()

    def save_dataframe(self, run_id: str, artifact_type: str, frame: pd.DataFrame) -> Path:
        path = self.base_dir / run_id / f'{artifact_type}.parquet'
        frame.to_parquet(path, index=True)
        self._register_artifact(run_id, artifact_type, path)
        return path

    def save_logs(self, run_id: str, logs: list[dict]) -> Path:
        path = self.base_dir / run_id / 'logs.jsonl'
        content = '\n'.join(json.dumps(item, ensure_ascii=False) for item in logs)
        if content:
            content += '\n'
        path.write_text(content, encoding='utf-8')
        self._register_artifact(run_id, 'logs', path)
        return path

    def load_dataframe(self, run_id: str, artifact_type: str) -> pd.DataFrame:
        path = self.base_dir / run_id / f'{artifact_type}.parquet'
        if not path.exists():
            return pd.DataFrame()
        return pd.read_parquet(path)

    def load_summary(self, run_id: str) -> dict:
        path = self.base_dir / run_id / 'summary.json'
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding='utf-8'))

    def load_logs(self, run_id: str) -> list[dict]:
        path = self.base_dir / run_id / 'logs.jsonl'
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]

    def get_metrics(self, run_id: str) -> dict:
        row = None
        if self.db_backend == 'mysql':
            connection = self._get_mysql_connection()
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT payload_json FROM backtest_metrics WHERE run_id = %s', (run_id,))
                    row = cursor.fetchone()
            finally:
                close_safely(connection)
        else:
            with connect_sqlite_db(self.db_path) as conn:
                row = conn.execute('SELECT payload_json FROM backtest_metrics WHERE run_id = ?', (run_id,)).fetchone()
        if row is None or not self._row_to_dict(row).get('payload_json'):
            return {}
        return json.loads(self._row_to_dict(row)['payload_json'])

    def _register_artifact(self, run_id: str, artifact_type: str, path: Path) -> None:
        if self.db_backend == 'mysql':
            connection = self._get_mysql_connection()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        '''
                        INSERT INTO backtest_artifacts(run_id, artifact_type, artifact_path)
                        VALUES(%s, %s, %s)
                        ON DUPLICATE KEY UPDATE artifact_path = VALUES(artifact_path)
                        ''',
                        (run_id, artifact_type, str(path)),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                close_safely(connection)
            return

        with connect_sqlite_db(self.db_path) as conn:
            conn.execute(
                'INSERT OR REPLACE INTO backtest_artifacts(run_id, artifact_type, artifact_path) VALUES(?, ?, ?)',
                (run_id, artifact_type, str(path)),
            )
            conn.commit()

    def list_runs(self) -> list[dict]:
        query = '''
            SELECT r.run_id, r.name, r.strategy_name, r.status, r.params_json, r.created_at, r.started_at, r.finished_at,
                   m.total_return, m.annual_return, m.sharpe_ratio, m.max_drawdown, m.win_rate, m.trade_count
            FROM backtest_runs r
            LEFT JOIN backtest_metrics m ON r.run_id = m.run_id
            ORDER BY r.created_at DESC
        '''
        if self.db_backend == 'mysql':
            connection = self._get_mysql_connection()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    rows = cursor.fetchall() or []
                return [self._row_to_dict(row) for row in rows]
            finally:
                close_safely(connection)

        with connect_sqlite_db(self.db_path) as conn:
            rows = conn.execute(query).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_run_row(self, run_id: str) -> dict | None:
        query = '''
            SELECT r.run_id, r.name, r.strategy_name, r.status, r.params_json, r.created_at, r.started_at, r.finished_at, r.error_message,
                   m.total_return, m.annual_return, m.sharpe_ratio, m.max_drawdown, m.win_rate, m.trade_count
            FROM backtest_runs r
            LEFT JOIN backtest_metrics m ON r.run_id = m.run_id
            WHERE r.run_id = {placeholder}
        '''
        if self.db_backend == 'mysql':
            connection = self._get_mysql_connection()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(query.format(placeholder='%s'), (run_id,))
                    row = cursor.fetchone()
                return None if row is None else self._row_to_dict(row)
            finally:
                close_safely(connection)

        with connect_sqlite_db(self.db_path) as conn:
            row = conn.execute(query.format(placeholder='?'), (run_id,)).fetchone()
        return None if row is None else self._row_to_dict(row)

    def _delete_run_directory(self, run_id: str) -> None:
        run_dir = (self.base_dir / run_id).resolve()
        base_dir = self.base_dir.resolve()
        if base_dir not in run_dir.parents:
            return
        if run_dir.exists():
            shutil.rmtree(run_dir, ignore_errors=True)

    def delete_run(self, run_id: str) -> bool:
        if self.db_backend == 'mysql':
            connection = self._get_mysql_connection()
            try:
                with connection.cursor() as cursor:
                    cursor.execute('DELETE FROM backtest_metrics WHERE run_id = %s', (run_id,))
                    cursor.execute('DELETE FROM backtest_artifacts WHERE run_id = %s', (run_id,))
                    affected = cursor.execute('DELETE FROM backtest_runs WHERE run_id = %s', (run_id,))
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                close_safely(connection)
            deleted = affected > 0
            if deleted:
                self._delete_run_directory(run_id)
            return deleted

        with connect_sqlite_db(self.db_path) as conn:
            conn.execute('DELETE FROM backtest_metrics WHERE run_id = ?', (run_id,))
            conn.execute('DELETE FROM backtest_artifacts WHERE run_id = ?', (run_id,))
            cursor = conn.execute('DELETE FROM backtest_runs WHERE run_id = ?', (run_id,))
            conn.commit()

        deleted = cursor.rowcount > 0
        if deleted:
            self._delete_run_directory(run_id)
        return deleted
