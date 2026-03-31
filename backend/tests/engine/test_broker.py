from datetime import datetime
import unittest

from event_driven_backtest.backend.core.config import BacktestConfig
from event_driven_backtest.backend.engine.broker import Broker


class BrokerTest(unittest.TestCase):
    def test_buy_order_reduces_cash_after_fill(self):
        broker = Broker(BacktestConfig(symbols=['000001.SZ'], initial_cash=10000))
        broker.buy(symbol='000001.SZ', price=10, quantity=100, timestamp=datetime(2026, 1, 2, 9, 35))
        self.assertLess(broker.account.cash, 10000)

    def test_t_plus_one_blocks_same_day_sell(self):
        broker = Broker(BacktestConfig(symbols=['000001.SZ'], initial_cash=10000))
        timestamp = datetime(2026, 1, 2, 9, 35)
        broker.buy(symbol='000001.SZ', price=10, quantity=100, timestamp=timestamp)
        rejected = broker.sell(symbol='000001.SZ', price=10, quantity=100, timestamp=timestamp)
        self.assertEqual(rejected.status.value, 'REJECTED')

    def test_max_positions_rejects_new_symbol_buy(self):
        broker = Broker(BacktestConfig(symbols=['000001.SZ', '000002.SZ'], initial_cash=50000, max_positions=1))
        timestamp = datetime(2026, 1, 2, 9, 35)
        first = broker.buy(symbol='000001.SZ', price=10, quantity=100, timestamp=timestamp)
        second = broker.buy(symbol='000002.SZ', price=10, quantity=100, timestamp=timestamp)
        self.assertEqual(first.status.value, 'FILLED')
        self.assertEqual(second.status.value, 'REJECTED')
        self.assertEqual(second.reject_reason, '超过最大持仓数')


if __name__ == '__main__':
    unittest.main()
