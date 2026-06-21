"""编排层 —— 串联数据获取 → 指标计算 → 策略信号 → 回测 → 报告。

核心函数:
- analyze_stock(): 单股分析+回测，最基础入口
- analyze_universe(): 批量回测一组股票
- run_backtest(): 顶层入口，支持单股/多股/全市场，渲染报告
- run_screener_backtest(): 游资两段式回测（先选股再择时）
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from autotrade.core.backtester import Backtester
from autotrade.core.config import get_backtest_config, get_strategy_params, load_config
from autotrade.core.datasource_factory import (
    FAILOVER_NAME, build_datasource_from_name,
)
from autotrade.core.interfaces import DataSource, Indicator, Reporter, Strategy
from autotrade.core.models import BacktestConfig, BacktestResult, Signal
from autotrade.registry import (
    get_datasource, get_indicator, get_reporter, get_screener,
    get_strategy, init_registry, list_strategies,
)
from autotrade.dataSources.local_ds import LocalDataSource

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
        end = date(2026, 6, 18)
    if start is None:
        start = date(2025, 1, 1)

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


# ---- 游资两段式回测 ----

_ST_CACHE: set | None = None


def _load_st_exclusion_set() -> set:
    """从 data/a_stock_list.csv 加载 ST/*ST 股票代码集合。"""
    global _ST_CACHE
    if _ST_CACHE is not None:
        return _ST_CACHE
    csv_path = (
        Path(__file__).resolve().parent.parent.parent
        / "data" / "a_stock_list.csv"
    )
    _ST_CACHE = set()
    if not csv_path.exists():
        return _ST_CACHE
    try:
        df = pd.read_csv(csv_path)
        if "code" in df.columns and "name" in df.columns:
            st_mask = df["name"].str.contains("ST", na=False)
            _ST_CACHE = set(str(c) for c in df.loc[st_mask, "code"])
        logger.info("ST 排除: %d 只", len(_ST_CACHE))
    except Exception as e:
        logger.warning("加载 ST 列表失败: %s", e)
    return _ST_CACHE


def _load_market_data(
    symbols: list[str],
    start: date,
    end: date,
    data_dir: str = "data/daily",
) -> dict[str, pd.DataFrame]:
    """批量加载全市场 OHLCV 到 {symbol: DataFrame}。

    直接读本地 parquet，不经网络。DataFrame index 为 DatetimeIndex。
    """
    ds = LocalDataSource(data_dir=data_dir)
    market: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            bars = ds.get_bars(sym, start, end)
            if bars:
                market[sym] = _bars_to_dataframe(bars)
        except Exception as e:
            logger.debug("加载 %s 失败: %s", sym, e)
    return market


def _load_screener_params(screener_name: str) -> dict[str, Any]:
    """加载 config/screens/<screener_name>.yaml 的参数。"""
    import yaml
    cfg_path = (
        Path(__file__).resolve().parent.parent.parent
        / "config" / "screens" / f"{screener_name}.yaml"
    )
    if not cfg_path.exists():
        return {}
    with open(cfg_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("params", {}) or {}


def _invert_selection(
    selection: dict[date, list[tuple[str, float, str]]],
) -> dict[str, list[date]]:
    """反转 {date: [(symbol,...)]} 为 {symbol: [date,...]}。"""
    inverted: dict[str, list[date]] = {}
    for d, picks in selection.items():
        for sym, _score, _type in picks:
            inverted.setdefault(sym, []).append(d)
    return inverted


def run_screener_backtest(
    screener_name: str,
    strategy_name: str,
    start: date,
    end: date,
    symbols: str | list[str] = "all",
    datasource_name: str = FAILOVER_NAME,
    screener_params: dict[str, Any] | None = None,
    strategy_params: dict[str, Any] | None = None,
    reporter_names: tuple[str, ...] = ("console",),
    stock_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """游资两段式回测: 先选股，再对选中票单股择时回测。

    流程:
      1. 加载全市场 OHLCV
      2. Screener.scan() → 每日候选 {date: [(symbol, score, type)]}
      3. 反转为 {symbol: [entry_dates]}
      4. 对每只选中 symbol 调 analyze_stock(strategy_params 含 allowed_entry_dates)
      5. 聚合统计

    Args:
        screener_name: 选股筛网名（如 "hot_money_screener"）。
        strategy_name: 择时策略名（如 "hot_money"）。
        start/end: 回测区间。
        symbols: "all" 用全市场，或代码列表。
        screener_params: Screener 参数，None 则从 YAML 加载。
        strategy_params: Strategy 出场参数（None 则 YAML），
            allowed_entry_dates 会被自动注入（覆盖用户值）。
    """
    init_registry()

    # ---- 1. 解析 symbols + 加载全市场数据 ----
    resolved = _resolve_symbols(symbols, datasource_name)
    if not resolved:
        return {"error": "No symbols to analyze", "results": []}

    # 排除 ST / *ST 股票
    st_exclude = _load_st_exclusion_set()
    if st_exclude:
        resolved = [s for s in resolved if s not in st_exclude]
        logger.info("排除 ST 后剩余 %d 只", len(resolved))
    if not resolved:
        return {"error": "All symbols excluded as ST", "results": []}

    market_data = _load_market_data(resolved, start, end)
    if not market_data:
        return {"error": "No market data loaded", "results": []}

    # 交易日序列（取所有票日期的并集，升序）
    all_dates: set[date] = set()
    for df in market_data.values():
        for v in df.index:
            d = v.date() if hasattr(v, "date") else v
            all_dates.add(d)
    scan_dates = sorted(all_dates)

    # ---- 2. 选股 ----
    s_params = screener_params
    if s_params is None:
        s_params = _load_screener_params(screener_name)
    screener_cls = get_screener(screener_name)
    screener = screener_cls(**s_params)
    selection = screener.scan(market_data, scan_dates)

    # ---- 3. 反转 ----
    symbol_to_entry_dates = _invert_selection(selection)
    logger.info(
        "Screener 选中 %d 只票，共 %d 个进场日",
        len(symbol_to_entry_dates),
        sum(len(v) for v in symbol_to_entry_dates.values()),
    )

    if not symbol_to_entry_dates:
        return {"error": "Screener selected no stocks", "results": []}

    # ---- 4. 对选中票单股回测 ----
    names = stock_names or {}
    results_list: list[BacktestResult] = []
    # 从 YAML 加载出场参数作为基准，用户传入的 strategy_params 可覆盖
    base_exit_params = get_strategy_params(strategy_name).get("params", {}) or {}
    for sym, entry_dates in symbol_to_entry_dates.items():
        merged_params: dict[str, Any] = dict(base_exit_params)
        if strategy_params:
            merged_params.update(strategy_params)
        merged_params["allowed_entry_dates"] = entry_dates
        try:
            result = analyze_stock(
                sym, strategy_name, start, end,
                datasource_name, None, merged_params,
                stock_name=names.get(sym, ""),
            )
            results_list.append(result)
        except Exception as e:
            logger.error("回测 %s 失败: %s", sym, e)
            results_list.append(BacktestResult(
                symbol=sym, stock_name=names.get(sym, ""),
                metrics={"error": str(e)},
            ))

    # ---- 5. 报告 + 汇总 ----
    for result in results_list:
        for rep_name in reporter_names:
            try:
                reporter_cls = get_reporter(rep_name)
                reporter = reporter_cls() if isinstance(reporter_cls, type) else reporter_cls
                reporter.render(result)
            except Exception as e:
                logger.error("Reporter '%s' 失败: %s", rep_name, e)

    summary = _summarize(results_list)
    summary["screener"] = screener_name
    summary["selection_count"] = len(symbol_to_entry_dates)
    return summary
