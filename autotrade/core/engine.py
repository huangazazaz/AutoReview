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
    result.close_prices = df.set_index("date")["close"] if "date" in df.columns else df["close"]

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
    """实例化策略，自动将字符串参数转为正确类型。"""
    if not params:
        return strategy_cls()
    # Coerce string values to proper types based on __init__ annotations
    import inspect
    sig = inspect.signature(strategy_cls.__init__)
    coerced = {}
    for key, val in params.items():
        if key in sig.parameters:
            ann = sig.parameters[key].annotation
            if ann is not inspect.Parameter.empty:
                try:
                    if ann is float or ann == "float":
                        coerced[key] = float(val)
                    elif ann is int or ann == "int":
                        coerced[key] = int(val)
                    elif ann is bool or ann == "bool":
                        coerced[key] = str(val).lower() in ("true", "1", "yes")
                    else:
                        coerced[key] = val
                except (ValueError, TypeError):
                    coerced[key] = val  # keep original on conversion failure
            else:
                coerced[key] = val
        else:
            coerced[key] = val
    return strategy_cls(**coerced)


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

    使用多线程并行读 parquet，大幅加速全市场加载。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    ds = LocalDataSource(data_dir=data_dir)
    market: dict[str, pd.DataFrame] = {}

    def _load_one(sym: str):
        try:
            bars = ds.get_bars(sym, start, end)
            if bars:
                return sym, _bars_to_dataframe(bars)
        except Exception:
            pass
        return sym, None

    # 多线程并行加载（I/O 密集型，线程足够）
    max_workers = min(32, len(symbols))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_load_one, s): s for s in symbols}
        done = 0
        for fut in as_completed(futures):
            sym, df = fut.result()
            done += 1
            if df is not None:
                market[sym] = df
            if done % 500 == 0:
                logger.info("加载进度: %d/%d", done, len(symbols))

    logger.info("全市场加载完成: %d/%d 只有数据", len(market), len(symbols))
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


# ---- 单日选股 ----

def run_screen(
    screener_name: str,
    strategy_name: str,
    target_date: date,
    top_n: int = 20,
    screener_params: dict[str, Any] | None = None,
    strategy_params: dict[str, Any] | None = None,
    datasource_name: str = FAILOVER_NAME,
) -> ScreenResult:
    """单日选股扫描：Screener 初筛 → Strategy 确认买点 → 因子明细。

    流程:
      1. 加载全市场 OHLCV（回溯窗口由 screener+strategy 所需最大天数决定）
      2. Screener.scan() → 候选列表
      3. 对每只候选跑 Strategy.generate_signals() → 筛选有 BUY 的
      4. Screener.explain() → 因子明细
      5. 提取关键指标 → 排序返回

    Args:
        screener_name: 选股器名称（如 "momentum_screener"）
        strategy_name: 交易策略名称（如 "ma_cross"）
        target_date: 目标日期
        top_n: 返回前 N 只
        screener_params: 选股器参数覆盖
        strategy_params: 策略参数覆盖
        datasource_name: 数据源名称

    Returns:
        ScreenResult 包含候选列表、买点信息和因子明细。
    """
    from autotrade.core.models import ScreenResult, ScreenItem

    init_registry()

    # ---- 1. 确定回溯窗口 ----
    lookback_days = 120
    start = target_date - pd.Timedelta(days=lookback_days * 2)
    end = target_date

    # ---- 2. 加载全市场数据 ----
    ds = build_datasource_from_name(datasource_name)
    all_symbols = ds.list_symbols()

    # 排除 ST
    st_exclude = _load_st_exclusion_set()
    if st_exclude:
        all_symbols = [s for s in all_symbols if s not in st_exclude]
        logger.info("排除 ST 后剩余 %d 只", len(all_symbols))

    market_data = _load_market_data(all_symbols, start, end)
    if not market_data:
        return ScreenResult(date=str(target_date), screener=screener_name,
                            strategy=strategy_name, universe_size=0)

    # ---- 3. 运行 Screener ----
    s_params = screener_params
    if s_params is None:
        s_params = _load_screener_params(screener_name)
    screener_cls = get_screener(screener_name)
    screener = screener_cls(**s_params)
    selection = screener.scan(market_data, [target_date])

    candidates = selection.get(target_date, [])
    logger.info("Screener '%s' 在 %s 选出 %d 只候选",
                screener_name, target_date, len(candidates))

    if not candidates:
        return ScreenResult(date=str(target_date), screener=screener_name,
                            strategy=strategy_name, universe_size=len(market_data),
                            candidates=0)

    # ---- 4. 运行 Strategy 确认买点 ----
    t_params = strategy_params
    if t_params is None:
        t_params = get_strategy_params(strategy_name).get("params", {}) or {}
    strategy_cls = get_strategy(strategy_name)
    strategy = strategy_cls(**t_params)

    # 计算指标列
    for indicator in strategy.required_indicators:
        for sym, _score, _tag in candidates:
            df = market_data.get(sym)
            if df is not None:
                try:
                    indicator.compute(df)
                except Exception:
                    pass

    # ---- 5. 构建结果列表 ----
    results: list[ScreenItem] = []
    name_map = _build_stock_name_map_safe()

    for sym, score, tag in candidates:
        df = market_data.get(sym)
        if df is None:
            continue

        idx = _screener_index_of(df, target_date)
        if idx is None:
            continue

        # 提取关键指标
        key_metrics: dict[str, Any] = {}
        try:
            key_metrics["close"] = round(float(df["close"].iloc[idx]), 2)
            key_metrics["volume"] = int(df["volume"].iloc[idx])
            amt_col = df.get("amount")
            if amt_col is not None:
                key_metrics["amount"] = round(float(amt_col.iloc[idx]), 0)
            else:
                key_metrics["amount"] = 0
            # 提取 MA 列（如果存在）
            for col in df.columns:
                if col.startswith("ind_ma_") or col.startswith("_ma_"):
                    val = float(df[col].iloc[idx])
                    if not pd.isna(val):
                        label = col.replace("ind_ma_", "ma_").replace("_ma_", "ma_")
                        key_metrics[label] = round(val, 2)
        except Exception:
            pass

        # 买点确认
        buy_signal = None
        try:
            signals = strategy.generate_signals(df)
            for sig in signals:
                sig_date = sig.date.date() if hasattr(sig.date, "date") else sig.date
                if sig_date == target_date and sig.action == "BUY":
                    buy_signal = {
                        "date": str(sig_date),
                        "action": sig.action,
                        "strength": sig.strength,
                        "reason": sig.reason,
                    }
                    break
        except Exception:
            pass

        # 因子明细
        factor_breakdown: dict[str, float] = {}
        try:
            factor_breakdown = screener.explain(market_data, sym, target_date)
        except Exception:
            pass

        item = ScreenItem(
            symbol=sym,
            name=name_map.get(sym, ""),
            score=round(score, 4),
            signal_tag=tag,
            factor_breakdown=factor_breakdown,
            buy_signal=buy_signal,
            key_metrics=key_metrics,
        )
        results.append(item)

    # ---- 6. 排序：有 buy_signal 的排前面，组内按 score 降序 ----
    results.sort(key=lambda x: (0 if x.buy_signal else 1, -x.score))
    with_buy = sum(1 for r in results if r.buy_signal is not None)

    return ScreenResult(
        date=str(target_date),
        screener=screener_name,
        strategy=strategy_name,
        universe_size=len(market_data),
        candidates=len(candidates),
        with_buy_signal=with_buy,
        results=results[:top_n],
    )


def _screener_index_of(df: pd.DataFrame, target: date) -> int | None:
    """查找 target date 在 DataFrame 中的整数索引。"""
    for i, val in enumerate(df.index):
        d = val.date() if hasattr(val, "date") else val
        if d == target:
            return i
    return None


def _build_stock_name_map_safe() -> dict[str, str]:
    """安全加载股票名称映射（不依赖 server 模块的缓存）。"""
    name_map: dict[str, str] = {}
    try:
        csv_path = (
            Path(__file__).resolve().parent.parent.parent
            / "data" / "a_stock_list.csv"
        )
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            if "code" in df.columns and "name" in df.columns:
                for _, row in df.iterrows():
                    name_map[str(row["code"])] = str(row["name"])
    except Exception:
        pass
    return name_map


# ---- 组合回测 ----

def _load_portfolio_backtest_config() -> dict:
    """Load portfolio backtest configuration from YAML."""
    import yaml
    cfg_path = (
        Path(__file__).resolve().parent.parent.parent
        / "config" / "backtest" / "portfolio.yaml"
    )
    if not cfg_path.exists():
        logger.warning("Portfolio backtest config not found, using defaults")
        return {}
    with open(cfg_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("portfolio_backtest", {}) or {}


def run_portfolio_backtest(
    screener_name: str = "momentum_screener",
    start: Optional[date] = None,
    end: Optional[date] = None,
    symbols: str | list[str] = "all",
    datasource_name: str = FAILOVER_NAME,
    screener_params: dict[str, Any] | None = None,
    strategy_name: str | None = None,
    strategy_params: dict[str, Any] | None = None,
    strategy_buy_window: int = 1,
    reporter_names: tuple[str, ...] = ("console",),
) -> dict[str, Any]:
    """组合级回测: 单账户多持仓 + Screener 每日选股 + 统一出场。

    流程:
      1. 加载配置 (config/backtest/portfolio.yaml)
      2. 加载全市场 OHLCV 数据
      3. 预计算 Screener 每日候选
      4. (可选) 构建策略信号缓存
      5. 运行 PortfolioBacktester 逐日模拟
      6. 输出报告

    Args:
        screener_name: 选股筛选器名称。
        start/end: 回测区间，None 则从配置读取。
        symbols: "all" 用全市场，或代码列表。
        datasource_name: 数据源名。
        screener_params: Screener 参数覆盖。
        strategy_name: 策略名 (如 "turtle")。None = 纯 Screener 模式。
        strategy_params: 策略参数覆盖。
        strategy_buy_window: 策略 BUY 信号匹配窗口 (天)。
        reporter_names: 报告输出方式。

    Returns:
        汇总字典。
    """
    import json
    from datetime import datetime as dt

    from autotrade.core.portfolio_backtester import (
        PortfolioBacktestConfig, PortfolioBacktester,
    )

    init_registry()

    # ---- 1. 加载配置 ----
    cfg = _load_portfolio_backtest_config()
    if not cfg:
        return {"error": "Portfolio backtest config not found"}

    if start is None:
        start_str = cfg.get("start_date", "2023-06-27")
        start = datetime.strptime(start_str, "%Y-%m-%d").date()  # type: ignore[assignment]
    if end is None:
        end_str = cfg.get("end_date", "2026-06-18")
        end = datetime.strptime(end_str, "%Y-%m-%d").date()  # type: ignore[assignment]

    # ---- 2. 解析 symbols + 加载全市场数据 ----
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

    market_data = _load_market_data(resolved, start, end)  # type: ignore[arg-type]
    if not market_data:
        return {"error": "No market data loaded", "results": []}

    # 交易日序列
    all_dates: set[date] = set()
    for df in market_data.values():
        for v in df.index:
            d = v.date() if hasattr(v, "date") else v
            all_dates.add(d)
    scan_dates = sorted(d for d in all_dates if start <= d <= end)  # type: ignore[operator]

    # ---- 3. 运行 Screener ----
    s_params = screener_params
    if s_params is None:
        s_params = _load_screener_params(screener_name)
    top_n = int(cfg.get("top_n_candidates", 50))
    # Map top_n to screener-specific parameter name
    if screener_name == "hot_money_screener":
        s_params["max_picks"] = top_n
    else:
        s_params["top_n_per_day"] = top_n
    screener_cls = get_screener(screener_name)
    screener = screener_cls(**s_params)
    selection = screener.scan(market_data, scan_dates)
    logger.info("Screener 扫描完成: %d 个交易日有候选", len(selection))

    # ---- 3b. AI 二次过滤 ----
    ai_cfg = cfg.get("ai_filter", {})
    if ai_cfg.get("enabled", False):
        from autotrade.ai.ai_filter import AIFilter
        from autotrade.ai.llm_cache import LLMCache

        logger.info("初始化 AI 过滤器...")
        llm_cache = LLMCache(cache_dir=ai_cfg.get("cache_dir", "data/cache/llm"))
        llm_cache.load_from_disk()

        use_local = ai_cfg.get("use_local_analyzer", True)
        analyzer = None
        if use_local:
            import os
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            if api_key:
                from autotrade.ai.local_ai_analyzer import LocalAIAnalyzer
                logger.info("使用 LocalAIAnalyzer (本地数据 + DeepSeek)")
                analyzer = LocalAIAnalyzer(api_key=api_key)
            else:
                logger.warning("DEEPSEEK_API_KEY 未设置，尝试 TradingAgents")
        if analyzer is None:
            from autotrade.ai.trading_agents_wrapper import TradingAgentsWrapper
            logger.info("使用 TradingAgentsWrapper")
            analyzer = TradingAgentsWrapper(ai_cfg)

        ai_filter = AIFilter(analyzer, llm_cache, ai_cfg)
        logger.info("AI 过滤中...")
        pre_count = sum(len(v) for v in selection.values())
        selection = ai_filter.filter(selection, market_data)
        post_count = sum(len(v) for v in selection.values())
        logger.info(
            "AI 过滤完成: %d → %d 候选 (%.1f%%)",
            pre_count, post_count,
            (post_count / pre_count * 100) if pre_count > 0 else 0,
        )
        llm_cache.save_to_disk()
    else:
        logger.info("AI 过滤器已禁用")

    # ---- 3c. 构建策略信号缓存 ----
    signal_cache = None
    if strategy_name:
        from autotrade.core.strategy_signal_cache import StrategySignalCache

        strategy_cls = get_strategy(strategy_name)
        if strategy_cls is None:
            logger.error("策略 '%s' 未注册", strategy_name)
            return {"error": f"Strategy '{strategy_name}' not found"}

        sp = strategy_params
        if sp is None:
            sp = get_strategy_params(strategy_name).get("params", {}) or {}
        strategy = _instantiate_strategy(strategy_cls, sp)

        logger.info("构建策略信号缓存 (策略=%s, 股票数=%d)...",
                    strategy_name, len(market_data))
        try:
            signal_cache = StrategySignalCache(strategy, market_data)
            logger.info("策略信号缓存构建完成: %d 只股票有信号", len(signal_cache))
        except Exception as e:
            logger.error("构建策略信号缓存失败: %s", e)
            return {"error": f"Strategy signal cache build failed: {e}"}

    # ---- 4. 构建回测配置 ----
    exit_rules = cfg.get("exit_rules", {})
    market_regime_cfg = cfg.get("market_regime", {})

    bt_config = PortfolioBacktestConfig(
        start_date=start,  # type: ignore[arg-type]
        end_date=end,  # type: ignore[arg-type]
        initial_capital=float(cfg.get("initial_capital", 1_000_000)),
        cash_buffer=float(cfg.get("cash_buffer", 0.05)),
        top_n_candidates=top_n,
        fill_price=str(cfg.get("fill_price", "next_open")),
        commission_rate=float(cfg.get("commission_rate", 0.0003)),
        stamp_duty_rate=float(cfg.get("stamp_duty_rate", 0.001)),
        slippage=float(cfg.get("slippage", 0.001)),
        min_commission=float(cfg.get("min_commission", 5.0)),
        lot_size=int(cfg.get("lot_size", 100)),
        allow_t_plus_1=bool(cfg.get("allow_t_plus_1", True)),
        exit_rules=exit_rules,
        market_regime=market_regime_cfg,
        strategy_name=strategy_name,
        strategy_params=strategy_params,
        strategy_buy_window=strategy_buy_window,
    )

    # ---- 5. 运行组合回测 ----
    backtester = PortfolioBacktester(bt_config)
    result = backtester.run(market_data, selection, signal_cache=signal_cache)

    logger.info(
        "组合回测完成: %d 笔交易, 收益率 %.2f%%, 最大回撤 %.2f%%, 夏普 %.4f",
        len(result.trades),
        result.metrics.get("total_return_pct", 0.0),
        result.metrics.get("max_drawdown_pct", 0.0),
        result.metrics.get("sharpe_ratio", 0.0),
    )

    # ---- 6. 输出报告 ----
    for rep_name in reporter_names:
        try:
            reporter_cls = get_reporter(rep_name)
            reporter = reporter_cls() if isinstance(reporter_cls, type) else reporter_cls
            if hasattr(reporter, "render_portfolio"):
                reporter.render_portfolio(result, bt_config)
            else:
                logger.info("Reporter '%s' does not support portfolio results", rep_name)
        except Exception as e:
            logger.error("Reporter '%s' failed: %s", rep_name, e)

    # ---- 7. 保存结果 ----
    output_dir = Path(cfg.get("output_dir", "data/results"))
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
    prefix = cfg.get("output_prefix", "portfolio_backtest")
    run_dir = output_dir / f"{prefix}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Save equity curve
    if result.equity_curve is not None:
        result.equity_curve.to_csv(run_dir / "equity_curve.csv", header=["equity"])

    # Save trades
    if result.trades:
        trades_df = pd.DataFrame([
            {
                "symbol": t.symbol,
                "buy_date": t.buy_date,
                "sell_date": t.sell_date,
                "buy_price": t.buy_price,
                "sell_price": t.sell_price,
                "quantity": t.quantity,
                "pnl": t.pnl,
                "pnl_pct": t.pnl_pct,
                "trigger": t.trigger,
            }
            for t in result.trades
        ])
        trades_df.to_csv(run_dir / "trades.csv", index=False)

    # Save summary
    with open(run_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(result.metrics, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {run_dir}")
    print(f"  权益曲线: {run_dir / 'equity_curve.csv'}")
    print(f"  交易明细: {run_dir / 'trades.csv'}")
    print(f"  汇总指标: {run_dir / 'summary.json'}")

    return {
        "metrics": result.metrics,
        "trade_count": len(result.trades),
        "output_dir": str(run_dir),
        "equity_curve": result.equity_curve,
        "trades": result.trades,
    }
