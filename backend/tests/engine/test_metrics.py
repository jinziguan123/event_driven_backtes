import unittest

import pandas as pd

from event_driven_backtest.backend.engine.metrics import (
    build_benchmark_curve,
    build_drawdown_curve,
    compute_core_metrics,
    compute_max_drawdown_window,
)


class MetricsTest(unittest.TestCase):
    def test_compute_core_metrics(self):
        equity = pd.Series([100, 110, 105, 120])
        trades = pd.DataFrame({'pnl': [10, -5, 8]})
        metrics = compute_core_metrics(equity, trades)
        self.assertAlmostEqual(metrics['total_return'], 0.2)
        self.assertGreaterEqual(metrics['max_drawdown'], 0)
        self.assertGreater(metrics['win_rate'], 0)

    def test_build_benchmark_curve_normalizes_to_initial_cash(self):
        index = pd.to_datetime(['2026-01-02 09:31:00', '2026-01-02 09:32:00', '2026-01-02 09:33:00'])
        price_series = pd.Series([100.0, 110.0, 120.0], index=index)
        equity_index = pd.to_datetime(['2026-01-02 09:31:00', '2026-01-02 09:32:00', '2026-01-02 09:33:00'])

        curve = build_benchmark_curve(price_series, equity_index, initial_cash=1_000_000)

        self.assertEqual(curve.iloc[0]['benchmark_equity'], 1_000_000)
        self.assertAlmostEqual(curve.iloc[-1]['benchmark_return'], 0.2)

    def test_compute_max_drawdown_window_finds_peak_and_trough(self):
        index = pd.to_datetime([
            '2026-01-02 09:31:00',
            '2026-01-02 09:32:00',
            '2026-01-02 09:33:00',
            '2026-01-02 09:34:00',
            '2026-01-02 09:35:00',
        ])
        equity = pd.Series([1_000_000, 1_100_000, 900_000, 950_000, 1_120_000], index=index)

        window = compute_max_drawdown_window(equity)

        self.assertEqual(window['peak_time'], '2026-01-02 09:32:00')
        self.assertEqual(window['trough_time'], '2026-01-02 09:33:00')
        self.assertEqual(window['recovery_time'], '2026-01-02 09:35:00')
        self.assertAlmostEqual(window['max_drawdown'], 0.18181818, places=6)

    def test_build_drawdown_curve_contains_strategy_and_benchmark(self):
        index = pd.to_datetime(['2026-01-02 09:31:00', '2026-01-02 09:32:00', '2026-01-02 09:33:00'])
        strategy_equity = pd.Series([100.0, 120.0, 90.0], index=index)
        benchmark_equity = pd.Series([100.0, 105.0, 102.0], index=index)

        curve = build_drawdown_curve(strategy_equity, benchmark_equity)

        self.assertIn('strategy_drawdown', curve.columns)
        self.assertIn('benchmark_drawdown', curve.columns)
        self.assertLess(curve.iloc[-1]['strategy_drawdown'], 0)


if __name__ == '__main__':
    unittest.main()
