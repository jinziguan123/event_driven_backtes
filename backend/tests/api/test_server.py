from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import os
from threading import Event, Thread

import pandas as pd
from fastapi.testclient import TestClient

os.environ['EVENT_BT_RESULT_DB_BACKEND'] = 'sqlite'
os.environ['EVENT_BT_STOCK_POOL_BACKEND'] = 'sqlite'

from event_driven_backtest.backend.api import server
from event_driven_backtest.backend.runner.service import BacktestService
from event_driven_backtest.backend.storage.result_store import ResultStore
from event_driven_backtest.backend.storage.stock_pool_store import StockPoolStore


class ApiServerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        base_dir = Path(self.temp_dir.name) / 'results'
        db_path = Path(self.temp_dir.name) / 'backtests.db'
        store = ResultStore(base_dir=base_dir, db_path=db_path, db_backend='sqlite')
        pool_store = StockPoolStore(db_path=db_path, backend='sqlite')
        self.original_service = server.service
        server.service = BacktestService(store=store, stock_pool_store=pool_store)
        self.client = TestClient(server.app)
        self.store = store

    def tearDown(self):
        server.service.wait_for_all_runs()
        server.service = self.original_service
        self.temp_dir.cleanup()

    def test_list_backtests_returns_200(self):
        response = self.client.get('/api/backtests')
        self.assertEqual(response.status_code, 200)

    def test_list_strategies_returns_python_files(self):
        response = self.client.get('/api/strategies')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        names = {item['name'] for item in payload}
        self.assertIn('demo_buy_hold', names)
        self.assertIn('minute_sma_5_20', names)

    def test_create_backtest_returns_running_status_immediately(self):
        payload = {
            'name': '双均线分钟回测',
            'strategy_name': 'minute_sma_5_20',
            'strategy_path': 'event_driven_backtest/backend/strategies/minute_sma_5_20.py',
            'symbols': ['000001.SZ'],
            'initial_cash': 1000000,
            'bar_frequency': '1m',
            'benchmark': '000300.SH',
        }
        create_response = self.client.post('/api/backtests', json=payload)
        self.assertEqual(create_response.status_code, 200)
        body = create_response.json()
        self.assertIn('run_id', body)
        self.assertEqual(body['status'], 'RUNNING')

    def test_stream_endpoint_returns_event_stream_snapshot(self):
        payload = {
            'name': '双均线分钟回测',
            'strategy_name': 'minute_sma_5_20',
            'strategy_path': 'event_driven_backtest/backend/strategies/minute_sma_5_20.py',
            'symbols': ['000001.SZ'],
            'initial_cash': 1000000,
            'bar_frequency': '1m',
            'benchmark': '000300.SH',
        }
        run_id = self.client.post('/api/backtests', json=payload).json()['run_id']

        with self.client.stream('GET', f'/api/backtests/{run_id}/stream') as response:
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.headers['content-type'].startswith('text/event-stream'))
            lines = []
            for line in response.iter_lines():
                if line:
                    lines.append(line)
                if len(lines) >= 2:
                    break
        self.assertTrue(any('event: snapshot' in line for line in lines))

    def test_trades_endpoint_supports_daily_aggregation(self):
        run_id = self.store.create_run_directory()
        self.store.register_run(run_id, name='聚合测试', strategy_name='test_strategy', status='SUCCESS', params={'symbols': ['000001.SZ']})
        trades = pd.DataFrame(
            [
                {'timestamp': '2026-03-10T09:31:00', 'symbol': '000001.SZ', 'side': 'BUY', 'quantity': 100, 'price': 10.0, 'commission': 1.0, 'stamp_duty': 0.0, 'pnl': 0.0},
                {'timestamp': '2026-03-10T14:31:00', 'symbol': '000001.SZ', 'side': 'SELL', 'quantity': 100, 'price': 10.8, 'commission': 1.0, 'stamp_duty': 1.08, 'pnl': 77.92},
                {'timestamp': '2026-03-11T10:01:00', 'symbol': '000001.SZ', 'side': 'BUY', 'quantity': 200, 'price': 11.0, 'commission': 2.0, 'stamp_duty': 0.0, 'pnl': 0.0},
            ]
        )
        self.store.save_dataframe(run_id, 'trades', trades)

        response = self.client.get(f'/api/backtests/{run_id}/trades?granularity=day')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0]['date'], '2026-03-10')
        self.assertEqual(payload[0]['buy_count'], 1)
        self.assertEqual(payload[0]['sell_count'], 1)
        self.assertAlmostEqual(payload[0]['realized_pnl'], 77.92)

    def test_positions_endpoint_supports_daily_aggregation(self):
        run_id = self.store.create_run_directory()
        self.store.register_run(run_id, name='持仓聚合测试', strategy_name='test_strategy', status='SUCCESS', params={'symbols': ['000001.SZ']})
        positions = pd.DataFrame(
            [
                {'timestamp': '2026-03-10T10:00:00', 'symbol': '000001.SZ', 'quantity': 100, 'sellable_quantity': 0, 'avg_cost': 10.0, 'market_value': 1005.0, 'unrealized_pnl': 5.0},
                {'timestamp': '2026-03-10T14:59:00', 'symbol': '000001.SZ', 'quantity': 100, 'sellable_quantity': 100, 'avg_cost': 10.0, 'market_value': 1080.0, 'unrealized_pnl': 80.0},
                {'timestamp': '2026-03-11T14:59:00', 'symbol': '000001.SZ', 'quantity': 200, 'sellable_quantity': 200, 'avg_cost': 11.0, 'market_value': 2240.0, 'unrealized_pnl': 40.0},
            ]
        )
        self.store.save_dataframe(run_id, 'positions', positions)

        response = self.client.get(f'/api/backtests/{run_id}/positions?granularity=day')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0]['date'], '2026-03-10')
        self.assertEqual(payload[0]['position_symbol_count'], 1)
        self.assertEqual(payload[0]['total_market_value'], 1080.0)
        self.assertEqual(payload[0]['total_unrealized_pnl'], 80.0)

    def test_cancel_running_backtest_returns_canceling(self):
        run_id = self.store.create_run_directory()
        self.store.register_run(run_id, name='可中断回测', strategy_name='demo', status='RUNNING', params={'symbols': ['000001.SZ']})
        self.store.mark_running(run_id)

        blocker = Event()
        thread = Thread(target=lambda: blocker.wait(2), daemon=True)
        thread.start()
        server.service._threads[run_id] = thread
        server.service._cancel_flags[run_id] = Event()

        response = self.client.post(f'/api/backtests/{run_id}/cancel')

        blocker.set()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['accepted'])
        self.assertEqual(payload['status'], 'CANCELING')
        self.assertTrue(server.service._cancel_flags[run_id].is_set())

    def test_delete_backtest_removes_metadata_and_artifacts(self):
        run_id = self.store.create_run_directory()
        self.store.register_run(run_id, name='删除测试', strategy_name='demo', status='SUCCESS', params={'symbols': ['000001.SZ']})
        self.store.save_logs(run_id, [{'timestamp': '2026-03-20T10:00:00', 'level': 'INFO', 'message': 'test'}])

        response = self.client.delete(f'/api/backtests/{run_id}')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['deleted'])
        self.assertIsNone(self.store.get_run_row(run_id))
        self.assertFalse((self.store.base_dir / run_id).exists())

    def test_delete_running_backtest_returns_409(self):
        run_id = self.store.create_run_directory()
        self.store.register_run(run_id, name='运行中删除测试', strategy_name='demo', status='RUNNING', params={'symbols': ['000001.SZ']})
        self.store.mark_running(run_id)

        blocker = Event()
        thread = Thread(target=lambda: blocker.wait(2), daemon=True)
        thread.start()
        server.service._threads[run_id] = thread

        response = self.client.delete(f'/api/backtests/{run_id}')

        blocker.set()
        self.assertEqual(response.status_code, 409)

    def test_get_backtest_profile_returns_stage_timings(self):
        run_id = self.store.create_run_directory()
        self.store.register_run(run_id, name='画像测试', strategy_name='demo', status='SUCCESS', params={'symbols': ['000001.SZ']})
        self.store.save_summary(
            run_id,
            {
                'run_id': run_id,
                'strategy_name': 'demo',
                'metrics': {},
                'config': {'symbols': ['000001.SZ']},
                'max_drawdown_window': {},
                'profile': {
                    'data_load_seconds': 0.12,
                    'engine_run_seconds': 0.34,
                    'persist_seconds': 0.05,
                    'total_seconds': 0.51,
                },
            },
        )

        response = self.client.get(f'/api/backtests/{run_id}/profile')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['run_id'], run_id)
        self.assertIn('total_seconds', payload['profile'])


if __name__ == '__main__':
    unittest.main()
