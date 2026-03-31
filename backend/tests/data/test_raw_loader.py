from __future__ import annotations

import unittest
import warnings

import pandas as pd

from event_driven_backtest.backend.data import raw_loader


class _DummyLoader:
    def __init__(self):
        self.calls: list[dict] = []

    def load_symbol_minutes(
        self,
        symbol: str,
        start_datetime: str | None = None,
        end_datetime: str | None = None,
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        self.calls.append(
            {
                'symbol': symbol,
                'start_datetime': start_datetime,
                'end_datetime': end_datetime,
                'fields': fields,
            }
        )
        index = pd.DatetimeIndex(['2026-01-02 09:31:00'], name='datetime')
        return pd.DataFrame(
            {
                'open': [10.0],
                'high': [10.1],
                'low': [9.9],
                'close': [10.0],
                'volume': [1000.0],
                'amount': [10000.0],
            },
            index=index,
        )


class RawLoaderTest(unittest.TestCase):
    def test_load_symbol_minutes_uses_injected_loader(self):
        loader = _DummyLoader()

        frame = raw_loader.load_symbol_minutes(
            symbol='000001.SZ',
            start_datetime='2026-01-02 09:31:00',
            end_datetime='2026-01-02 15:00:00',
            adjustment='none',
            loader=loader,
        )

        self.assertFalse(frame.empty)
        self.assertEqual(len(loader.calls), 1)
        self.assertEqual(loader.calls[0]['symbol'], '000001.SZ')
        self.assertEqual(loader.calls[0]['fields'], raw_loader.DEFAULT_FIELDS)

    def test_load_symbol_map_calls_loader_for_each_symbol(self):
        loader = _DummyLoader()

        result = raw_loader.load_symbol_map(
            symbols=['000001.SZ', '600000.SH'],
            adjustment='none',
            loader=loader,
        )

        self.assertEqual(set(result.keys()), {'000001.SZ', '600000.SH'})
        self.assertEqual(len(loader.calls), 2)

    def test_qfq_adjustment_falls_back_to_raw_data_and_warns(self):
        loader = _DummyLoader()
        raw_loader._QFQ_WARNING_EMITTED = False

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always', RuntimeWarning)
            frame = raw_loader.load_symbol_minutes(
                symbol='000001.SZ',
                adjustment='qfq',
                loader=loader,
            )

        self.assertFalse(frame.empty)
        self.assertTrue(any('暂未接入前复权因子' in str(item.message) for item in caught))


if __name__ == '__main__':
    unittest.main()
