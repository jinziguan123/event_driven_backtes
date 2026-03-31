from __future__ import annotations

from dataclasses import dataclass

from . import indicators


@dataclass(slots=True)
class TdxRuntime:
    symbol: str | None = None

    def __getattr__(self, item):
        try:
            return getattr(indicators, item)
        except AttributeError as exc:
            raise AttributeError(f'未实现的通达信函数: {item}') from exc
