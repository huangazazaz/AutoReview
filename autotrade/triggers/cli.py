"""CLI 入口（click）。

子命令:
- analyze: 单股快速验证
- backtest: 指定股票池批量
- scan: 全市场扫描找标的
- list: 自省（看有哪些插件）
- show: 复看历史结果

Usage:
    autotrade analyze --symbol 000001 --strategy ma_cross --start 2024-01-01
    autotrade list strategies
    autotrade scan --strategy ma_cross --top 10
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import click

from autotrade.core.config import load_config, get_strategy_params
from autotrade.core.engine import run_backtest
from autotrade.registry import (
    init_registry, list_datasources, list_indicators,
    list_strategies, list_reporters,
)

logger = logging.getLogger(__name__)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="显示调试日志")
def cli(verbose: bool):
    """AutoTrade: A股自动化交易信号生成与回测系统。"""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    init_registry()


@cli.command()
@click.option("--symbol", required=True, help="股票代码，如 000001")
@click.option("--strategy", "strategy_name", required=True, help="策略名")
@click.option("--start", default=None, help="开始日期 (YYYY-MM-DD)")
@click.option("--end", default=None, help="结束日期 (YYYY-MM-DD)")
@click.option("--period", "-p", default=None, help="快捷周期: 1y/6m/20d/60t (默认 2025-01-01 ~ 2026-06-18)")
@click.option("--datasource", default=None, help="数据源 (默认 akshare)")
@click.option("--reporters", default="console", help="报告输出方式，逗号分隔")
def analyze(symbol: str, strategy_name: str, start: Optional[str],
            end: Optional[str], period: Optional[str],
            datasource: Optional[str], reporters: str):
    """分析单只股票（含回测）。"""
    _run_and_report(
        strategy_name=strategy_name,
        symbols=symbol,
        start=start,
        end=end,
        period=period,
        datasource=datasource,
        reporters=reporters,
    )


@cli.command()
@click.option("--strategy", "strategy_name", required=True, help="策略名")
@click.option("--symbols", default=None, help="股票代码列表，逗号分隔")
@click.option("--group", default=None, help="股票分组名 (config/groups/<name>.yaml)")
@click.option("--start", default=None, help="开始日期 (YYYY-MM-DD)")
@click.option("--end", default=None, help="结束日期 (YYYY-MM-DD)")
@click.option("--period", "-p", default=None, help="快捷周期: 1y/6m/20d/60t (默认 2025-01-01 ~ 2026-06-18)")
@click.option("--datasource", default=None, help="数据源 (默认 akshare)")
@click.option("--reporters", default="console", help="报告输出方式，逗号分隔")
def backtest(strategy_name: str, symbols: Optional[str], group: Optional[str],
             start: Optional[str], end: Optional[str], period: Optional[str],
             datasource: Optional[str], reporters: str):
    """批量回测多只股票。--symbols 或 --group 至少指定一个。"""
    resolved = _resolve_input(symbols, group)
    if not resolved:
        click.echo("请用 --symbols 或 --group 指定股票", err=True)
        return
    names = _load_group_names(group) if group else None
    _run_and_report(
        strategy_name=strategy_name,
        symbols=resolved,
        start=start,
        end=end,
        period=period,
        datasource=datasource,
        reporters=reporters,
        stock_names=names,
    )


@cli.command()
@click.option("--strategy", "strategy_name", required=True, help="策略名")
@click.option("--universe", default="all", help="股票池 (默认 all 全市场)")
@click.option("--end", default=None, help="结束日期 (YYYY-MM-DD)")
@click.option("--datasource", default=None, help="数据源 (默认 akshare)")
@click.option("--top", default=20, type=int, help="只显示前 N 名")
@click.option("--min-trades", default=1, type=int, help="最少交易次数")
def scan(strategy_name: str, universe: str, end: Optional[str],
         datasource: Optional[str], top: int, min_trades: int):
    """全市场扫描，按收益率排序。"""
    summary = _run_and_report(
        strategy_name=strategy_name,
        symbols=universe,
        start=None,
        end=end,
        datasource=datasource,
        reporters="console",
    )

    if summary and "results" in summary:
        sorted_results = sorted(
            summary["results"],
            key=lambda r: float(r.get("return_pct", 0)),
            reverse=True,
        )
        filtered = [r for r in sorted_results
                    if int(r.get("trades", 0)) >= min_trades][:top]

        click.echo(f"\n=== Top {top} 结果 ===")
        click.echo(f"{'排名':<6} {'代码':<10} {'收益率%':<12} {'交易次数':<10} {'夏普':<10}")
        click.echo("-" * 50)
        for idx, r in enumerate(filtered, 1):
            click.echo(
                f"{idx:<6} {r['symbol']:<10} "
                f"{float(r['return_pct']):<12.2f} "
                f"{int(r['trades']):<10} "
                f"{float(r.get('sharpe', 0)):<10.4f}"
            )


@cli.command()
@click.argument("component", type=click.Choice(["strategies", "indicators",
                                                  "datasources", "reporters"]))
def list_plugins(component: str):
    """列出可用插件。"""
    registry_map = {
        "strategies": ("策略", list_strategies()),
        "indicators": ("指标", list_indicators()),
        "datasources": ("数据源", list_datasources()),
        "reporters": ("报告", list_reporters()),
    }

    label, items = registry_map[component]
    click.echo(f"\n可用 {label} ({len(items)}):")
    if items:
        for item in items:
            click.echo(f"  • {item}")
    else:
        click.echo("  (空)")


@cli.command(name="list-groups")
def list_groups():
    """列出股票分组。"""
    groups_dir = Path(__file__).resolve().parent.parent.parent / "config" / "groups"
    if not groups_dir.exists():
        click.echo("(无分组)")
        return
    files = sorted(groups_dir.glob("*.yaml"))
    if not files:
        click.echo("(无分组)")
        return
    click.echo(f"\n可用分组 ({len(files)}):")
    for f in files:
        cfg = _load_yaml(f)
        name = cfg.get("name", f.stem)
        symbols = _extract_symbols(cfg)
        click.echo(f"  • {f.stem}  ({name}): {', '.join(f'{c}({n})' for c, n in symbols[:5])}{'...' if len(symbols) > 5 else ''}")


@cli.command()
@click.option("--result", required=True, help="结果文件路径 (.json)")
def show(result: str):
    """复看历史结果。"""
    path = Path(result)
    if not path.exists():
        click.echo(f"文件不存在: {result}", err=True)
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    click.echo(f"\n回测结果: {data.get('symbol', 'unknown')}")
    for key, val in data.get("metrics", {}).items():
        click.echo(f"  {key}: {val}")


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """解析日期字符串。"""
    if not date_str:
        return None
    return date.fromisoformat(date_str)


def _parse_period(period: Optional[str]) -> tuple[Optional[date], Optional[date]]:
    """解析周期快捷参数，返回 (start, end)。

    支持: 1y(年) 6m(月) 20d(日历日) 60t(交易日, 近似日历日×1.4)
    无参数时返回 (None, None)，由调用方决定默认值。
    """
    if not period:
        return None, None

    import re
    m = re.match(r"^(\d+)\s*([ymdt])$", period.lower().strip())
    if not m:
        return None, None

    num = int(m.group(1))
    unit = m.group(2)
    today = date.today()

    if unit == "y":
        start = date(today.year - num, today.month, today.day)
    elif unit == "m":
        total_months = today.month - 1 - num
        y = today.year + total_months // 12
        m = total_months % 12 + 1
        start = date(y, m, min(today.day, 28))
    else:
        # d(日历日) / t(交易日, 近似日历日×1.4)
        from datetime import timedelta
        days = int(num * 1.4) if unit == "t" else num
        start = today - timedelta(days=days)

    return start, today


def _resolve_input(symbols: Optional[str], group: Optional[str]) -> Optional[str]:
    """解析 --symbols 或 --group，返回逗号分隔的代码字符串。"""
    if symbols:
        return symbols
    if group:
        return _load_group_symbols(group)
    return None


def _load_group_symbols(name: str) -> Optional[str]:
    """从 config/groups/<name>.yaml 加载股票列表（返回逗号分隔代码）。"""
    groups_dir = Path(__file__).resolve().parent.parent.parent / "config" / "groups"
    path = groups_dir / f"{name}.yaml"
    if not path.exists():
        click.echo(f"分组不存在: {name} (文件: {path})", err=True)
        return None
    cfg = _load_yaml(path)
    syms = _extract_symbols(cfg)
    if not syms:
        click.echo(f"分组 {name} 没有配置股票", err=True)
        return None
    return ",".join(c for c, _ in syms)


def _extract_symbols(cfg: dict) -> list[tuple[str, str]]:
    """从分组配置提取 [(code, name), ...]。

    支持两种格式:
      symbols: ["600522", "000001"]              → name 为空
      symbols: {"600522": "中天科技", ...}       → code→name 映射
    """
    raw = cfg.get("symbols", [])
    if isinstance(raw, dict):
        return [(str(k), str(v)) for k, v in raw.items()]
    if isinstance(raw, list):
        return [(str(s), "") for s in raw]
    return []


def _load_group_names(name: str) -> dict[str, str]:
    """加载分组的代码→名称映射。"""
    groups_dir = Path(__file__).resolve().parent.parent.parent / "config" / "groups"
    path = groups_dir / f"{name}.yaml"
    if not path.exists():
        return {}
    cfg = _load_yaml(path)
    syms = _extract_symbols(cfg)
    return {code: sname for code, sname in syms if sname}


def _load_yaml(path: Path) -> dict:
    """加载 YAML 文件。"""
    import yaml
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _run_and_report(strategy_name: str, symbols: str,
                    start: Optional[str], end: Optional[str],
                    period: Optional[str] = None,
                    datasource: Optional[str] = None,
                    reporters: str = "console",
                    stock_names: dict[str, str] | None = None) -> dict:
    """统一执行入口。"""
    config = load_config()
    ds = datasource or config.get("datasource", {}).get("default", "failover")
    reporter_list = [r.strip() for r in reporters.split(",") if r.strip()]

    # 日期：显式 start/end 优先 → period → 默认 2025-01-01 ~ 2026-06-18
    p_start = _parse_date(start)
    p_end = _parse_date(end)
    if p_start is None and p_end is None:
        if period or not (start or end):
            p_start, p_end = _parse_period(period)
            if p_start is None and p_end is None:
                p_start = date(2025, 1, 1)
                p_end = date(2026, 6, 18)

    # 加载策略参数
    strategy_params = get_strategy_params(strategy_name)

    summary = run_backtest(
        strategy_name=strategy_name,
        symbols=symbols,
        start=p_start,
        end=p_end,
        datasource_name=ds,
        reporter_names=tuple(reporter_list),
        strategy_params=strategy_params.get("params") if strategy_params else None,
        stock_names=stock_names,
    )

    # 输出汇总
    if summary and "avg_return_pct" in summary:
        click.echo(
            f"\n汇总: 成功 {summary['success']}/{summary['total']}, "
            f"平均收益率 {summary['avg_return_pct']:.2f}%, "
            f"正收益 {summary.get('positive_count', 0)} 只"
        )

    return summary
