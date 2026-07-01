"""插件注册表与自动发现机制。

支持四类插件：DataSource / Indicator / Strategy / Reporter。
每类维护一个 name → class 的 dict。
Auto-discover: 扫描 plugindir 下所有 .py 模块，找出符合接口的类。
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Optional

from autotrade.core.interfaces import (
    DataSource, Indicator, Reporter, Screener, Strategy,
)

# 注册表存储
_datasources: dict[str, type[DataSource]] = {}
_indicators: dict[str, type[Indicator]] = {}
_strategies: dict[str, type[Strategy]] = {}
_reporters: dict[str, type[Reporter]] = {}
_screens: dict[str, type[Screener]] = {}

# 初始化标志
_initialized = False

# ── 内置策略（系统自带，不可删除/覆盖）──────────────────────────────
_BUILTIN_STRATEGIES: set[str] = {
    "turtle", "ma_cross", "ma_cross_macd", "hot_money",
    "golden_filter", "trend_ma_breakout", "trend_bb_rsi", "macd_divergence",
}

# ── 内置分组（系统自带，不可删除/修改）──────────────────────────────
_BUILTIN_GROUPS: set[str] = {"银行", "科技", "通信", "自选"}


def is_builtin_strategy(name: str) -> bool:
    """Check whether a strategy name belongs to the built-in set."""
    return name in _BUILTIN_STRATEGIES


def is_builtin_group(name: str) -> bool:
    """Check whether a group name belongs to the built-in set."""
    return name in _BUILTIN_GROUPS


def _discover_plugins(package_name: str, base_class: type,
                      registry: dict[str, type]) -> None:
    """扫描指定包下所有模块，找出 base_class 的子类并注册。"""
    try:
        package = importlib.import_module(package_name)
    except ImportError:
        return  # 包不存在，跳过

    prefix = package.__name__ + "."
    for importer, modname, ispkg in pkgutil.iter_modules(
        package.__path__, prefix
    ):
        try:
            module = importlib.import_module(modname)
        except Exception as e:
            continue  # 跳过加载失败的模块

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (issubclass(obj, base_class) and obj is not base_class
                    and not inspect.isabstract(obj)):
                # 获取实例以读取 name 属性
                try:
                    instance = obj() if base_class in (Indicator, Strategy) else obj
                    key = instance.name if hasattr(instance, 'name') else name.lower()
                except Exception:
                    key = name.lower()
                # 跳过内部包装器类（如 FailoverDataSource 的 name="_failover"），
                # 避免被当成普通插件注册而被 --datasource 误选。
                if isinstance(key, str) and key.startswith("_"):
                    continue
                registry[key] = obj


def init_registry(force: bool = False) -> None:
    """初始化注册表：扫描所有插件目录。"""
    global _initialized
    if _initialized and not force:
        return
    _initialized = True

    # 清空并重新发现
    _datasources.clear()
    _indicators.clear()
    _strategies.clear()
    _reporters.clear()
    _screens.clear()

    _discover_plugins("autotrade.dataSources", DataSource, _datasources)
    _discover_plugins("autotrade.indicators", Indicator, _indicators)
    _discover_plugins("autotrade.strategies", Strategy, _strategies)
    _discover_plugins("autotrade.reporters", Reporter, _reporters)
    _discover_plugins("autotrade.screens", Screener, _screens)


# --- 注册（手动注册，供插件 __init__ 使用）---

def register_datasource(name: str, cls: type[DataSource]) -> None:
    _datasources[name] = cls


def register_indicator(name: str, cls: type[Indicator]) -> None:
    _indicators[name] = cls


def register_strategy(name: str, cls: type[Strategy]) -> None:
    _strategies[name] = cls


def register_reporter(name: str, cls: type[Reporter]) -> None:
    _reporters[name] = cls


# --- 查询 ---

def get_datasource(name: str) -> type[DataSource]:
    if not _initialized:
        init_registry()
    if name not in _datasources:
        raise KeyError(f"DataSource '{name}' not found. Available: {list(_datasources)}")
    return _datasources[name]


def get_indicator(name: str) -> type[Indicator]:
    if not _initialized:
        init_registry()
    if name not in _indicators:
        raise KeyError(f"Indicator '{name}' not found. Available: {list(_indicators)}")
    return _indicators[name]


def get_strategy(name: str) -> type[Strategy]:
    if not _initialized:
        init_registry()
    if name not in _strategies:
        raise KeyError(f"Strategy '{name}' not found. Available: {list(_strategies)}")
    return _strategies[name]


def get_reporter(name: str) -> type[Reporter]:
    if not _initialized:
        init_registry()
    if name not in _reporters:
        raise KeyError(f"Reporter '{name}' not found. Available: {list(_reporters)}")
    return _reporters[name]


# --- 列表 ---

def list_datasources() -> list[str]:
    if not _initialized:
        init_registry()
    return list(_datasources)


def list_indicators() -> list[str]:
    if not _initialized:
        init_registry()
    return list(_indicators)


def list_strategies() -> list[str]:
    if not _initialized:
        init_registry()
    return list(_strategies)


def list_reporters() -> list[str]:
    if not _initialized:
        init_registry()
    return list(_reporters)


# --- 批量获取 ---

def get_all_strategies() -> dict[str, type[Strategy]]:
    if not _initialized:
        init_registry()
    return dict(_strategies)


# --- Screener 注册与查询 ---

def register_screener(name: str, cls: type[Screener]) -> None:
    _screens[name] = cls


def get_screener(name: str) -> type[Screener]:
    if not _initialized:
        init_registry()
    if name not in _screens:
        raise KeyError(
            f"Screener '{name}' not found. Available: {list(_screens)}"
        )
    return _screens[name]


def list_screens() -> list[str]:
    if not _initialized:
        init_registry()
    return list(_screens)
