from __future__ import annotations

from types import ModuleType
from typing import Any

from .base import BaseStrategyAdapter


class ScriptStrategyAdapter(BaseStrategyAdapter):
    def __init__(self, module: ModuleType):
        self._module = module
        self.name = getattr(module, 'name', module.__name__)

    def initialize(self, context: dict[str, Any]) -> None:
        initializer = getattr(self._module, 'initialize', None)
        if callable(initializer):
            initializer(context)

    def on_bar(self, context: dict[str, Any], bars: Any):
        handler = getattr(self._module, 'handle_bar', None)
        if not callable(handler):
            raise AttributeError('脚本策略缺少 handle_bar(context, bars) 函数')
        return handler(context, bars)

    def after_trading(self, context: dict[str, Any]) -> None:
        hook = getattr(self._module, 'after_trading', None)
        if callable(hook):
            hook(context)
