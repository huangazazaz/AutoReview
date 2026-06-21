"""游资策略全样本回测验证脚本。

用法: python scripts/backtest_hot_money.py
从 config/groups/随机组.yaml 读取股票池（450 只），跑全样本回测，
输出胜率/收益分布，验收 60% 胜率 + 20% 收益目标。
"""
import json
from datetime import date
from pathlib import Path

import yaml

from autotrade.core.engine import run_screener_backtest


def load_group_symbols(yaml_path: str) -> tuple[list[str], dict[str, str]]:
    """加载股票池，返回 (codes, {code: name})。"""
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    symbols_raw = data.get("symbols") or data.get("stocks") or {}
    if isinstance(symbols_raw, list):
        codes = [str(s) for s in symbols_raw]
        names = {}
    elif isinstance(symbols_raw, dict):
        codes = []
        names = {}
        for k, v in symbols_raw.items():
            code = str(k)
            codes.append(code)
            names[code] = str(v) if v else ""
    else:
        codes = []
        names = {}
    return codes, names


def main():
    # 全市场模式：不限制股票池
    import sys
    use_all = "--all" in sys.argv
    group = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else None

    if use_all or (not group):
        symbols = "all"
        stock_names = None
        label = "全市场(4700+)"
    else:
        symbols, stock_names = load_group_symbols(group)
        label = f"{group} ({len(symbols)} 只)"

    print(f"回测模式: {label}")

    summary = run_screener_backtest(
        screener_name="hot_money_screener",
        strategy_name="hot_money",
        start=date(2025, 1, 1),
        end=date(2026, 6, 18),
        symbols=symbols,
        reporter_names=(),
        stock_names=stock_names,
    )

    if "error" in summary:
        print(f"错误: {summary['error']}")
        return

    # 统计
    results = [r for r in summary["results"] if "error" not in str(r.get("metrics", {}))]
    win_rates = [r.get("win_rate", 0) for r in results]
    returns = [r.get("return_pct", 0) for r in results]
    avg_win = sum(win_rates) / len(win_rates) if win_rates else 0
    avg_ret = sum(returns) / len(returns) if returns else 0

    print(f"\n===== 游资策略回测结果 =====")
    print(f"回测模式: {label}")
    print(f"Screener 选中并回测: {summary.get('selection_count', 0)} 只")
    print(f"有效结果: {len(results)} 只")
    print(f"平均胜率: {avg_win:.1f}%  (目标 >=60%)")
    print(f"平均收益: {avg_ret:.2f}%  (目标 >=20%)")
    print(f"胜率>=60%的票: {sum(1 for w in win_rates if w >= 60)}")
    print(f"收益>=20%的票: {sum(1 for r in returns if r >= 20)}")
    print(f"两者都达标: {sum(1 for w, r in zip(win_rates, returns) if w >= 60 and r >= 20)}")

    # 保存结果
    out_path = Path("data/results/hot_money_result.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
