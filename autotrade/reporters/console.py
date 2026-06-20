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
        title = result.symbol
        if result.stock_name:
            title = f"{result.stock_name} ({result.symbol})"
        console.print(Panel.fit(f"[bold]回测结果: {title}", border_style="blue"))

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
            initial_capital = result.metrics.get("initial_capital", 100000)
            trades_table = Table(title=f"交易记录 ({len(result.trades)} 笔)",
                                 show_header=True, header_style="bold green")
            trades_table.add_column("日期")
            trades_table.add_column("方向")
            trades_table.add_column("价格")
            trades_table.add_column("数量")
            trades_table.add_column("持仓")
            trades_table.add_column("现金")
            trades_table.add_column("总资产")
            trades_table.add_column("原因")

            # 构建日期→信号映射，方便给每笔交易标注原因
            signal_reasons: dict[str, list[str]] = {}
            for s in result.signals:
                key = f"{s.date}_{s.action}"
                signal_reasons.setdefault(key, []).append(s.reason)

            cash = initial_capital
            position = 0
            for t in result.trades:
                if t.action == "BUY":
                    position += t.quantity
                    cash -= t.price * t.quantity + t.commission
                else:
                    position -= t.quantity
                    cash += t.price * t.quantity - t.commission - t.stamp_duty

                total_equity = cash + position * t.price

                # 匹配信号原因
                key = f"{t.date}_{t.action}"
                reasons = signal_reasons.get(key, [])
                reason_str = reasons.pop(0) if reasons else "-"

                trades_table.add_row(
                    str(t.date),
                    t.action,
                    f"{t.price:.2f}",
                    str(t.quantity),
                    str(position),
                    f"{cash:,.0f}",
                    f"{total_equity:,.0f}",
                    reason_str,
                )

            console.print(trades_table)

        # 信号摘要
        if result.signals:
            buy_count = sum(1 for s in result.signals if s.action == "BUY")
            sell_count = sum(1 for s in result.signals if s.action == "SELL")
            hold_count = sum(1 for s in result.signals if s.action == "HOLD")
            console.print(f"[dim]信号: {buy_count} BUY / {sell_count} SELL / {hold_count} HOLD[/dim]")

        console.print()
