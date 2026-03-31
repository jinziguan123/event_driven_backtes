from __future__ import annotations

from typing import Any

from .base import BaseStrategyAdapter


class ClassStrategyAdapter(BaseStrategyAdapter):
    def __init__(self, strategy_instance: Any):
        self._strategy = strategy_instance
        self.name = getattr(strategy_instance, 'name', strategy_instance.__class__.__name__)

    def initialize(self, context: dict[str, Any]) -> None:
        initializer = getattr(self._strategy, 'initialize', None)
        if callable(initializer):
            initializer(context)

    def on_bar(self, context: dict[str, Any], bars: Any):
        return self._strategy.on_bar(context, bars)

    def after_trading(self, context: dict[str, Any]) -> None:
        hook = getattr(self._strategy, 'after_trading', None)
        if callable(hook):
            hook(context)
