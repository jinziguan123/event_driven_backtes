from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import os

from fastapi.testclient import TestClient

os.environ['EVENT_BT_RESULT_DB_BACKEND'] = 'sqlite'
os.environ['EVENT_BT_STOCK_POOL_BACKEND'] = 'sqlite'

from event_driven_backtest.backend.api import server
from event_driven_backtest.backend.runner.service import BacktestService
from event_driven_backtest.backend.storage.result_store import ResultStore
from event_driven_backtest.backend.storage.stock_pool_store import StockPoolStore


class StockPoolApiTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        base_dir = Path(self.temp_dir.name) / 'results'
        db_path = Path(self.temp_dir.name) / 'backtests.db'
        store = ResultStore(base_dir=base_dir, db_path=db_path, db_backend='sqlite')
        pool_store = StockPoolStore(db_path=db_path, backend='sqlite')
        self.original_service = server.service
        server.service = BacktestService(store=store, stock_pool_store=pool_store)
        self.client = TestClient(server.app)

    def tearDown(self):
        server.service.wait_for_all_runs()
        server.service = self.original_service
        self.temp_dir.cleanup()

    def test_create_and_list_stock_pools(self):
        create_response = self.client.post(
            '/api/stock-pools',
            json={
                'name': '核心观察池',
                'description': '分钟策略观察池',
                'symbols': ['000001.SZ', '600519.SH'],
            },
        )
        self.assertEqual(create_response.status_code, 200)
        created = create_response.json()
        self.assertEqual(created['name'], '核心观察池')
        self.assertEqual(created['symbols'], ['000001.SZ', '600519.SH'])

        list_response = self.client.get('/api/stock-pools')
        self.assertEqual(list_response.status_code, 200)
        pools = list_response.json()
        self.assertEqual(len(pools), 1)
        self.assertEqual(pools[0]['symbol_count'], 2)

    def test_update_and_delete_stock_pool(self):
        created = self.client.post(
            '/api/stock-pools',
            json={
                'name': '待编辑股票池',
                'description': '',
                'symbols': ['000001.SZ'],
            },
        ).json()
        pool_id = created['pool_id']

        update_response = self.client.put(
            f'/api/stock-pools/{pool_id}',
            json={
                'name': '更新后股票池',
                'description': '已调整标的',
                'symbols': ['000001.SZ', '000002.SZ'],
            },
        )
        self.assertEqual(update_response.status_code, 200)
        updated = update_response.json()
        self.assertEqual(updated['name'], '更新后股票池')
        self.assertEqual(updated['symbols'], ['000001.SZ', '000002.SZ'])

        delete_response = self.client.delete(f'/api/stock-pools/{pool_id}')
        self.assertEqual(delete_response.status_code, 200)

        list_response = self.client.get('/api/stock-pools')
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json(), [])

    def test_list_stocks_returns_symbols_for_checkbox_selection(self):
        self.client.post(
            '/api/stock-pools',
            json={
                'name': '股票列表来源',
                'description': '用于测试股票勾选',
                'symbols': ['000001.SZ', '600519.SH', '300750.SZ'],
            },
        )

        response = self.client.get('/api/stocks?keyword=000&limit=20')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        symbols = {item['symbol'] for item in payload}
        self.assertIn('000001.SZ', symbols)
        self.assertNotIn('600519.SH', symbols)

    def test_list_stocks_page_supports_pagination(self):
        self.client.post(
            '/api/stock-pools',
            json={
                'name': '分页测试股票池',
                'description': '用于分页',
                'symbols': ['000001.SZ', '000002.SZ', '000003.SZ', '600519.SH'],
            },
        )

        response = self.client.get('/api/stocks/page?keyword=000&page=1&page_size=2')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['page'], 1)
        self.assertEqual(payload['page_size'], 2)
        self.assertEqual(payload['total'], 3)
        self.assertEqual(len(payload['items']), 2)


if __name__ == '__main__':
    unittest.main()
