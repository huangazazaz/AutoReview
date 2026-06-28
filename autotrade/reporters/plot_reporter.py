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

    def render_portfolio(self, result, config=None):
        """Render portfolio backtest results with equity curve chart."""
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime
        from pathlib import Path

        if result.equity_curve is None or result.equity_curve.empty:
            print("No equity curve to plot.")
            return

        fig, axes = plt.subplots(3, 1, figsize=(14, 12),
                                 gridspec_kw={"height_ratios": [3, 1, 1]})

        # 1. Equity curve
        ax1 = axes[0]
        eq = result.equity_curve
        ax1.plot(eq.index, eq.values, color="#1f77b4", linewidth=1.2, label="Equity")
        ax1.axhline(y=eq.iloc[0], color="gray", linestyle="--", alpha=0.5, label="Initial")
        ax1.fill_between(eq.index, eq.iloc[0], eq.values,
                         where=eq.values >= eq.iloc[0],
                         color="green", alpha=0.1)
        ax1.fill_between(eq.index, eq.values, eq.iloc[0],
                         where=eq.values < eq.iloc[0],
                         color="red", alpha=0.1)
        ax1.set_ylabel("Account Equity (¥)")
        ax1.set_title("Portfolio Backtest — Equity Curve", fontsize=13, fontweight="bold")
        ax1.legend(loc="upper left")
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")

        # 2. Drawdown
        ax2 = axes[1]
        peak = eq.cummax()
        drawdown = (eq - peak) / peak * 100
        ax2.fill_between(eq.index, 0, drawdown.values, color="red", alpha=0.3)
        ax2.plot(eq.index, drawdown.values, color="red", linewidth=0.8)
        ax2.set_ylabel("Drawdown (%)")
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha="right")

        # 3. Daily returns
        ax3 = axes[2]
        daily_ret = eq.pct_change() * 100
        colors = ["green" if v >= 0 else "red" for v in daily_ret.values]
        ax3.bar(eq.index[1:], daily_ret.values[1:], color=colors, width=1, alpha=0.6)
        ax3.set_ylabel("Daily Return (%)")
        ax3.set_xlabel("Date")
        ax3.grid(True, alpha=0.3)
        ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha="right")

        plt.tight_layout()

        # Save
        os.makedirs(self.output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(self.output_dir, f"portfolio_equity_{timestamp}.png")
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Chart saved to: {save_path}")

        if self.show:
            plt.show()
        else:
            plt.close()

        # Print metrics summary
        metrics = result.metrics
        if metrics:
            print("\n  ── Performance Metrics ──")
            print(f"  Initial Capital:  ¥{metrics.get('initial_capital', 0):,.0f}")
            print(f"  Final Equity:     ¥{metrics.get('final_equity', 0):,.0f}")
            print(f"  Total Return:     {metrics.get('total_return_pct', 0):.2f}%")
            print(f"  Win Rate:         {metrics.get('win_rate', 0):.2f}%")
            print(f"  Max Drawdown:     {metrics.get('max_drawdown_pct', 0):.2f}%")
            print(f"  Sharpe Ratio:     {metrics.get('sharpe_ratio', 0):.4f}")
            print(f"  Total Trades:     {metrics.get('total_trades', 0)}")

            # Trigger breakdown
            if hasattr(result, 'trades') and result.trades:
                from collections import Counter
                trigger_counts = Counter(t.trigger for t in result.trades if t.trigger)
                if trigger_counts:
                    print("\n  ── Exit Triggers ──")
                    for trigger, count in trigger_counts.most_common():
                        print(f"  {trigger}:  {count}")
