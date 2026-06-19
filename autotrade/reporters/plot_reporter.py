"""图表报告输出（matplotlib）。"""

from __future__ import annotations

import os

from autotrade.core.interfaces import Reporter
from autotrade.core.models import BacktestResult


class PlotReporter(Reporter):
    """生成回测图表（净值曲线、买卖点标注）。"""

    name = "plot"

    def __init__(self, output_dir: str = "data/results", show: bool = False):
        self.output_dir = output_dir
        self.show = show

    def render(self, result: BacktestResult) -> str:
        """生成图表并保存到文件，返回文件路径。"""
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        os.makedirs(self.output_dir, exist_ok=True)

        fig, axes = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [3, 1]})

        # 净值曲线 + 买卖点
        ax1 = axes[0]
        if result.equity_curve is not None:
            ax1.plot(result.equity_curve.index, result.equity_curve.values,
                     label="Equity", color="blue", linewidth=1.5)
            ax1.fill_between(result.equity_curve.index, result.equity_curve.values,
                             alpha=0.1, color="blue")

        # 标注买卖点
        buy_dates = [t.date for t in result.trades if t.action == "BUY"]
        sell_dates = [t.date for t in result.trades if t.action == "SELL"]

        if buy_dates and result.equity_curve is not None:
            buy_vals = [result.equity_curve.get(d, None) for d in buy_dates]
            buy_vals = [v for v in buy_vals if v is not None]
            if buy_vals:
                ax1.scatter(buy_dates[:len(buy_vals)], buy_vals,
                           color="red", marker="^", s=80, label="BUY", zorder=5)

        if sell_dates and result.equity_curve is not None:
            sell_vals = [result.equity_curve.get(d, None) for d in sell_dates]
            sell_vals = [v for v in sell_vals if v is not None]
            if sell_vals:
                ax1.scatter(sell_dates[:len(sell_vals)], sell_vals,
                           color="green", marker="v", s=80, label="SELL", zorder=5)

        ax1.set_title(f"{result.symbol} 回测净值曲线")
        ax1.set_ylabel("净值")
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        ax1.xaxis.set_major_locator(mdates.WeekdayLocator())

        # 回撤曲线
        ax2 = axes[1]
        if result.equity_curve is not None:
            peak = result.equity_curve.cummax()
            drawdown = (peak - result.equity_curve) / peak * 100
            ax2.fill_between(drawdown.index, drawdown.values, 0,
                             color="red", alpha=0.3, label="Drawdown")
            ax2.plot(drawdown.index, drawdown.values, color="red", linewidth=1)
            ax2.set_ylabel("回撤 (%)")
            ax2.set_xlabel("日期")
            ax2.grid(True, alpha=0.3)
            ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
            ax2.xaxis.set_major_locator(mdates.WeekdayLocator())

        plt.tight_layout()
        filepath = os.path.join(self.output_dir, f"{result.symbol}_backtest.png")
        plt.savefig(filepath, dpi=150, bbox_inches="tight")

        if self.show:
            plt.show()
        else:
            plt.close()

        return filepath
