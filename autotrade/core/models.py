"""数据模型：Bar / Signal / Trade / Position / BacktestResult / BacktestConfig。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd


@dataclass
class Bar:
    """单根K线（日线）。所有数据源的统一输出格式。"""
    symbol: str          # 股票代码，如 "000001"
    date: date           # 交易日期
    open: float
    high: float
    low: float
    close: float
    volume: float        # 成交量（股）
    amount: float        # 成交额（元）

    def __post_init__(self):
        for field_name in ("open", "high", "low", "close", "volume", "amount"):
            val = getattr(self, field_name)
            if val is not None:
                setattr(self, field_name, float(val))


@dataclass
class Signal:
    """策略在某一天产生的信号。"""
    symbol: str
    date: date
    action: str          # "BUY" | "SELL" | "SELL_SHORT" | "BUY_TO_COVER"
    strength: float = 1.0  # 信号强度 0~1，供仓位管理用
    reason: str = ""       # 人类可读的理由（如 "MA5上穿MA20"）


@dataclass
class Trade:
    """回测中实际成交的一笔交易。"""
    symbol: str
    date: date
    action: str          # "BUY" | "SELL" | "SELL_SHORT" | "BUY_TO_COVER"
    price: float         # 实际成交价（考虑滑点）
    quantity: int        # 成交股数（A股需100股整数倍）
    commission: float    # 手续费
    stamp_duty: float = 0.0  # 印花税（仅卖出时产生）


@dataclass
class Position:
    """某时刻的持仓快照，支持多空双向。"""
    symbol: str
    long_qty: int = 0            # 多头持仓股数
    long_avg_cost: float = 0.0    # 多头持仓均价
    short_qty: int = 0           # 空头持仓股数
    short_avg_cost: float = 0.0   # 空头持仓均价

    @property
    def net_qty(self) -> int:
        return self.long_qty - self.short_qty


@dataclass
class BacktestConfig:
    """回测撮合配置。"""
    initial_capital: float = 100_000.0     # 初始资金
    fill_price: str = "next_open"          # "next_open" | "close"
    commission_rate: float = 0.0003        # 佣金费率（万三）
    stamp_duty_rate: float = 0.001         # 印花税（仅卖出千一）
    slippage: float = 0.001               # 滑点（千一）
    min_commission: float = 5.0           # 单笔最低佣金 5 元
    lot_size: int = 100                   # A 股一手 100 股
    allow_t_plus_1: bool = True           # T+1：当日买入次日才能卖
    position_sizing: str = "strength"     # "full" | "strength"
    max_positions: int = 1                # 最大同时持仓股票数
    allow_short: bool = False             # 是否允许做空
    short_margin_ratio: float = 1.0       # 融券保证金比例（1.0 = 100%）
    short_interest_rate: float = 0.085    # 融券年化利率


@dataclass
class BacktestResult:
    """回测结果，传给 Reporter 输出。"""
    symbol: str
    trades: list[Trade] = field(default_factory=list)
    equity_curve: Optional[pd.Series] = None  # 净值曲线（按日期）
    metrics: dict = field(default_factory=dict)  # 收益率/胜率/最大回撤/夏普等
    signals: list[Signal] = field(default_factory=list)  # 产生的所有信号
    stock_name: str = ""  # 股票名称（可选）
    close_prices: Optional[pd.Series] = None  # 收盘价序列（按日期，用于前端叠加显示）

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {}


@dataclass
class ScreenItem:
    """单只股票的选股结果。"""
    symbol: str
    name: str = ""
    score: float = 0.0
    signal_tag: str = ""
    factor_breakdown: dict = field(default_factory=dict)        # {因子名: 得分}
    buy_signal: Optional[dict] = None                            # {"date": str, "action": str, "strength": float, "reason": str}
    key_metrics: dict = field(default_factory=dict)              # {"close": ..., "volume": ..., ...}


@dataclass
class ScreenResult:
    """选股扫描完整结果。"""
    date: str = ""
    screener: str = ""
    strategy: str = ""
    universe_size: int = 0
    candidates: int = 0
    with_buy_signal: int = 0
    results: list[ScreenItem] = field(default_factory=list)
