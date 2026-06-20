"""Tushare Pro 数据源实现（可选，需 token）。

使用 Tushare Pro API 获取 A 股日线数据，输出统一 Bar 格式。
依赖 tushare 为可选 extra（pyproject.toml 中声明），故采用延迟 import。

token 来源（优先级低→高）：
1. 构造参数 token
2. 配置 datasource.sources.tushare.token
3. 环境变量 AUTOTRADE__DATASOURCE__SOURCES__TUSHARE__TOKEN
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from autotrade.core.interfaces import DataSource
from autotrade.core.models import Bar

logger = logging.getLogger(__name__)


def _to_ts_code(symbol: str) -> str:
    """6 位纯代码补市场后缀 → Tushare 的 ts_code。

    规则：
    - 6/9 开头 → 上交所 .SH（如 600519、900901）
    - 4/8 开头 → 北交所 .BJ（如 830799）
    - 其余 → 深交所 .SZ（如 000001、300750）
    已含后缀（如 000001.SZ）则原样返回。
    """
    if "." in symbol:
        return symbol
    head = symbol[0]
    if head in ("6", "9"):
        return f"{symbol}.SH"
    if head in ("4", "8"):
        return f"{symbol}.BJ"
    return f"{symbol}.SZ"


class TushareDataSource(DataSource):
    """基于 Tushare Pro 的数据源。"""

    name = "tushare"

    def __init__(self, token: str = "", auto_adjust: bool = True):
        self.token = token or ""
        self.auto_adjust = auto_adjust

    def _build_pro(self):
        """惰性构建 Tushare pro 接口。"""
        import tushare as ts

        if not self.token:
            return None
        ts.set_token(self.token)
        return ts.pro_api()

    def get_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        """获取 A 股日线数据（不复权；前复权需 Tushare 付费账户解除 adj_factor 限流）。"""
        if not self.token:
            logger.info("Tushare 未配置 token，跳过 %s", symbol)
            return []

        try:
            pro = self._build_pro()
            if pro is None:
                return []

            ts_code = _to_ts_code(symbol)
            start_date = start.strftime("%Y%m%d")
            end_date = end.strftime("%Y%m%d")

            # 统一用 pro.daily() 获取不复权数据
            # pro_bar(adj='qfq') 内部会多次调用 adj_factor，免费账户限流极严（1 次/分钟），
            # 跨多个月时必然失败。升级 Tushare 付费账户后可启用 pro_bar。
            df = pro.daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            logger.error("Tushare get_bars failed for %s: %s", symbol, e)
            return []

        if df is None or df.empty:
            logger.info("Tushare 返回空数据: %s %s~%s", symbol, start, end)
            return []

        bars = []
        for _, row in df.iterrows():
            try:
                trade_date = row["trade_date"]
                # Tushare trade_date 为 "YYYYMMDD" 字符串，统一转 date
                if isinstance(trade_date, str):
                    bar_date = datetime.strptime(trade_date, "%Y%m%d").date()
                elif isinstance(trade_date, datetime):
                    bar_date = trade_date.date()
                else:
                    bar_date = trade_date

                # Tushare amount 单位为千元，转成元以与 AkShare 对齐
                amount = float(row.get("amount", 0.0)) * 1000.0
                bar = Bar(
                    symbol=symbol,
                    date=bar_date,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["vol"]),
                    amount=amount,
                )
                bars.append(bar)
            except Exception as e:
                logger.warning("Skipping row for %s: %s", symbol, e)
                continue

        # Tushare 默认按交易日降序返回，统一升序（与 AkShare 一致）
        bars.sort(key=lambda b: b.date)
        logger.info(
            "Tushare 成功获取 %s: %d 根 %s~%s",
            symbol, len(bars), start, end,
        )
        return bars

    def list_symbols(self) -> list[str]:
        """列出全市场股票代码。"""
        if not self.token:
            logger.info("Tushare 未配置 token，list_symbols 跳过")
            return []

        try:
            pro = self._build_pro()
            if pro is None:
                return []
            df = pro.stock_basic(exchange="", list_status="L",
                                 fields="ts_code,symbol,name")
        except Exception as e:
            logger.error("Tushare list_symbols failed: %s", e)
            return []

        if df is None or df.empty:
            return []

        # symbol 为 6 位纯代码，去掉可能的后缀
        return [str(s).split(".")[0] for s in df["symbol"].tolist()]
