from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType

from .class_adapter import ClassStrategyAdapter
from .script_adapter import ScriptStrategyAdapter


def _load_module(path: str | Path) -> ModuleType:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f'策略文件不存在: {file_path}')

    spec = spec_from_file_location(file_path.stem, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f'无法加载策略文件: {file_path}')

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_strategy(path: str | Path):
    module = _load_module(path)

    if hasattr(module, 'handle_bar'):
        return ScriptStrategyAdapter(module)

    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and callable(getattr(attr, 'on_bar', None)):
            return ClassStrategyAdapter(attr())

    raise ValueError('未找到可用的策略入口，请提供类式 on_bar 或脚本式 handle_bar')
