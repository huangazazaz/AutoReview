"""数据源工厂：从配置实例化数据源，并构建主备降级包装器。

把"数据源实例化"逻辑收口在此，供 engine 复用：
- build_datasource(name): 单源实例化（注入 token 等参数）
- build_failover_datasource(): 按 priority 构建有序多源降级包装器
- build_datasource_from_name(name): 统一入口，name="failover" 走降级，其余走单源
"""

from __future__ import annotations

import logging
from typing import Any

from autotrade.core.config import load_config
from autotrade.core.interfaces import DataSource
from autotrade.dataSources.failover_ds import FailoverDataSource
from autotrade.dataSources.local_ds import CacheWriter, LocalDataSource
from autotrade.registry import get_datasource

logger = logging.getLogger(__name__)

# 需要从配置 sources.<name>.token 注入的数据源
_TOKEN_SOURCES = {"tushare"}

# 触发降级模式的特殊名字
FAILOVER_NAME = "failover"


def build_datasource(name: str, config: dict[str, Any] | None = None) -> DataSource:
    """根据配置实例化指定数据源。

    Args:
        name: 数据源名（如 "akshare" / "tushare"）。
        config: 全局配置，None 则从 load_config() 加载。

    Returns:
        数据源实例。
    """
    cls = get_datasource(name)
    cfg = config or load_config(force_reload=True)
    source_cfg = _get_source_config(name, cfg)

    if name in _TOKEN_SOURCES:
        token = str(source_cfg.get("token", "") or "")
        return cls(token=token)
    return cls()


def build_failover_datasource(
    config: dict[str, Any] | None = None,
) -> FailoverDataSource:
    """按 priority 构建有序多源降级包装器。

    读取 config["datasource"]["sources"]，按 priority 升序排序，
    跳过 enabled=False 的源，以及 tushare 无 token 的源。
    """
    cfg = config or load_config(force_reload=True)
    ds_cfg = cfg.get("datasource", {})
    sources_map = ds_cfg.get("sources", {}) or {}

    # 按 priority 升序（缺失默认 99）
    ordered = sorted(
        sources_map.items(),
        key=lambda kv: int(kv[1].get("priority", 99)),
    )

    instances: list[tuple[str, DataSource]] = []

    # ---- 1. 本地缓存源（优先级最高，始终在最前面）----
    local_cache = LocalDataSource(data_dir="data/daily")
    instances.append(("local", local_cache))

    # ---- 2. 网络数据源（按 priority 排序，每个包裹 CacheWriter 自动落盘）----
    for name, src_cfg in ordered:
        if not _is_source_usable(name, src_cfg):
            continue
        try:
            ds = build_datasource(name, cfg)
            # 包装：成功后自动写入本地 parquet 缓存
            wrapped = CacheWriter(ds, cache=local_cache)
            instances.append((name, wrapped))
        except Exception as e:
            logger.warning("无法构建数据源 %s: %s", name, e)

    logger.info("Failover 数据源顺序: %s",
                [n for n, _ in instances] or "(空)")
    return FailoverDataSource(instances)


def build_datasource_from_name(
    name: str | None,
    config: dict[str, Any] | None = None,
) -> DataSource:
    """统一入口：name 为 failover/None 走降级，其余走单源。

    被 engine.analyze_stock / _resolve_symbols 调用，集中处理实例化分支。
    """
    resolved = name or FAILOVER_NAME
    if resolved == "auto":
        resolved = FAILOVER_NAME
    if resolved == FAILOVER_NAME:
        return build_failover_datasource(config)
    return build_datasource(resolved, config)


def _get_source_config(name: str, config: dict[str, Any]) -> dict[str, Any]:
    """从 config["datasource"]["sources"][name] 取该源的子配置。"""
    ds_cfg = config.get("datasource", {}) or {}
    sources = ds_cfg.get("sources", {}) or {}
    return (sources.get(name) or {}) if isinstance(sources, dict) else {}


def _is_source_usable(name: str, src_cfg: dict[str, Any]) -> bool:
    """判断某数据源是否可用：enabled 且（需 token 的源已配 token）。"""
    if not src_cfg.get("enabled", True):
        logger.info("数据源 %s 已禁用 (enabled=false)", name)
        return False
    if name in _TOKEN_SOURCES and not src_cfg.get("token"):
        logger.info("数据源 %s 未配置 token，自动禁用", name)
        return False
    return True
