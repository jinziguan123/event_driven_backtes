from __future__ import annotations

from datetime import date
import unittest

from event_driven_backtest.backend.data.clickhouse_loader import ClickHouseMinuteBarLoader, normalize_symbol


class _FakeMysqlCursor:
    def __init__(self, connection):
        self._connection = connection

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params):
        self._connection.last_sql = sql
        self._connection.last_params = params

    def fetchall(self):
        return self._connection.rows


class _FakeMysqlConnection:
    def __init__(self, rows):
        self.rows = rows
        self.last_sql = ''
        self.last_params = ()
        self.closed = False

    def cursor(self):
        return _FakeMysqlCursor(self)

    def close(self):
        self.closed = True


class _FakeQueryResult:
    def __init__(self, rows, columns):
        self.result_rows = rows
        self.column_names = columns


class _FakeClickHouseClient:
    def __init__(self, rows, columns):
        self.rows = rows
        self.columns = columns
        self.last_sql = ''
        self.last_params = {}
        self.closed = False

    def query(self, sql, parameters):
        self.last_sql = sql
        self.last_params = parameters
        return _FakeQueryResult(self.rows, self.columns)

    def close(self):
        self.closed = True


class ClickHouseMinuteBarLoaderTest(unittest.TestCase):
    def test_normalize_symbol_auto_append_market_suffix(self):
        self.assertEqual(normalize_symbol('600000'), '600000.SH')
        self.assertEqual(normalize_symbol('000001'), '000001.SZ')
        self.assertEqual(normalize_symbol('430001'), '430001.BJ')

    def test_load_symbol_minutes_returns_frame_with_datetime_index(self):
        mysql_conn = _FakeMysqlConnection([{'symbol': '000001.SZ', 'symbol_id': 1}])
        ch_client = _FakeClickHouseClient(
            rows=[
                (date(2026, 1, 2), 571, 10.0, 10.2, 9.9, 10.1, 1200, 345),
                (date(2026, 1, 2), 572, 10.1, 10.3, 10.0, 10.2, 1500, 400),
            ],
            columns=['trade_date', 'minute_slot', 'open', 'high', 'low', 'close', 'volume', 'amount_k'],
        )
        loader = ClickHouseMinuteBarLoader(
            clickhouse_client_factory=lambda: ch_client,
            mysql_connection_factory=lambda: mysql_conn,
        )

        frame = loader.load_symbol_minutes(
            symbol='000001.SZ',
            start_datetime='2026-01-02 09:31:00',
            end_datetime='2026-01-02 09:32:00',
        )

        self.assertEqual(list(frame.columns), ['open', 'high', 'low', 'close', 'volume', 'amount'])
        self.assertEqual(frame.index.name, 'datetime')
        self.assertEqual(frame.index[0].isoformat(), '2026-01-02T09:31:00')
        self.assertAlmostEqual(float(frame.iloc[0]['amount']), 345000.0)
        self.assertTrue(mysql_conn.closed)
        self.assertTrue(ch_client.closed)
        self.assertIn('start_slot', ch_client.last_params)
        self.assertIn('end_slot', ch_client.last_params)
        self.assertEqual(ch_client.last_params['start_slot'], 571)
        self.assertEqual(ch_client.last_params['end_slot'], 572)

    def test_load_symbol_minutes_returns_empty_when_symbol_not_found(self):
        mysql_conn = _FakeMysqlConnection([])
        ch_client = _FakeClickHouseClient(rows=[], columns=[])
        loader = ClickHouseMinuteBarLoader(
            clickhouse_client_factory=lambda: ch_client,
            mysql_connection_factory=lambda: mysql_conn,
        )

        frame = loader.load_symbol_minutes(symbol='000001.SZ')
        self.assertTrue(frame.empty)
        self.assertEqual(list(frame.columns), ['open', 'high', 'low', 'close', 'volume', 'amount'])
        self.assertEqual(ch_client.last_sql, '')


if __name__ == '__main__':
    unittest.main()
