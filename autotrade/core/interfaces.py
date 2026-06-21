"""插件抽象基类：DataSource / Indicator / Strategy / Reporter / Screener。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

import pandas as pd

from autotrade.core.models import Bar, BacktestResult, Signal


class DataSource(ABC):
    """数据源插件：把外部数据统一成 Bar 序列。"""

    @abstractmethod
    def get_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        """获取指定股票在日期范围内的日线数据（前复权）。"""

    @abstractmethod
    def list_symbols(self) -> list[str]:
        """列出全市场股票代码（用于全市场回测）。"""


class Indicator(ABC):
    """指标插件：在含 Bar 列的 DataFrame 上追加指标列。
    输入输出都是 DataFrame，便于多个指标链式追加（列名 ind_<name>_<field>）。"""
    name: str = "base"           # 指标名，如 "ma"
    params: dict = {}            # 参数，如 {"period": 20}

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """输入含 OHLCV 列的 df，返回追加了指标列的 df。"""


class Strategy(ABC):
    """策略插件：声明所需指标，在含指标 DataFrame 上产生 Signal 序列。"""
    name: str = "base"
    required_indicators: list[Indicator] = []  # 编排层据此先算好指标列

    def __init__(self):
        self.required_indicators = []

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        """df 是已计算好所需指标的 DataFrame；返回每日信号列表。"""


class Reporter(ABC):
    """报告插件：消费 BacktestResult，输出到不同媒介。"""

    @abstractmethod
    def render(self, result: BacktestResult) -> None:
        """输出报告（终端/CSV/图表）。"""


class Screener(ABC):
    """选股筛网插件：横向比较全市场，每日选出候选票。

    与 Strategy 的区别：
    - Strategy 是"给定一只票在其上择时"（纵向），接收单股 df。
    - Screener 是"比较全市场挑出当日候选"（横向），接收 {symbol: df} 字典。
    - 职责切分：Screener 答"今天买谁"，Strategy 答"买了什么时候卖"。
    """

    name: str = "base"
    required_indicators: list[Indicator] = []

    def __init__(self):
        self.required_indicators = []

    @abstractmethod
    def scan(self, market_data: dict[str, pd.DataFrame],
             dates: list[date]) -> dict[date, list[tuple[str, float, str]]]:
        """扫描全市场，逐日选出候选票。

        Args:
            market_data: {symbol: OHLCV DataFrame}，每个 df 已算好 required_indicators。
                每个 DataFrame 的 index 为日期（DatetimeIndex 或 date 序列），
                含 open/high/low/close/volume 列 + ind_xxx 指标列。
            dates: 待扫描的交易日列表（升序）。

        Returns:
            {date: [(symbol, score, signal_type), ...]}
            每日按 score 降序排列的候选列表，signal_type 为 "breakout"/"reversal"。
        """
