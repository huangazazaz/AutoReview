"""主备降级数据源（包装器）。

按优先级持有多个 DataSource 实例，取数时依次尝试：
首个返回非空结果的源即采用，全部失败则返回空列表（与单源失败行为一致）。

注意：name 以 "_" 开头，registry 自动发现会跳过此类（见 registry._discover_plugins），
避免 FailoverDataSource 被当成普通数据源注册而被 --datasource 误选。
"""

from __future__ import annotations

import logging
from datetime import date

from autotrade.core.interfaces import DataSource
from autotrade.core.models import Bar

logger = logging.getLogger(__name__)


class FailoverDataSource(DataSource):
    """主备降级数据源：内部持有多源列表，按顺序尝试。"""

    name = "_failover"

    def __init__(self, sources: list[tuple[str, DataSource]] | None = None):
        """sources: [(name, datasource_instance), ...]，已按优先级排序。"""
        self._sources = sources or []
        if not self._sources:
            logger.warning("FailoverDataSource 未配置任何可用数据源")

    @property
    def source_names(self) -> list[str]:
        """当前持有的数据源名列表（便于调试/日志）。"""
        return [name for name, _ in self._sources]

    def get_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        """按顺序尝试各数据源，首个成功即返回。"""
        for name, ds in self._sources:
            try:
                bars = ds.get_bars(symbol, start, end)
                if bars:
                    logger.info(
                        "数据源 %s 取数成功: %s %d 根",
                        name, symbol, len(bars),
                    )
                    return bars
                logger.warning(
                    "数据源 %s 返回空，尝试下一个 (symbol=%s)", name, symbol,
                )
            except Exception as e:
                logger.warning(
                    "数据源 %s 异常，尝试下一个 (symbol=%s): %s",
                    name, symbol, e,
                )
        logger.error("所有数据源均失败 for %s", symbol)
        return []

    def list_symbols(self) -> list[str]:
        """按顺序尝试各数据源，首个返回非空结果即采用。"""
        for name, ds in self._sources:
            try:
                symbols = ds.list_symbols()
                if symbols:
                    logger.info(
                        "数据源 %s 列代码成功: %d 只", name, len(symbols),
                    )
                    return symbols
                logger.warning(
                    "数据源 %s list_symbols 返回空，尝试下一个", name,
                )
            except Exception as e:
                logger.warning(
                    "数据源 %s list_symbols 异常，尝试下一个: %s", name, e,
                )
        logger.error("所有数据源 list_symbols 均失败")
        return []
