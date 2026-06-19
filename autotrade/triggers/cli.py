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
@click.option("--datasource", default=None, help="数据源 (默认 akshare)")
@click.option("--reporters", default="console", help="报告输出方式，逗号分隔")
def analyze(symbol: str, strategy_name: str, start: Optional[str],
            end: Optional[str], datasource: Optional[str],
            reporters: str):
    """分析单只股票（含回测）。"""
    _run_and_report(
        strategy_name=strategy_name,
        symbols=symbol,
        start=start,
        end=end,
        datasource=datasource,
        reporters=reporters,
    )


@cli.command()
@click.option("--strategy", "strategy_name", required=True, help="策略名")
@click.option("--symbols", required=True, help="股票代码列表，逗号分隔")
@click.option("--start", default=None, help="开始日期 (YYYY-MM-DD)")
@click.option("--end", default=None, help="结束日期 (YYYY-MM-DD)")
@click.option("--datasource", default=None, help="数据源 (默认 akshare)")
@click.option("--reporters", default="console", help="报告输出方式，逗号分隔")
def backtest(strategy_name: str, symbols: str, start: Optional[str],
             end: Optional[str], datasource: Optional[str],
             reporters: str):
    """批量回测多只股票。"""
    _run_and_report(
        strategy_name=strategy_name,
        symbols=symbols,
        start=start,
        end=end,
        datasource=datasource,
        reporters=reporters,
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


def _run_and_report(strategy_name: str, symbols: str,
                    start: Optional[str], end: Optional[str],
                    datasource: Optional[str],
                    reporters: str = "console") -> dict:
    """统一执行入口。"""
    config = load_config()
    ds = datasource or config.get("datasource", {}).get("default", "akshare")
    reporter_list = [r.strip() for r in reporters.split(",") if r.strip()]

    # 加载策略参数
    strategy_params = get_strategy_params(strategy_name)

    summary = run_backtest(
        strategy_name=strategy_name,
        symbols=symbols,
        start=_parse_date(start),
        end=_parse_date(end),
        datasource_name=ds,
        reporter_names=tuple(reporter_list),
        strategy_params=strategy_params.get("params") if strategy_params else None,
    )

    # 输出汇总
    if summary and "avg_return_pct" in summary:
        click.echo(
            f"\n汇总: 成功 {summary['success']}/{summary['total']}, "
            f"平均收益率 {summary['avg_return_pct']:.2f}%, "
            f"正收益 {summary.get('positive_count', 0)} 只"
        )

    return summary
