from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import warnings

from event_driven_backtest.backend.storage import stock_pool_store
from event_driven_backtest.backend.storage.stock_pool_store import StockPoolStore


class _FakeCursor:
    def __init__(self, connection):
        self._connection = connection
        self._response = {}
        self.lastrowid = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self._connection.executed.append((sql, params))
        if not self._connection.responses:
            raise AssertionError('缺少预置 SQL 响应')
        response = self._connection.responses.pop(0)
        expect = response.get('sql_contains')
        if expect and expect not in sql:
            raise AssertionError(f'SQL 不符合预期: {sql}')
        self._response = response
        self.lastrowid = int(response.get('lastrowid', 0))
        return int(response.get('rowcount', 0))

    def fetchone(self):
        return self._response.get('fetchone')

    def fetchall(self):
        return self._response.get('fetchall', [])


class _FakeConnection:
    def __init__(self, responses):
        self.responses = list(responses)
        self.executed = []
        self.closed = False
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class _Factory:
    def __init__(self, connections):
        self._connections = list(connections)
        self._index = 0

    def __call__(self):
        if self._index >= len(self._connections):
            raise AssertionError('连接工厂调用次数超出预期')
        connection = self._connections[self._index]
        self._index += 1
        return connection


class StockPoolStoreMysqlTest(unittest.TestCase):
    def test_list_pools_mysql_backend(self):
        health_conn = _FakeConnection(
            responses=[
                {'sql_contains': 'SELECT 1', 'fetchone': {'1': 1}},
            ]
        )
        list_conn = _FakeConnection(
            responses=[
                {
                    'sql_contains': 'FROM stock_pool p',
                    'fetchall': [
                        {
                            'pool_id': 12,
                            'name': '核心池',
                            'description': '测试池',
                            'created_at': datetime(2026, 3, 19, 9, 30, 0),
                            'updated_at': datetime(2026, 3, 19, 10, 0, 0),
                            'symbol_count': 2,
                        }
                    ],
                }
            ]
        )
        store = StockPoolStore(
            backend='mysql',
            owner_key='default',
            mysql_connection_factory=_Factory([health_conn, list_conn]),
        )

        rows = store.list_pools()

        self.assertEqual(store.backend, 'mysql')
        self.assertEqual(rows[0]['pool_id'], '12')
        self.assertEqual(rows[0]['name'], '核心池')
        self.assertEqual(rows[0]['created_at'], '2026-03-19T09:30:00')
        self.assertTrue(health_conn.closed)
        self.assertTrue(list_conn.closed)

    def test_fallback_to_sqlite_when_mysql_unavailable(self):
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / 'fallback.db'

            def broken_factory():
                raise RuntimeError('mysql down')

            stock_pool_store._MYSQL_FALLBACK_WARNING_EMITTED = False
            original = os.environ.get('EVENT_BT_STOCK_POOL_ALLOW_SQLITE_FALLBACK')
            os.environ['EVENT_BT_STOCK_POOL_ALLOW_SQLITE_FALLBACK'] = '1'
            try:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always', RuntimeWarning)
                    store = StockPoolStore(
                        db_path=db_path,
                        backend='mysql',
                        mysql_connection_factory=broken_factory,
                    )
            finally:
                if original is None:
                    os.environ.pop('EVENT_BT_STOCK_POOL_ALLOW_SQLITE_FALLBACK', None)
                else:
                    os.environ['EVENT_BT_STOCK_POOL_ALLOW_SQLITE_FALLBACK'] = original

            self.assertEqual(store.backend, 'sqlite')
            self.assertTrue(any('自动回退 SQLite' in str(item.message) for item in caught))


if __name__ == '__main__':
    unittest.main()
