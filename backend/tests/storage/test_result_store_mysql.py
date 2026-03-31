from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from event_driven_backtest.backend.storage.result_store import ResultStore


class _FakeCursor:
    def __init__(self, connection):
        self._connection = connection
        self._fetchone = None
        self._fetchall = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self._connection.executed.append((sql, params))
        response = self._connection.pop_response()
        self._fetchone = response.get('fetchone')
        self._fetchall = response.get('fetchall', [])
        return int(response.get('rowcount', 0))

    def fetchone(self):
        return self._fetchone

    def fetchall(self):
        return self._fetchall


class _FakeConnection:
    def __init__(self, responses):
        self._responses = list(responses)
        self.executed = []
        self.closed = False
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return _FakeCursor(self)

    def pop_response(self):
        if self._responses:
            return self._responses.pop(0)
        return {}

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
        conn = self._connections[self._index]
        self._index += 1
        return conn


class ResultStoreMysqlTest(unittest.TestCase):
    def test_register_and_query_run_on_mysql_backend(self):
        conn_init = _FakeConnection(responses=[{}, {}, {}])
        conn_register = _FakeConnection(responses=[{}, {}])
        conn_list = _FakeConnection(
            responses=[
                {
                    'fetchall': [
                        {
                            'run_id': 'run_1',
                            'name': '测试回测',
                            'strategy_name': 'demo',
                            'status': 'RUNNING',
                            'params_json': '{}',
                            'created_at': None,
                            'started_at': None,
                            'finished_at': None,
                            'total_return': 0.0,
                            'annual_return': 0.0,
                            'sharpe_ratio': 0.0,
                            'max_drawdown': 0.0,
                            'win_rate': 0.0,
                            'trade_count': 0,
                        }
                    ]
                }
            ]
        )
        conn_get = _FakeConnection(
            responses=[
                {
                    'fetchone': {
                        'run_id': 'run_1',
                        'name': '测试回测',
                        'strategy_name': 'demo',
                        'status': 'RUNNING',
                        'params_json': '{}',
                        'created_at': None,
                        'started_at': None,
                        'finished_at': None,
                        'error_message': None,
                        'total_return': 0.0,
                        'annual_return': 0.0,
                        'sharpe_ratio': 0.0,
                        'max_drawdown': 0.0,
                        'win_rate': 0.0,
                        'trade_count': 0,
                    }
                }
            ]
        )
        factory = _Factory([conn_init, conn_register, conn_list, conn_get])

        with TemporaryDirectory() as temp_dir:
            store = ResultStore(
                base_dir=Path(temp_dir) / 'results',
                db_backend='mysql',
                mysql_connection_factory=factory,
            )
            store.register_run('run_1', name='测试回测', strategy_name='demo', status='RUNNING', params={})
            rows = store.list_runs()
            row = store.get_run_row('run_1')

        self.assertEqual(store.db_backend, 'mysql')
        self.assertEqual(rows[0]['run_id'], 'run_1')
        self.assertEqual(row['run_id'], 'run_1')
        self.assertTrue(conn_register.committed)
        self.assertTrue(conn_init.closed and conn_register.closed and conn_list.closed and conn_get.closed)


if __name__ == '__main__':
    unittest.main()
