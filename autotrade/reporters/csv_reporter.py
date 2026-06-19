"""CSV 报告输出。"""

from __future__ import annotations

import csv
import os

from autotrade.core.interfaces import Reporter
from autotrade.core.models import BacktestResult


class CSVReporter(Reporter):
    """将回测结果输出为 CSV 文件。"""

    name = "csv"

    def __init__(self, output_dir: str = "data/results"):
        self.output_dir = output_dir

    def render(self, result: BacktestResult) -> str:
        """输出 CSV 并返回文件路径。"""
        os.makedirs(self.output_dir, exist_ok=True)

        # 指标文件
        metrics_path = os.path.join(
            self.output_dir,
            f"{result.symbol}_metrics.csv"
        )
        with open(metrics_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["metric", "value"])
            for key, val in (result.metrics or {}).items():
                writer.writerow([key, val])

        # 交易记录文件
        trades_path = os.path.join(
            self.output_dir,
            f"{result.symbol}_trades.csv"
        )
        with open(trades_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "action", "price", "quantity",
                             "commission", "stamp_duty"])
            for t in result.trades:
                writer.writerow([
                    t.date, t.action, t.price, t.quantity,
                    t.commission, t.stamp_duty,
                ])

        # 净值曲线
        if result.equity_curve is not None:
            equity_path = os.path.join(
                self.output_dir,
                f"{result.symbol}_equity.csv"
            )
            result.equity_curve.to_csv(equity_path, header=["equity"])

        return metrics_path
