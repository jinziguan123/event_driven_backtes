from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import pandas as pd

from event_driven_backtest.backend.core.config import BacktestConfig
from event_driven_backtest.backend.core.models import MarketBar, Order, OrderSide, OrderStatus, PortfolioSnapshot, Trade
from event_driven_backtest.backend.data.portal import DataPortal
from .broker import Broker
from .metrics import compute_core_metrics

ProgressCallback = Callable[[str, dict[str, Any]], None]
StopChecker = Callable[[], bool]


class BacktestRunner:
    def __init__(
        self,
        config: BacktestConfig,
        data_portal: DataPortal,
        progress_callback: ProgressCallback | None = None,
        stop_checker: StopChecker | None = None,
    ):
        self.config = config
        self.data_portal = data_portal
        self.progress_callback = progress_callback
        self.stop_checker = stop_checker
        self.broker = Broker(config)
        self.snapshots: list[PortfolioSnapshot] = []
        self.position_rows: list[dict[str, Any]] = []
        self.logs: list[dict[str, Any]] = []
        self.pending_orders: list[dict[str, Any]] = []

    def _all_timestamps(self) -> list[pd.Timestamp]:
        timestamps: set[pd.Timestamp] = set()
        for frame in self.data_portal.bars_by_symbol.values():
            timestamps.update(pd.to_datetime(frame.index).tolist())
        return sorted(timestamps)

    def _emit_progress(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.progress_callback is not None:
            self.progress_callback(event_type, payload)

    def _should_stop(self) -> bool:
        if self.stop_checker is None:
            return False
        return bool(self.stop_checker())

    def _log(self, level: str, message: str, timestamp: datetime | None = None, **extra: Any) -> None:
        payload = {
            'timestamp': (timestamp or datetime.now()).isoformat(),
            'level': level,
            'message': message,
        }
        if extra:
            payload['extra'] = extra
        self.logs.append(payload)
        self._emit_progress('log', payload)

    def _build_bars(self, timestamp: pd.Timestamp) -> dict[str, MarketBar]:
        bars: dict[str, MarketBar] = {}
        for symbol, frame in self.data_portal.bars_by_symbol.items():
            if timestamp not in frame.index:
                continue
            row = frame.loc[timestamp]
            bars[symbol] = MarketBar(
                symbol=symbol,
                datetime=timestamp.to_pydatetime() if hasattr(timestamp, 'to_pydatetime') else datetime.fromisoformat(str(timestamp)),
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=float(row.get('volume', 0.0)),
                amount=float(row.get('amount', 0.0)),
            )
        return bars

    def run(self, strategy: Any) -> dict[str, Any]:
        context = {
            'config': self.config,
            'broker': self.broker,
            'data_portal': self.data_portal,
            'logs': self.logs,
        }
        initializer = getattr(strategy, 'initialize', None)
        if callable(initializer):
            initializer(context)
        self._log('INFO', '策略初始化完成')

        timestamps = self._all_timestamps()
        if not timestamps:
            self._log('WARNING', '当前回测区间没有可用行情数据')

        cancelled = False
        for timestamp in timestamps:
            if self._should_stop():
                cancelled = True
                self._log('WARNING', '收到中断请求，停止回测循环')
                break
            bar_time = timestamp.to_pydatetime() if hasattr(timestamp, 'to_pydatetime') else timestamp
            self.broker.on_new_bar(bar_time)
            bars = self._build_bars(timestamp)
            if not bars:
                continue
            self._fill_pending_orders(bars, bar_time)
            context['timestamp'] = timestamp
            result = strategy.on_bar(context, bars)
            self._process_result(result, bars, timestamp)
            snapshot = self.broker.mark_to_market({symbol: bar.close for symbol, bar in bars.items()}, bar_time)
            self.snapshots.append(snapshot)
            self._emit_progress('equity', self._snapshot_to_record(snapshot))
            for row in self._append_positions(snapshot.timestamp):
                self._emit_progress('position', row)

        if cancelled:
            self._cancel_pending_orders()
        else:
            self._flush_pending_orders()

        if not cancelled:
            after_trading = getattr(strategy, 'after_trading', None)
            if callable(after_trading):
                after_trading(context)
            self._log('INFO', '回测运行结束')
        else:
            self._log('WARNING', '回测已中断，结果为部分区间数据')

        results = self.get_results(strategy_name=getattr(strategy, 'name', 'unknown_strategy'))
        results['cancelled'] = cancelled
        return results

    def _append_positions(self, timestamp: datetime) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for symbol, position in self.broker.account.positions.items():
            row = {
                'timestamp': timestamp.isoformat(),
                'symbol': symbol,
                'quantity': position.quantity,
                'sellable_quantity': position.sellable_quantity,
                'avg_cost': position.avg_cost,
                'market_value': position.market_value,
                'unrealized_pnl': position.unrealized_pnl,
            }
            rows.append(row)
            self.position_rows.append(row)
        return rows

    def _snapshot_to_record(self, snapshot: PortfolioSnapshot) -> dict[str, Any]:
        return {
            'timestamp': snapshot.timestamp.isoformat(),
            'cash': snapshot.cash,
            'market_value': snapshot.market_value,
            'total_equity': snapshot.total_equity,
            'position_ratio': snapshot.position_ratio,
        }

    def _trade_to_record(self, trade: Trade) -> dict[str, Any]:
        return {
            'timestamp': trade.timestamp.isoformat(),
            'symbol': trade.symbol,
            'side': trade.side.value,
            'quantity': trade.quantity,
            'price': trade.price,
            'commission': trade.commission,
            'stamp_duty': trade.stamp_duty,
            'pnl': trade.pnl,
        }

    def _emit_trade(self, order: Order) -> None:
        if order.status != OrderStatus.FILLED or not self.broker.trades:
            return
        self._emit_progress('trade', self._trade_to_record(self.broker.trades[-1]))

    def _normalize_orders(self, result: Any) -> list[dict[str, Any]]:
        if result is None:
            return []
        if isinstance(result, dict):
            return [result]
        return list(result)

    def _fill_pending_orders(self, bars: dict[str, MarketBar], timestamp: datetime) -> None:
        if not self.pending_orders:
            return

        remaining_orders: list[dict[str, Any]] = []
        for order in self.pending_orders:
            symbol = order['symbol']
            if symbol not in bars:
                remaining_orders.append(order)
                continue
            bar = bars[symbol]
            order_type = order['type'].upper()
            quantity = int(order['quantity'])
            execution_mode = str(order.get('execution', self.config.match_mode))
            if execution_mode == 'next_bar_price':
                fill_price = float(order.get('price', bar.open))
            else:
                fill_price = bar.open
            if order_type == 'BUY':
                order_result = self.broker.buy(symbol=symbol, price=fill_price, quantity=quantity, timestamp=timestamp)
            else:
                order_result = self.broker.sell(symbol=symbol, price=fill_price, quantity=quantity, timestamp=timestamp)
            if order_result.status == OrderStatus.FILLED:
                self._emit_trade(order_result)
                self._log('INFO', '下一根K线开盘撮合成交', timestamp, symbol=symbol, side=order_type, price=fill_price, quantity=quantity)
            else:
                self._log(
                    'WARNING',
                    order_result.reject_reason or '下一根K线开盘撮合失败',
                    timestamp,
                    symbol=symbol,
                    side=order_type,
                    price=fill_price,
                    quantity=quantity,
                )
        self.pending_orders = remaining_orders

    def _execute_order(self, order: dict[str, Any], bars: dict[str, MarketBar], timestamp: datetime) -> None:
        symbol = order['symbol']
        if symbol not in bars:
            self._log('WARNING', '订单对应股票当前无可用bar，已跳过', timestamp, symbol=symbol)
            return
        bar = bars[symbol]
        order_type = order['type'].upper()
        quantity = int(order['quantity'])
        execution_mode = str(order.get('execution', self.config.match_mode))

        if execution_mode in {'next_open', 'next_bar_price'}:
            self.pending_orders.append(order)
            self._log('INFO', '订单进入下一根K线开盘撮合队列', timestamp, symbol=symbol, side=order_type, quantity=quantity)
            return

        if execution_mode == 'limit':
            limit_price = float(order.get('price', bar.close))
            if not (bar.low <= limit_price <= bar.high):
                self.broker.reject_order(symbol, OrderSide[order_type], quantity, timestamp, price=limit_price, reason='限价未成交')
                self._log('WARNING', '限价单未成交', timestamp, symbol=symbol, side=order_type, price=limit_price, quantity=quantity)
                return
            fill_price = limit_price
        else:
            fill_price = float(order.get('price', bar.close)) if 'price' in order else bar.close

        if order_type == 'BUY':
            order_result = self.broker.buy(symbol=symbol, price=fill_price, quantity=quantity, timestamp=timestamp)
        else:
            order_result = self.broker.sell(symbol=symbol, price=fill_price, quantity=quantity, timestamp=timestamp)

        if order_result.status == OrderStatus.FILLED:
            self._emit_trade(order_result)
            self._log('INFO', '订单成交', timestamp, symbol=symbol, side=order_type, price=fill_price, quantity=quantity)
            return

        self._log(
            'WARNING',
            order_result.reject_reason or '订单被拒绝',
            timestamp,
            symbol=symbol,
            side=order_type,
            price=fill_price,
            quantity=quantity,
        )

    def _process_result(self, result: Any, bars: dict[str, MarketBar], timestamp: pd.Timestamp) -> None:
        bar_time = timestamp.to_pydatetime() if hasattr(timestamp, 'to_pydatetime') else timestamp
        for order in self._normalize_orders(result):
            self._execute_order(order, bars, bar_time)

    def _flush_pending_orders(self) -> None:
        if not self.pending_orders:
            return
        for order in self.pending_orders:
            symbol = order['symbol']
            quantity = int(order['quantity'])
            side = OrderSide[order['type'].upper()]
            self.broker.reject_order(symbol, side, quantity, datetime.now(), price=order.get('price'), reason='回测结束仍未等到下一根K线')
            self._log('WARNING', '回测结束时仍存在待开盘撮合订单，已拒绝', symbol=symbol, side=side.value, quantity=quantity)
        self.pending_orders = []

    def _cancel_pending_orders(self) -> None:
        if not self.pending_orders:
            return
        for order in self.pending_orders:
            symbol = order['symbol']
            quantity = int(order['quantity'])
            side = OrderSide[order['type'].upper()]
            self.broker.reject_order(symbol, side, quantity, datetime.now(), price=order.get('price'), reason='回测中断')
            self._log('WARNING', '回测中断，未成交挂单已撤销', symbol=symbol, side=side.value, quantity=quantity)
        self.pending_orders = []

    def get_results(self, strategy_name: str) -> dict[str, Any]:
        equity_df = pd.DataFrame(
            [
                {
                    'timestamp': snapshot.timestamp,
                    'cash': snapshot.cash,
                    'market_value': snapshot.market_value,
                    'total_equity': snapshot.total_equity,
                    'position_ratio': snapshot.position_ratio,
                }
                for snapshot in self.snapshots
            ]
        )
        if not equity_df.empty:
            equity_df = equity_df.set_index('timestamp')

        trades_df = pd.DataFrame(
            [
                {
                    'timestamp': trade.timestamp,
                    'symbol': trade.symbol,
                    'side': trade.side.value,
                    'quantity': trade.quantity,
                    'price': trade.price,
                    'commission': trade.commission,
                    'stamp_duty': trade.stamp_duty,
                    'pnl': trade.pnl,
                }
                for trade in self.broker.trades
            ]
        )

        orders_df = pd.DataFrame(
            [
                {
                    'submitted_at': order.submitted_at,
                    'symbol': order.symbol,
                    'side': order.side.value,
                    'quantity': order.quantity,
                    'price': order.price,
                    'status': order.status.value,
                    'filled_at': order.filled_at,
                    'filled_price': order.filled_price,
                    'reject_reason': order.reject_reason,
                }
                for order in self.broker.orders
            ]
        )

        positions_df = pd.DataFrame(self.position_rows)
        equity_series = equity_df['total_equity'] if not equity_df.empty else pd.Series(dtype=float)
        metrics = compute_core_metrics(equity_series, trades_df)

        return {
            'strategy_name': strategy_name,
            'metrics': metrics,
            'equity': equity_df,
            'orders': orders_df,
            'trades': trades_df,
            'positions': positions_df,
            'logs': self.logs,
        }
