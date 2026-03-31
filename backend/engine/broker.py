from __future__ import annotations

from datetime import date, datetime

from event_driven_backtest.backend.core.config import BacktestConfig
from event_driven_backtest.backend.core.models import AccountState, Order, OrderSide, OrderStatus, PortfolioSnapshot, Position, Trade
from .account import TradingAccount


class Broker:
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.account = TradingAccount(AccountState(cash=config.initial_cash, total_equity=config.initial_cash))
        self.orders: list[Order] = []
        self.trades: list[Trade] = []
        self._current_date: date | None = None

    def on_new_bar(self, timestamp: datetime) -> None:
        current_date = timestamp.date()
        if self._current_date is None:
            self._current_date = current_date
            return
        if current_date != self._current_date:
            for position in self.account.positions.values():
                position.sellable_quantity = position.quantity
            self._current_date = current_date

    def active_position_count(self) -> int:
        return sum(1 for position in self.account.positions.values() if position.quantity > 0)

    def reject_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        timestamp: datetime,
        price: float | None = None,
        reason: str = '',
    ) -> Order:
        order = Order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            submitted_at=timestamp,
            price=price,
            status=OrderStatus.REJECTED,
            reject_reason=reason,
        )
        self.orders.append(order)
        return order

    def buy(self, symbol: str, price: float, quantity: int, timestamp: datetime | None = None) -> Order:
        ts = timestamp or datetime.now()
        position = self.account.positions.get(symbol)
        if (position is None or position.quantity == 0) and self.active_position_count() >= self.config.max_positions:
            return self.reject_order(symbol, OrderSide.BUY, quantity, ts, price=price, reason='超过最大持仓数')

        commission = price * quantity * self.config.commission
        total_cost = price * quantity + commission
        if total_cost > self.account.cash:
            return self.reject_order(symbol, OrderSide.BUY, quantity, ts, price=price, reason='资金不足')

        position = self.account.positions.setdefault(symbol, Position(symbol=symbol, last_updated=ts))
        new_quantity = position.quantity + quantity
        if new_quantity > 0:
            position.avg_cost = ((position.avg_cost * position.quantity) + (price * quantity)) / new_quantity
        position.quantity = new_quantity
        position.last_updated = ts
        if not self.config.enable_t1:
            position.sellable_quantity += quantity

        self.account.cash -= total_cost
        self.account.state.cumulative_commission += commission

        trade = Trade(symbol=symbol, side=OrderSide.BUY, quantity=quantity, price=price, timestamp=ts, commission=commission)
        self.trades.append(trade)
        order = Order(symbol=symbol, side=OrderSide.BUY, quantity=quantity, submitted_at=ts, price=price, status=OrderStatus.FILLED, filled_at=ts, filled_price=price)
        self.orders.append(order)
        return order

    def sell(self, symbol: str, price: float, quantity: int, timestamp: datetime | None = None) -> Order:
        ts = timestamp or datetime.now()
        position = self.account.positions.get(symbol)
        if position is None or position.quantity < quantity:
            return self.reject_order(symbol, OrderSide.SELL, quantity, ts, price=price, reason='持仓不足')
        if position.sellable_quantity < quantity:
            return self.reject_order(symbol, OrderSide.SELL, quantity, ts, price=price, reason='T+1 限制')

        avg_cost = position.avg_cost
        commission = price * quantity * self.config.commission
        stamp_duty = price * quantity * self.config.stamp_duty
        proceeds = price * quantity - commission - stamp_duty

        position.quantity -= quantity
        position.sellable_quantity -= quantity
        position.last_updated = ts
        if position.quantity == 0:
            position.avg_cost = 0.0

        self.account.cash += proceeds
        self.account.state.cumulative_commission += commission
        self.account.state.cumulative_stamp_duty += stamp_duty

        trade = Trade(
            symbol=symbol,
            side=OrderSide.SELL,
            quantity=quantity,
            price=price,
            timestamp=ts,
            commission=commission,
            stamp_duty=stamp_duty,
            pnl=(price - avg_cost) * quantity - commission - stamp_duty,
        )
        self.trades.append(trade)
        order = Order(symbol=symbol, side=OrderSide.SELL, quantity=quantity, submitted_at=ts, price=price, status=OrderStatus.FILLED, filled_at=ts, filled_price=price)
        self.orders.append(order)
        return order

    def mark_to_market(self, prices: dict[str, float], timestamp: datetime) -> PortfolioSnapshot:
        market_value = 0.0
        for symbol, position in self.account.positions.items():
            last_price = prices.get(symbol, position.avg_cost)
            position.market_value = position.quantity * last_price
            position.unrealized_pnl = (last_price - position.avg_cost) * position.quantity
            position.last_updated = timestamp
            market_value += position.market_value

        total_equity = self.account.cash + market_value
        self.account.state.market_value = market_value
        self.account.state.total_equity = total_equity
        position_ratio = market_value / total_equity if total_equity else 0.0
        return PortfolioSnapshot(
            timestamp=timestamp,
            cash=self.account.cash,
            market_value=market_value,
            total_equity=total_equity,
            position_ratio=position_ratio,
        )
