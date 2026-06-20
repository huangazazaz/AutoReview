"""编排层 —— 串联数据获取 → 指标计算 → 策略信号 → 回测 → 报告。

核心函数:
- analyze_stock(): 单股分析+回测，最基础入口
- analyze_universe(): 批量回测一组股票
- run_backtest(): 顶层入口，支持单股/多股/全市场，渲染报告
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from autotrade.core.backtester import Backtester
from autotrade.core.config import get_backtest_config, load_config
from autotrade.core.datasource_factory import (
    FAILOVER_NAME, build_datasource_from_name,
)
from autotrade.core.interfaces import DataSource, Indicator, Reporter, Strategy
from autotrade.core.models import BacktestConfig, BacktestResult, Signal
from autotrade.registry import (
    get_datasource, get_indicator, get_reporter, get_strategy,
    init_registry, list_strategies,
)

logger = logging.getLogger(__name__)


def analyze_stock(
    symbol: str,
    strategy_name: str,
    start: date,
    end: date,
    datasource_name: str = FAILOVER_NAME,
    backtest_config: Optional[BacktestConfig] = None,
    strategy_params: Optional[dict] = None,
    stock_name: str = "",
) -> BacktestResult:
    """单股分析+回测。最基础入口，被其他所有触发方式复用。

    Args:
        symbol: 股票代码。
        strategy_name: 策略名。
        start: 开始日期。
        end: 结束日期。
        datasource_name: 数据源名。
        backtest_config: 回测配置，None 则从全局配置加载。
        strategy_params: 策略参数，None 则从 YAML 加载。

    Returns:
        BacktestResult 包含成交记录、净值曲线、汇总指标。
    """
    # 1. 获取插件（datasource_name="failover"/None 走主备降级，其余单源）
    ds = build_datasource_from_name(datasource_name)

    strategy_cls = get_strategy(strategy_name)
    strategy = _instantiate_strategy(strategy_cls, strategy_params)

    # 2. 获取行情数据
    bars = ds.get_bars(symbol, start, end)
    if not bars:
        logger.warning("No bar data for %s from %s to %s", symbol, start, end)
        return BacktestResult(symbol=symbol, stock_name=stock_name,
                              metrics={"error": "No data"})

    # 3. list[Bar] → DataFrame
    df = _bars_to_dataframe(bars)

    # 4. 计算指标
    for ind in strategy.required_indicators:
        df = ind.compute(df)

    # 5. 生成信号（填充 symbol）
    raw_signals = strategy.generate_signals(df)
    for sig in raw_signals:
        if not sig.symbol:
            sig.symbol = symbol

    # 6. 回测撮合
    config = backtest_config or _make_backtest_config()
    backtester = Backtester(config)
    result = backtester.run(raw_signals, bars)
    result.signals = raw_signals
    result.stock_name = stock_name

    logger.info(
        "Analyzed %s with %s: %d trades, return %.2f%%",
        symbol, strategy_name, len(result.trades),
        result.metrics.get("total_return_pct", 0.0),
    )

    return result


def analyze_universe(
    symbols: list[str],
    strategy_name: str,
    start: date,
    end: date,
    datasource_name: str = FAILOVER_NAME,
    backtest_config: Optional[BacktestConfig] = None,
    strategy_params: Optional[dict] = None,
    stock_names: dict[str, str] | None = None,
) -> list[BacktestResult]:
    """批量回测一组股票。"""
    names = stock_names or {}
    results: list[BacktestResult] = []
    for symbol in symbols:
        try:
            result = analyze_stock(
                symbol, strategy_name, start, end,
                datasource_name, backtest_config, strategy_params,
                stock_name=names.get(symbol, ""),
            )
            results.append(result)
        except Exception as e:
            logger.error("Failed to analyze %s: %s", symbol, e)
            results.append(BacktestResult(
                symbol=symbol,
                stock_name=names.get(symbol, ""),
                metrics={"error": str(e)},
            ))
    return results


def run_backtest(
    strategy_name: str,
    symbols: str | list[str] = "all",
    start: Optional[date] = None,
    end: Optional[date] = None,
    datasource_name: str = FAILOVER_NAME,
    backtest_config: Optional[BacktestConfig] = None,
    strategy_params: Optional[dict] = None,
    reporter_names: tuple[str, ...] = ("console",),
    stock_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """顶层入口：支持单股/多股/全市场，渲染报告，返回汇总。

    Args:
        strategy_name: 策略名。
        symbols: 股票代码列表，"all" 表示全市场。
        start: 开始日期。
        end: 结束日期。
        datasource_name: 数据源名。
        backtest_config: 回测配置。
        strategy_params: 策略参数。
        reporter_names: 报告输出方式列表。
        stock_names: 代码→名称映射（可选，用于分组回测显示名称）。

    Returns:
        汇总字典。
    """
    # 确保注册表已初始化
    init_registry()

    # 解析日期
    if end is None:
        end = date.today()
    if start is None:
        start = date(end.year - 1, end.month, end.day)

    # 解析符号
    resolved_symbols = _resolve_symbols(symbols, datasource_name)

    if not resolved_symbols:
        return {"error": "No symbols to analyze", "results": []}

    # 运行回测
    if len(resolved_symbols) == 1:
        names = stock_names or {}
        result = analyze_stock(
            resolved_symbols[0], strategy_name, start, end,
            datasource_name, backtest_config, strategy_params,
            stock_name=names.get(resolved_symbols[0], ""),
        )
        results_list = [result]
    else:
        results_list = analyze_universe(
            resolved_symbols, strategy_name, start, end,
            datasource_name, backtest_config, strategy_params,
            stock_names=stock_names,
        )

    # 渲染报告
    for result in results_list:
        for rep_name in reporter_names:
            try:
                reporter_cls = get_reporter(rep_name)
                reporter = reporter_cls() if isinstance(reporter_cls, type) else reporter_cls
                reporter.render(result)
            except Exception as e:
                logger.error("Reporter '%s' failed: %s", rep_name, e)

    # 汇总
    summary = _summarize(results_list)
    return summary


def _bars_to_dataframe(bars) -> pd.DataFrame:
    """将 list[Bar] 转为 DataFrame。"""
    records = []
    for bar in bars:
        records.append({
            "date": bar.date,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "amount": bar.amount,
        })
    df = pd.DataFrame(records)
    if "date" in df.columns and not df.empty:
        df.set_index("date", inplace=True)
    return df


def _resolve_symbols(symbols: str | list[str],
                     datasource_name: str = "akshare") -> list[str]:
    """解析符号参数为列表。"""
    if isinstance(symbols, list):
        return symbols
    if symbols == "all":
        ds = build_datasource_from_name(datasource_name)
        return ds.list_symbols()
    return [s.strip() for s in symbols.split(",") if s.strip()]


def _make_backtest_config() -> BacktestConfig:
    """从全局配置创建 BacktestConfig。"""
    cfg = load_config(force_reload=True)
    bc = get_backtest_config(cfg)
    return BacktestConfig(
        initial_capital=float(bc.get("initial_capital", 100000)),
        fill_price=str(bc.get("fill_price", "next_open")),
        commission_rate=float(bc.get("commission_rate", 0.0003)),
        stamp_duty_rate=float(bc.get("stamp_duty_rate", 0.001)),
        slippage=float(bc.get("slippage", 0.001)),
        min_commission=float(bc.get("min_commission", 5.0)),
        lot_size=int(bc.get("lot_size", 100)),
        allow_t_plus_1=bool(bc.get("allow_t_plus_1", True)),
        position_sizing=str(bc.get("position_sizing", "strength")),
        max_positions=int(bc.get("max_positions", 1)),
    )


def _instantiate_strategy(strategy_cls: type, params: Optional[dict] = None) -> Strategy:
    """实例化策略，应用参数。"""
    if params:
        return strategy_cls(**params)
    return strategy_cls()


def _summarize(results: list[BacktestResult]) -> dict[str, Any]:
    """汇总多个回测结果。"""
    valid = [r for r in results if r.metrics and "error" not in r.metrics]
    errors = [r for r in results if r.metrics and "error" in r.metrics]

    summary: dict[str, Any] = {
        "total": len(results),
        "success": len(valid),
        "failed": len(errors),
        "results": [],
    }

    if valid:
        returns_list = [float(r.metrics.get("total_return_pct", 0)) for r in valid]
        summary["avg_return_pct"] = round(sum(returns_list) / len(returns_list), 2)
        summary["positive_count"] = sum(1 for r in returns_list if r > 0)
        summary["negative_count"] = sum(1 for r in returns_list if r <= 0)

        # 最佳 / 最差
        best_idx = max(range(len(returns_list)), key=lambda i: returns_list[i])
        worst_idx = min(range(len(returns_list)), key=lambda i: returns_list[i])
        summary["best_symbol"] = valid[best_idx].symbol
        summary["best_return"] = returns_list[best_idx]
        summary["worst_symbol"] = valid[worst_idx].symbol
        summary["worst_return"] = returns_list[worst_idx]

    for r in valid:
        summary["results"].append({
            "symbol": r.symbol,
            "stock_name": r.stock_name or "",
            "trades": len(r.trades),
            "return_pct": r.metrics.get("total_return_pct", 0),
            "sharpe": r.metrics.get("sharpe_ratio", 0),
            "max_drawdown_pct": r.metrics.get("max_drawdown_pct", 0),
            "win_rate": r.metrics.get("win_rate", 0),
        })

    return summary
