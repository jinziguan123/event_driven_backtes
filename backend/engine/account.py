from __future__ import annotations

from dataclasses import dataclass, field

from event_driven_backtest.backend.core.models import AccountState, Position


@dataclass(slots=True)
class TradingAccount:
    state: AccountState
    positions: dict[str, Position] = field(default_factory=dict)

    @property
    def cash(self) -> float:
        return self.state.cash

    @cash.setter
    def cash(self, value: float) -> None:
        self.state.cash = value
