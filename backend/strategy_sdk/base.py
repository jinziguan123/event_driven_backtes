from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseStrategyAdapter(ABC):
    name: str = 'unnamed_strategy'

    def initialize(self, context: dict[str, Any]) -> None:
        return None

    @abstractmethod
    def on_bar(self, context: dict[str, Any], bars: Any):
        raise NotImplementedError

    def after_trading(self, context: dict[str, Any]) -> None:
        return None
