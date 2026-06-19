"""AkShare 数据源实现（默认，免费）。

使用 AkShare API 获取 A 股日线数据，输出统一 Bar 格式。
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from autotrade.core.interfaces import DataSource
from autotrade.core.models import Bar

logger = logging.getLogger(__name__)


class AkShareDataSource(DataSource):
    """基于 AkShare 的数据源。"""

    name = "akshare"

    def __init__(self, auto_adjust: bool = True):
        self.auto_adjust = auto_adjust

    def get_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        """获取 A 股日线数据（前复权）。"""
        import akshare as ak

        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust="qfq" if self.auto_adjust else "",
            )
        except Exception as e:
            logger.error("AkShare get_bars failed for %s: %s", symbol, e)
            return []

        if df is None or df.empty:
            return []

        bars = []
        for _, row in df.iterrows():
            try:
                bar = Bar(
                    symbol=symbol,
                    date=row["日期"].date() if isinstance(row["日期"], datetime) else row["日期"],
                    open=float(row["开盘"]),
                    high=float(row["最高"]),
                    low=float(row["最低"]),
                    close=float(row["收盘"]),
                    volume=float(row["成交量"]),
                    amount=float(row["成交额"]),
                )
                bars.append(bar)
            except Exception as e:
                logger.warning("Skipping row for %s: %s", symbol, e)
                continue

        return bars

    def list_symbols(self) -> list[str]:
        """列出全市场股票代码。"""
        import akshare as ak
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                return df["代码"].tolist()
        except Exception as e:
            logger.error("AkShare list_symbols failed: %s", e)
        return []
