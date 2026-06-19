"""终端报告输出（rich 表格）。"""

from __future__ import annotations

from autotrade.core.interfaces import Reporter
from autotrade.core.models import BacktestResult


class ConsoleReporter(Reporter):
    """在终端以 rich 表格形式输出回测结果。"""

    name = "console"

    def render(self, result: BacktestResult) -> None:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel

        console = Console()

        # 标题
        console.print(Panel.fit(f"[bold]回测结果: {result.symbol}", border_style="blue"))

        # 汇总指标
        if result.metrics:
            metrics_table = Table(title="汇总指标", show_header=True, header_style="bold cyan")
            metrics_table.add_column("指标", style="dim")
            metrics_table.add_column("值")

            for key, val in result.metrics.items():
                if isinstance(val, float):
                    metrics_table.add_row(key, f"{val:.2f}")
                else:
                    metrics_table.add_row(key, str(val))

            console.print(metrics_table)

        # 交易记录
        if result.trades:
            trades_table = Table(title=f"交易记录 ({len(result.trades)} 笔)",
                                 show_header=True, header_style="bold green")
            trades_table.add_column("日期")
            trades_table.add_column("方向")
            trades_table.add_column("价格")
            trades_table.add_column("数量")
            trades_table.add_column("佣金")
            trades_table.add_column("印花税")

            for t in result.trades:
                trades_table.add_row(
                    str(t.date),
                    t.action,
                    f"{t.price:.2f}",
                    str(t.quantity),
                    f"{t.commission:.2f}",
                    f"{t.stamp_duty:.2f}" if t.stamp_duty else "-",
                )

            console.print(trades_table)

        # 信号摘要
        if result.signals:
            buy_count = sum(1 for s in result.signals if s.action == "BUY")
            sell_count = sum(1 for s in result.signals if s.action == "SELL")
            hold_count = sum(1 for s in result.signals if s.action == "HOLD")
            console.print(f"[dim]信号: {buy_count} BUY / {sell_count} SELL / {hold_count} HOLD[/dim]")

        console.print()
