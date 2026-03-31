from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from threading import Lock
import time


REPO_ROOT = Path(__file__).resolve().parents[3]
STRATEGY_DIR = REPO_ROOT / 'event_driven_backtest' / 'backend' / 'strategies'
CACHE_TTL_SECONDS = 1.0
_strategy_cache_lock = Lock()
_strategy_cache: dict[str, tuple[float, list[dict[str, str]]]] = {}


def clear_strategy_cache() -> None:
    with _strategy_cache_lock:
        _strategy_cache.clear()


def list_strategy_files(strategy_dir: str | Path | None = None) -> list[dict[str, str]]:
    resolved_dir = Path(strategy_dir) if strategy_dir is not None else STRATEGY_DIR
    cache_key = str(resolved_dir.resolve())
    now = time.monotonic()

    with _strategy_cache_lock:
        cached = _strategy_cache.get(cache_key)
        if cached is not None and cached[0] > now:
            return deepcopy(cached[1])

    strategies: list[dict[str, str]] = []
    for file_path in sorted(resolved_dir.glob('*.py')):
        if file_path.name == '__init__.py' or file_path.name.startswith('_'):
            continue
        relative_path = file_path.relative_to(REPO_ROOT) if file_path.is_relative_to(REPO_ROOT) else file_path
        strategies.append(
            {
                'name': file_path.stem,
                'path': str(relative_path),
            }
        )

    with _strategy_cache_lock:
        _strategy_cache[cache_key] = (now + CACHE_TTL_SECONDS, deepcopy(strategies))
    return strategies
