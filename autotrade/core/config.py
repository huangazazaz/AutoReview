"""配置加载（YAML + 环境变量覆盖）。

优先级（低 → 高）:
1. config/settings.yaml          ← 默认配置（提交 git）
2. 环境变量 AUTOTRADE_*           ← 部署/CI 覆盖
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# 项目根目录（通过 autotrade 包自身位置推导）
_CONFIG_DIR: Path = Path(__file__).resolve().parent.parent.parent / "config"
_DEFAULT_CONFIG_PATH: Path = _CONFIG_DIR / "settings.yaml"

# 默认配置（硬编码 fallback）
_DEFAULT_SETTINGS: dict[str, Any] = {
    "datasource": {
        "default": "akshare",
        "tushare": {"token": ""},
    },
    "cache": {
        "enabled": True,
        "dir": "data/cache",
    },
    "backtest": {
        "initial_capital": 100000,
        "fill_price": "next_open",
        "commission_rate": 0.0003,
        "stamp_duty_rate": 0.001,
        "slippage": 0.001,
        "min_commission": 5.0,
        "lot_size": 100,
        "allow_t_plus_1": True,
        "position_sizing": "strength",
        "max_positions": 1,
    },
    "paths": {
        "results_dir": "data/results",
        "cache_dir": "data/cache",
    },
    "logging": {
        "level": "INFO",
        "file": "data/logs/autotrade.log",
    },
}

_config_cache: dict[str, Any] | None = None


def _load_yaml_config(path: Path) -> dict[str, Any]:
    """从 YAML 文件加载配置，文件不存在时返回空字典。"""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """应用 AUTOTRADE_* 环境变量覆盖。

    环境变量名规则：AUTOTRADE__<SECTION>__<KEY>
    例: AUTOTRADE__BACKTEST__INITIAL_CAPITAL → config["backtest"]["initial_capital"]
    双下划线 __ 作为层级分隔符，避免与配置键内部的下划线冲突。
    """
    prefix = "AUTOTRADE__"
    for env_key, env_val in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        rest = env_key[len(prefix):].lower()
        parts = rest.split("__")
        if len(parts) < 2:
            continue

        # 尝试转为数值类型
        try:
            if "." in env_val:
                env_val = float(env_val)
            else:
                env_val = int(env_val)
        except ValueError:
            pass  # 保持字符串

        # 导航到配置深层位置
        target = config
        for part in parts[:-1]:
            if part not in target:
                target[part] = {}
            target = target[part]
        target[parts[-1]] = env_val

    return config


def load_config(path: Path | None = None, force_reload: bool = False) -> dict[str, Any]:
    """加载配置（含优先级叠加）。

    Args:
        path: 配置文件路径，默认 config/settings.yaml。
        force_reload: 忽略缓存强制重新加载。

    Returns:
        合并后的配置字典。
    """
    global _config_cache
    if _config_cache is not None and not force_reload:
        return _config_cache

    config = dict(_DEFAULT_SETTINGS)

    # 加载 YAML 文件覆盖
    yaml_path = path or _DEFAULT_CONFIG_PATH
    yaml_config = _load_yaml_config(yaml_path)
    _deep_merge(config, yaml_config)

    # 环境变量覆盖
    config = _apply_env_overrides(config)

    _config_cache = config
    return config


def _deep_merge(base: dict, override: dict) -> None:
    """深度合并字典（override 覆盖 base）。"""
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


def get_config() -> dict[str, Any]:
    """获取当前配置（快捷方式）。"""
    return load_config()


def get_backtest_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """从配置中提取回测子配置。"""
    cfg = config or load_config()
    return cfg.get("backtest", {})


def get_strategy_params(strategy_name: str) -> dict[str, Any]:
    """加载 config/strategies/<strategy_name>.yaml 的策略参数。"""
    path = _CONFIG_DIR / "strategies" / f"{strategy_name}.yaml"
    return _load_yaml_config(path)
