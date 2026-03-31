from datetime import datetime
import unittest

import pandas as pd

from event_driven_backtest.backend.core.config import BacktestConfig
from event_driven_backtest.backend.data.portal import DataPortal
from event_driven_backtest.backend.engine.runner import BacktestRunner


class DummyStrategy:
    name = 'dummy'

    def __init__(self):
        self.calls = 0

    def on_bar(self, context, bars):
        self.calls += 1
        return None


class BuyFirstBarStrategy:
    name = 'buy_first_bar'

    def __init__(self):
        self.has_sent = False

    def on_bar(self, context, bars):
        if self.has_sent:
            return None
        self.has_sent = True
        return {'symbol': '000001.SZ', 'type': 'BUY', 'quantity': 100}


class BuyFirstBarWithTriggerPriceStrategy:
    name = 'buy_first_bar_with_trigger_price'

    def __init__(self):
        self.has_sent = False

    def on_bar(self, context, bars):
        if self.has_sent:
            return None
        self.has_sent = True
        return {
            'symbol': '000001.SZ',
            'type': 'BUY',
            'quantity': 100,
            'price': 10.2,
            'execution': 'next_bar_price',
        }


class RunnerTest(unittest.TestCase):
    def test_runner_calls_strategy_on_each_bar(self):
        frame = pd.DataFrame(
            {
                'open': [1, 2],
                'high': [1, 2],
                'low': [1, 2],
                'close': [1, 2],
                'volume': [10, 20],
                'amount': [100, 200],
            },
            index=[datetime(2026, 1, 2, 9, 31), datetime(2026, 1, 2, 9, 32)],
        )
        portal = DataPortal({'000001.SZ': frame})
        strategy = DummyStrategy()
        runner = BacktestRunner(BacktestConfig(symbols=['000001.SZ']), portal)
        runner.run(strategy)
        self.assertEqual(strategy.calls, 2)

    def test_next_open_executes_on_following_bar_open(self):
        frame = pd.DataFrame(
            {
                'open': [10, 11],
                'high': [10.5, 11.5],
                'low': [9.8, 10.8],
                'close': [10.2, 11.2],
                'volume': [100, 120],
                'amount': [1000, 1200],
            },
            index=[datetime(2026, 1, 2, 9, 31), datetime(2026, 1, 2, 9, 32)],
        )
        portal = DataPortal({'000001.SZ': frame})
        strategy = BuyFirstBarStrategy()
        config = BacktestConfig(symbols=['000001.SZ'], match_mode='next_open', enable_t1=False)
        runner = BacktestRunner(config, portal)
        runner.run(strategy)
        self.assertEqual(len(runner.broker.orders), 1)
        self.assertEqual(runner.broker.orders[0].filled_price, 11)
        self.assertEqual(runner.broker.orders[0].filled_at, datetime(2026, 1, 2, 9, 32))

    def test_next_bar_price_executes_on_following_bar_using_order_price(self):
        frame = pd.DataFrame(
            {
                'open': [10, 11],
                'high': [10.5, 11.5],
                'low': [9.8, 10.8],
                'close': [10.2, 11.2],
                'volume': [100, 120],
                'amount': [1000, 1200],
            },
            index=[datetime(2026, 1, 2, 9, 31), datetime(2026, 1, 2, 9, 32)],
        )
        portal = DataPortal({'000001.SZ': frame})
        strategy = BuyFirstBarWithTriggerPriceStrategy()
        config = BacktestConfig(symbols=['000001.SZ'], match_mode='next_open', enable_t1=False)
        runner = BacktestRunner(config, portal)

        runner.run(strategy)

        self.assertEqual(len(runner.broker.orders), 1)
        self.assertEqual(runner.broker.orders[0].filled_price, 10.2)
        self.assertEqual(runner.broker.orders[0].filled_at, datetime(2026, 1, 2, 9, 32))

    def test_close_executes_on_current_bar_close(self):
        frame = pd.DataFrame(
            {
                'open': [10, 11],
                'high': [10.5, 11.5],
                'low': [9.8, 10.8],
                'close': [10.2, 11.2],
                'volume': [100, 120],
                'amount': [1000, 1200],
            },
            index=[datetime(2026, 1, 2, 9, 31), datetime(2026, 1, 2, 9, 32)],
        )
        portal = DataPortal({'000001.SZ': frame})
        strategy = BuyFirstBarStrategy()
        config = BacktestConfig(symbols=['000001.SZ'], match_mode='close', enable_t1=False)
        runner = BacktestRunner(config, portal)
        runner.run(strategy)
        self.assertEqual(runner.broker.orders[0].filled_price, 10.2)
        self.assertEqual(runner.broker.orders[0].filled_at, datetime(2026, 1, 2, 9, 31))

    def test_runner_supports_cancel_signal(self):
        frame = pd.DataFrame(
            {
                'open': [1, 2, 3],
                'high': [1, 2, 3],
                'low': [1, 2, 3],
                'close': [1, 2, 3],
                'volume': [10, 20, 30],
                'amount': [100, 200, 300],
            },
            index=[
                datetime(2026, 1, 2, 9, 31),
                datetime(2026, 1, 2, 9, 32),
                datetime(2026, 1, 2, 9, 33),
            ],
        )
        portal = DataPortal({'000001.SZ': frame})
        strategy = DummyStrategy()
        called = {'count': 0}

        def stop_checker():
            called['count'] += 1
            return called['count'] >= 2

        runner = BacktestRunner(BacktestConfig(symbols=['000001.SZ']), portal, stop_checker=stop_checker)
        result = runner.run(strategy)

        self.assertTrue(result['cancelled'])
        self.assertEqual(strategy.calls, 1)


if __name__ == '__main__':
    unittest.main()
