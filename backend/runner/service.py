from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from time import perf_counter
from typing import Any

import pandas as pd

from event_driven_backtest.backend.core.config import BacktestConfig
from event_driven_backtest.backend.data.aggregator import aggregate_bars
from event_driven_backtest.backend.data.portal import DataPortal
from event_driven_backtest.backend.data.raw_loader import load_symbol_minutes
from event_driven_backtest.backend.engine.metrics import build_benchmark_curve, build_drawdown_curve
from event_driven_backtest.backend.engine.runner import BacktestRunner
from event_driven_backtest.backend.runner.stream_hub import RunStreamHub
from event_driven_backtest.backend.storage.result_store import ResultStore
from event_driven_backtest.backend.storage.stock_pool_store import StockPoolStore
from event_driven_backtest.backend.strategy_sdk.discovery import list_strategy_files
from event_driven_backtest.backend.strategy_sdk.loader import load_strategy

DEFAULT_STRATEGY_PATH = Path('event_driven_backtest/backend/strategies/demo_buy_hold.py')
STREAM_LIST_FIELDS = {
    'log': 'logs',
    'equity': 'equity',
    'trade': 'trades',
    'position': 'positions',
}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _json_ready(value: Any):
    if isinstance(value, pd.Timestamp):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    if pd.isna(value):
        return None
    if hasattr(value, 'item'):
        try:
            return value.item()
        except Exception:
            return value
    return value


def _normalize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: _json_ready(value) for key, value in row.items()} for row in records]


class BacktestService:
    def __init__(
        self,
        store: ResultStore | None = None,
        stream_hub: RunStreamHub | None = None,
        stock_pool_store: StockPoolStore | None = None,
    ):
        self.store = store or ResultStore()
        self.stock_pool_store = stock_pool_store or StockPoolStore(self.store.db_path)
        self.stream_hub = stream_hub or RunStreamHub()
        self._threads: dict[str, Thread] = {}
        self._cancel_flags: dict[str, Event] = {}

    def list_strategies(self) -> list[dict[str, str]]:
        return list_strategy_files()

    def list_stock_pools(self) -> list[dict]:
        return self.stock_pool_store.list_pools()

    def list_stocks(self, keyword: str | None = None, limit: int = 200) -> list[dict]:
        return self.stock_pool_store.list_symbols(keyword=keyword, limit=limit)

    def list_stocks_page(self, keyword: str | None = None, page: int = 1, page_size: int = 100) -> dict:
        safe_page = max(int(page), 1)
        safe_page_size = min(max(int(page_size), 1), 500)
        offset = (safe_page - 1) * safe_page_size
        items = self.stock_pool_store.list_symbols(keyword=keyword, limit=safe_page_size, offset=offset)
        total = self.stock_pool_store.count_symbols(keyword=keyword)
        return {
            'items': items,
            'total': total,
            'page': safe_page,
            'page_size': safe_page_size,
        }

    def get_stock_pool(self, pool_id: str) -> dict | None:
        return self.stock_pool_store.get_pool(pool_id)

    def create_stock_pool(self, payload: dict) -> dict:
        return self.stock_pool_store.create_pool(
            name=payload['name'],
            description=payload.get('description', ''),
            symbols=payload.get('symbols', []),
        )

    def update_stock_pool(self, pool_id: str, payload: dict) -> dict | None:
        return self.stock_pool_store.update_pool(
            pool_id=pool_id,
            name=payload['name'],
            description=payload.get('description', ''),
            symbols=payload.get('symbols', []),
        )

    def delete_stock_pool(self, pool_id: str) -> bool:
        return self.stock_pool_store.delete_pool(pool_id)

    def _resolve_symbols(self, payload: dict) -> dict:
        resolved_payload = dict(payload)
        pool_id = resolved_payload.get('pool_id')
        if not pool_id:
            return resolved_payload
        pool = self.stock_pool_store.get_pool(pool_id)
        if pool is None:
            raise ValueError(f'未找到股票池: {pool_id}')
        resolved_payload['symbols'] = pool['symbols']
        resolved_payload['pool_name'] = pool['name']
        return resolved_payload

    def _load_benchmark_curve(self, config: BacktestConfig, equity_df: pd.DataFrame) -> pd.DataFrame:
        if equity_df.empty or 'total_equity' not in equity_df.columns or not config.benchmark:
            return pd.DataFrame(columns=['benchmark_price', 'benchmark_equity', 'benchmark_return'])

        benchmark_df = load_symbol_minutes(
            symbol=config.benchmark,
            start_datetime=config.start_datetime.isoformat(sep=' ') if config.start_datetime else None,
            end_datetime=config.end_datetime.isoformat(sep=' ') if config.end_datetime else None,
            adjustment=config.adjustment,
        )
        if benchmark_df.empty:
            return pd.DataFrame(columns=['benchmark_price', 'benchmark_equity', 'benchmark_return'])

        if config.bar_frequency != '1m':
            benchmark_df = aggregate_bars(benchmark_df, config.bar_frequency)

        if 'close' not in benchmark_df.columns:
            return pd.DataFrame(columns=['benchmark_price', 'benchmark_equity', 'benchmark_return'])

        return build_benchmark_curve(
            benchmark_price=benchmark_df['close'],
            equity_index=equity_df.index,
            initial_cash=config.initial_cash,
        )

    def create_run(self, payload: dict) -> dict:
        resolved_payload = self._resolve_symbols(payload)
        run_id = self.store.create_run_directory()
        strategy_path = resolved_payload.get('strategy_path') or str(DEFAULT_STRATEGY_PATH)

        self.store.register_run(
            run_id,
            name=resolved_payload.get('name', '未命名回测'),
            strategy_name=resolved_payload.get('strategy_name', '未指定策略'),
            status='RUNNING',
            params=resolved_payload,
        )
        self.store.mark_running(run_id)

        initial_state = self._load_stream_state(run_id) or {
            'run_id': run_id,
            'status': 'RUNNING',
            'detail': {'run_id': run_id, 'status': 'RUNNING'},
            'logs': [],
            'equity': [],
            'benchmark': [],
            'drawdown': [],
            'trades': [],
            'positions': [],
        }
        self.stream_hub.ensure_run(run_id, initial_state)
        self.stream_hub.update_state(run_id, {'status': 'RUNNING'})
        self.stream_hub.publish(run_id, 'status', {'run_id': run_id, 'status': 'RUNNING'})
        self._cancel_flags[run_id] = Event()

        thread = Thread(
            target=self._execute_run,
            args=(run_id, resolved_payload, strategy_path),
            daemon=True,
            name=f'backtest-{run_id}',
        )
        self._threads[run_id] = thread
        thread.start()
        return {'run_id': run_id, 'status': 'RUNNING'}

    def _build_config(self, payload: dict, strategy_path: str) -> BacktestConfig:
        return BacktestConfig(
            symbols=payload['symbols'],
            initial_cash=payload.get('initial_cash', 1_000_000),
            max_positions=payload.get('max_positions', 5),
            slippage=payload.get('slippage', 0.0),
            commission=payload.get('commission', 0.0003),
            stamp_duty=payload.get('stamp_duty', 0.001),
            adjustment=payload.get('adjustment', 'qfq'),
            match_mode=payload.get('match_mode', 'next_open'),
            enable_t1=payload.get('enable_t1', True),
            data_frequency=payload.get('data_frequency', '1m'),
            bar_frequency=payload.get('bar_frequency', '1m'),
            strategy_type=payload.get('strategy_type', 'class'),
            strategy_path=strategy_path,
            start_datetime=_parse_datetime(payload.get('start_datetime')),
            end_datetime=_parse_datetime(payload.get('end_datetime')),
            benchmark=payload.get('benchmark', '000300.SH'),
        )

    def _build_progress_callback(self, run_id: str):
        def callback(event_type: str, payload: dict[str, Any]) -> None:
            list_key = STREAM_LIST_FIELDS.get(event_type)
            if list_key is not None:
                self.stream_hub.append_item(run_id, list_key, payload)
            self.stream_hub.publish(run_id, event_type, payload)

        return callback

    def _is_cancel_requested(self, run_id: str) -> bool:
        cancel_flag = self._cancel_flags.get(run_id)
        return bool(cancel_flag and cancel_flag.is_set())

    def _emit_status(self, run_id: str, status: str, **extra: Any) -> None:
        payload = {'run_id': run_id, 'status': status, **extra}
        self.stream_hub.update_state(run_id, {'status': status})
        self.stream_hub.publish(run_id, 'status', payload)

    def _execute_run(self, run_id: str, payload: dict, strategy_path: str) -> None:
        stage_started = perf_counter()
        profile_payload: dict[str, Any] = {}
        try:
            config = self._build_config(payload, strategy_path)
            data_start = perf_counter()
            portal = DataPortal.from_loader(
                symbols=config.symbols,
                start_datetime=payload.get('start_datetime'),
                end_datetime=payload.get('end_datetime'),
                adjustment=config.adjustment,
                bar_frequency=config.bar_frequency,
            )
            profile_payload['data_load_seconds'] = round(perf_counter() - data_start, 6)
            profile_payload['symbol_count'] = len(config.symbols)
            profile_payload['loaded_symbol_count'] = len(portal.bars_by_symbol)

            strategy_start = perf_counter()
            strategy = load_strategy(strategy_path)
            profile_payload['strategy_load_seconds'] = round(perf_counter() - strategy_start, 6)

            run_start = perf_counter()
            runner = BacktestRunner(
                config,
                portal,
                progress_callback=self._build_progress_callback(run_id),
                stop_checker=lambda: self._is_cancel_requested(run_id),
            )
            results = runner.run(strategy)
            cancelled = bool(results.get('cancelled', False))
            profile_payload['engine_run_seconds'] = round(perf_counter() - run_start, 6)
            profile_payload['equity_points'] = len(results['equity']) if 'equity' in results and results['equity'] is not None else 0
            profile_payload['trade_count_runtime'] = len(results['trades']) if 'trades' in results and results['trades'] is not None else 0
            profile_payload['position_rows_runtime'] = len(results['positions']) if 'positions' in results and results['positions'] is not None else 0

            benchmark_start = perf_counter()
            benchmark_curve = self._load_benchmark_curve(config, results['equity'])
            benchmark_equity = benchmark_curve['benchmark_equity'] if not benchmark_curve.empty else pd.Series(dtype=float)
            drawdown_curve = build_drawdown_curve(
                strategy_equity=results['equity']['total_equity'] if not results['equity'].empty else pd.Series(dtype=float),
                benchmark_equity=benchmark_equity,
            )
            profile_payload['benchmark_drawdown_seconds'] = round(perf_counter() - benchmark_start, 6)
            if benchmark_curve.empty:
                warning_log = {
                    'timestamp': datetime.now().isoformat(),
                    'level': 'WARNING',
                    'message': f'未能生成基准曲线，基准代码: {config.benchmark}',
                }
                results['logs'].append(warning_log)
                self.stream_hub.append_item(run_id, 'logs', warning_log)
                self.stream_hub.publish(run_id, 'log', warning_log)

            metrics_payload = dict(results['metrics'])
            metrics_payload['benchmark'] = config.benchmark
            persist_start = perf_counter()
            self.store.save_metrics(run_id, metrics_payload)
            self.store.save_summary(
                run_id,
                {
                    'run_id': run_id,
                    'strategy_name': results['strategy_name'],
                    'metrics': metrics_payload,
                    'config': payload,
                    'max_drawdown_window': results['metrics'].get('max_drawdown_window', {}),
                    'profile': profile_payload,
                },
            )
            self.store.save_logs(run_id, results['logs'])
            for artifact_type in ('equity', 'orders', 'trades', 'positions'):
                frame = results[artifact_type]
                if frame is not None and not frame.empty:
                    self.store.save_dataframe(run_id, artifact_type, frame)
            if not benchmark_curve.empty:
                self.store.save_dataframe(run_id, 'benchmark_curve', benchmark_curve)
            if not drawdown_curve.empty:
                self.store.save_dataframe(run_id, 'drawdown_curve', drawdown_curve)
            profile_payload['persist_seconds'] = round(perf_counter() - persist_start, 6)
            profile_payload['total_seconds'] = round(perf_counter() - stage_started, 6)
            profile_payload['final_status'] = 'CANCELED' if cancelled else 'SUCCESS'
            self.store.save_summary(
                run_id,
                {
                    'run_id': run_id,
                    'strategy_name': results['strategy_name'],
                    'metrics': metrics_payload,
                    'config': payload,
                    'max_drawdown_window': results['metrics'].get('max_drawdown_window', {}),
                    'profile': profile_payload,
                },
            )
            profile_log = {
                'timestamp': datetime.now().isoformat(),
                'level': 'INFO',
                'message': f'性能画像: data={profile_payload.get("data_load_seconds", 0):.3f}s, run={profile_payload.get("engine_run_seconds", 0):.3f}s, persist={profile_payload.get("persist_seconds", 0):.3f}s, total={profile_payload.get("total_seconds", 0):.3f}s',
                'extra': profile_payload,
            }
            results['logs'].append(profile_log)
            self.stream_hub.append_item(run_id, 'logs', profile_log)
            self.stream_hub.publish(run_id, 'log', profile_log)
            self.store.save_logs(run_id, results['logs'])

            final_status = 'CANCELED' if cancelled else 'SUCCESS'
            self.store.update_status(run_id, final_status)
            success_state = self._load_stream_state(run_id)
            if success_state is not None:
                self.stream_hub.update_state(run_id, success_state)
            self._emit_status(run_id, final_status)
            self.stream_hub.publish(
                run_id,
                'complete',
                {
                    'run_id': run_id,
                    'status': final_status,
                    'detail': self.get_run(run_id),
                },
            )
        except Exception as exc:
            profile_payload['total_seconds'] = round(perf_counter() - stage_started, 6)
            profile_payload['final_status'] = 'FAILED'
            error_log = {
                'timestamp': datetime.now().isoformat(),
                'level': 'ERROR',
                'message': str(exc),
            }
            current_logs = self.stream_hub.get_snapshot(run_id).get('logs', [])
            self.stream_hub.append_item(run_id, 'logs', error_log)
            self.stream_hub.publish(run_id, 'log', error_log)
            try:
                self.store.save_logs(run_id, current_logs + [error_log])
            except Exception:
                pass
            try:
                self.store.save_summary(
                    run_id,
                    {
                        'run_id': run_id,
                        'strategy_name': payload.get('strategy_name', '未指定策略'),
                        'metrics': {},
                        'config': payload,
                        'max_drawdown_window': {},
                        'profile': profile_payload,
                    },
                )
            except Exception:
                pass
            self.store.update_status(run_id, 'FAILED', str(exc))
            failed_state = self._load_stream_state(run_id)
            if failed_state is not None:
                self.stream_hub.update_state(run_id, failed_state)
            self._emit_status(run_id, 'FAILED', error_message=str(exc))
            self.stream_hub.publish(
                run_id,
                'complete',
                {
                    'run_id': run_id,
                    'status': 'FAILED',
                    'error_message': str(exc),
                },
            )
        finally:
            self._threads.pop(run_id, None)
            self._cancel_flags.pop(run_id, None)

    def get_run_profile(self, run_id: str) -> dict | None:
        run = self.get_run(run_id)
        if run is None:
            return None
        summary = run.get('summary') or {}
        profile = summary.get('profile') or {}
        return {'run_id': run_id, 'profile': profile}

    def cancel_run(self, run_id: str) -> dict | None:
        run = self.store.get_run_row(run_id)
        if run is None:
            return None

        status = run.get('status', 'PENDING')
        if status in {'SUCCESS', 'FAILED', 'CANCELED'}:
            return {'run_id': run_id, 'status': status, 'accepted': False, 'message': '任务已结束，无需中断'}
        if status == 'CANCELING':
            return {'run_id': run_id, 'status': status, 'accepted': False, 'message': '中断请求已提交，请等待任务停止'}

        thread = self._threads.get(run_id)
        if thread is None or not thread.is_alive():
            return {'run_id': run_id, 'status': status, 'accepted': False, 'message': '任务不在运行中，无法中断'}

        cancel_flag = self._cancel_flags.setdefault(run_id, Event())
        cancel_flag.set()
        self.store.update_status(run_id, 'CANCELING')

        if not self.stream_hub.has_run(run_id):
            snapshot = self._load_stream_state(run_id)
            if snapshot is not None:
                self.stream_hub.ensure_run(run_id, snapshot)

        cancel_log = {
            'timestamp': datetime.now().isoformat(),
            'level': 'WARNING',
            'message': '收到中断请求，正在安全停止回测',
        }
        self.stream_hub.append_item(run_id, 'logs', cancel_log)
        self.stream_hub.publish(run_id, 'log', cancel_log)
        self.stream_hub.update_state(run_id, {'status': 'CANCELING'})
        self.stream_hub.publish(run_id, 'status', {'run_id': run_id, 'status': 'CANCELING'})

        return {
            'run_id': run_id,
            'status': 'CANCELING',
            'accepted': True,
            'message': '已收到中断请求，等待任务停止',
        }

    def delete_run(self, run_id: str) -> dict | None:
        run = self.store.get_run_row(run_id)
        if run is None:
            return None

        status = run.get('status', 'PENDING')
        thread = self._threads.get(run_id)
        if status in {'RUNNING', 'CANCELING'} and thread is not None and thread.is_alive():
            return {'run_id': run_id, 'deleted': False, 'message': '回测仍在运行，请先中断'}

        deleted = self.store.delete_run(run_id)
        if deleted:
            self.stream_hub.remove_run(run_id)
            self._threads.pop(run_id, None)
            self._cancel_flags.pop(run_id, None)
            return {'run_id': run_id, 'deleted': True}
        return {'run_id': run_id, 'deleted': False, 'message': '删除回测记录失败'}

    def _load_stream_state(self, run_id: str) -> dict[str, Any] | None:
        detail = self.get_run(run_id)
        if detail is None:
            return None
        return {
            'run_id': run_id,
            'status': detail.get('status', 'PENDING'),
            'detail': detail,
            'logs': self.get_logs(run_id),
            'equity': self.get_equity(run_id),
            'benchmark': self.get_benchmark(run_id),
            'drawdown': self.get_drawdown(run_id),
            'trades': self.get_trades(run_id),
            'positions': self.get_positions(run_id),
        }

    def stream_run(self, run_id: str):
        if not self.stream_hub.has_run(run_id):
            snapshot = self._load_stream_state(run_id)
            if snapshot is None:
                return None
            self.stream_hub.ensure_run(run_id, snapshot)
        return self.stream_hub.subscribe(run_id)

    def wait_for_all_runs(self, timeout: float = 2.0) -> None:
        for thread in list(self._threads.values()):
            thread.join(timeout=timeout)

    def _load_artifact_frame(self, run_id: str, artifact_type: str) -> pd.DataFrame:
        frame = self.store.load_dataframe(run_id, artifact_type)
        if frame.empty:
            return frame
        normalized = frame.copy()
        if 'timestamp' in normalized.columns:
            normalized['timestamp'] = pd.to_datetime(normalized['timestamp'])
        elif normalized.index.name == 'timestamp':
            normalized = normalized.reset_index()
            normalized['timestamp'] = pd.to_datetime(normalized['timestamp'])
        return normalized

    @staticmethod
    def _filter_by_date(frame: pd.DataFrame, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
        if frame.empty or 'timestamp' not in frame.columns:
            return frame
        filtered = frame
        if start_date:
            start_ts = pd.to_datetime(start_date)
            filtered = filtered[filtered['timestamp'] >= start_ts]
        if end_date:
            end_ts = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
            filtered = filtered[filtered['timestamp'] <= end_ts]
        return filtered

    @staticmethod
    def _aggregate_trades_by_day(frame: pd.DataFrame) -> list[dict]:
        if frame.empty:
            return []
        working = frame.copy()
        working['date'] = working['timestamp'].dt.strftime('%Y-%m-%d')
        working['amount'] = working['quantity'] * working['price']
        rows: list[dict] = []
        for date, group in working.groupby('date', sort=True):
            buy_group = group[group['side'] == 'BUY']
            sell_group = group[group['side'] == 'SELL']
            rows.append(
                {
                    'date': date,
                    'buy_count': int(len(buy_group)),
                    'sell_count': int(len(sell_group)),
                    'buy_amount': float(buy_group['amount'].sum()) if not buy_group.empty else 0.0,
                    'sell_amount': float(sell_group['amount'].sum()) if not sell_group.empty else 0.0,
                    'realized_pnl': float(group.get('pnl', pd.Series(dtype=float)).sum()),
                    'commission': float(group.get('commission', pd.Series(dtype=float)).sum()),
                    'stamp_duty': float(group.get('stamp_duty', pd.Series(dtype=float)).sum()),
                }
            )
        return rows

    @staticmethod
    def _aggregate_positions_by_day(frame: pd.DataFrame) -> list[dict]:
        if frame.empty:
            return []
        working = frame.copy()
        working = working.sort_values(['timestamp', 'symbol'])
        working['date'] = working['timestamp'].dt.strftime('%Y-%m-%d')
        last_rows = working.groupby(['date', 'symbol'], as_index=False).tail(1)
        rows: list[dict] = []
        for date, group in last_rows.groupby('date', sort=True):
            active_positions = group[group['quantity'] > 0]
            rows.append(
                {
                    'date': date,
                    'position_symbol_count': int(active_positions['symbol'].nunique()),
                    'total_quantity': int(active_positions['quantity'].sum()) if not active_positions.empty else 0,
                    'total_market_value': float(active_positions['market_value'].sum()) if not active_positions.empty else 0.0,
                    'total_unrealized_pnl': float(active_positions['unrealized_pnl'].sum()) if not active_positions.empty else 0.0,
                }
            )
        return rows

    def list_runs(self) -> list[dict]:
        return self.store.list_runs()

    def get_run(self, run_id: str) -> dict | None:
        result = self.store.get_run_row(run_id)
        if result is None:
            return None
        result['summary'] = self.store.load_summary(run_id)
        return result

    def get_equity(self, run_id: str):
        frame = self.store.load_dataframe(run_id, 'equity')
        if frame.empty:
            return []
        return _normalize_records(frame.reset_index().to_dict(orient='records'))

    def get_benchmark(self, run_id: str):
        frame = self.store.load_dataframe(run_id, 'benchmark_curve')
        if frame.empty:
            return []
        return _normalize_records(frame.reset_index().to_dict(orient='records'))

    def get_drawdown(self, run_id: str):
        frame = self.store.load_dataframe(run_id, 'drawdown_curve')
        if frame.empty:
            return []
        return _normalize_records(frame.reset_index().to_dict(orient='records'))

    def get_trades(
        self,
        run_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        granularity: str = 'raw',
    ):
        frame = self._load_artifact_frame(run_id, 'trades')
        if frame.empty:
            return []
        filtered = self._filter_by_date(frame, start_date=start_date, end_date=end_date)
        if granularity == 'day':
            return self._aggregate_trades_by_day(filtered)
        return _normalize_records(filtered.to_dict(orient='records'))

    def get_positions(
        self,
        run_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        granularity: str = 'raw',
    ):
        frame = self._load_artifact_frame(run_id, 'positions')
        if frame.empty:
            return []
        filtered = self._filter_by_date(frame, start_date=start_date, end_date=end_date)
        if granularity == 'day':
            return self._aggregate_positions_by_day(filtered)
        return _normalize_records(filtered.to_dict(orient='records'))

    def get_logs(self, run_id: str):
        return self.store.load_logs(run_id)
