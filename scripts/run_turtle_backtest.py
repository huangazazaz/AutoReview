#!/usr/bin/env python
"""海龟策略批量回测脚本。

用法:
    python scripts/run_turtle_backtest.py                     # 全市场回测
    python scripts/run_turtle_backtest.py --symbols 000001,600519  # 指定股票
    python scripts/run_turtle_backtest.py --long-only          # 仅做多
    python scripts/run_turtle_backtest.py --group config/groups/蓝筹.yaml  # 指定池子
"""
import json
import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autotrade.registry import init_registry
from autotrade.core.engine import analyze_stock, _make_backtest_config
from autotrade.core.models import BacktestConfig


def load_group(yaml_path: str) -> list[str]:
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    raw = data.get("symbols") or data.get("stocks") or {}
    if isinstance(raw, list):
        return [str(s) for s in raw]
    return [str(k) for k in raw]


def main():
    init_registry()

    import argparse
    parser = argparse.ArgumentParser(description="Turtle Strategy Backtest")
    parser.add_argument("--symbols", type=str, default="",
                        help="逗号分隔的股票代码，默认用 momentum_screener 跑全市场")
    parser.add_argument("--group", type=str, default="",
                        help="股票池 YAML 路径")
    parser.add_argument("--start", type=str, default="2024-01-01")
    parser.add_argument("--end", type=str, default="2025-12-31")
    parser.add_argument("--long-only", action="store_true",
                        help="仅做多，关闭做空")
    parser.add_argument("--capital", type=float, default=100_000)
    parser.add_argument("--top", type=int, default=20,
                        help="最多回测前 N 只（当 symbols=all 时）")
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    # 确定股票池
    if args.group:
        symbols = load_group(args.group)
    elif args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
    else:
        # 全市场：用 momentum_screener 选候选
        from autotrade.core.engine import run_screener_backtest
        print(f"使用 momentum_screener 筛选候选股...")
        summary = run_screener_backtest(
            screener_name="momentum_screener",
            strategy_name="turtle",
            start=start, end=end,
            symbols="all",
            reporter_names=(),
        )
        if "error" in summary:
            print(f"错误: {summary['error']}")
            return
        # 取回测结果中的股票列表
        symbols = [r.get("symbol", "") for r in summary.get("results", []) if "symbol" in r]
        symbols = [s for s in symbols if s][:args.top]
        if not symbols:
            print("没有候选股，退出")
            return
        print(f"选中 {len(symbols)} 只候选股")

    # 回测配置
    cfg = BacktestConfig(
        initial_capital=args.capital,
        fill_price="next_open",
        allow_short=not args.long_only,
        short_margin_ratio=1.0,
        position_sizing="strength",
    )

    print(f"\n{'='*60}")
    print(f"  海龟策略回测  |  {len(symbols)} 只  |  {start} ~ {end}")
    print(f"  做空: {'关' if args.long_only else '开'}  |  本金: {args.capital:,.0f}")
    print(f"{'='*60}\n")

    results = []
    for i, sym in enumerate(symbols):
        try:
            result = analyze_stock(
                symbol=sym,
                strategy_name="turtle",
                start=start, end=end,
                backtest_config=cfg,
            )
            results.append(result)
            m = result.metrics
            print(f"[{i+1:3d}/{len(symbols)}] {sym:8s}  "
                  f"收益={m.get('total_return_pct', 0):6.2f}%  "
                  f"胜率={m.get('win_rate', 0):5.1f}%  "
                  f"回撤={m.get('max_drawdown_pct', 0):6.2f}%  "
                  f"夏普={m.get('sharpe_ratio', 0):6.4f}  "
                  f"交易={m.get('total_trades', 0)}")
        except Exception as e:
            print(f"[{i+1:3d}/{len(symbols)}] {sym:8s}  错误: {e}")

    # 汇总
    valid = [r for r in results if "error" not in r.metrics]
    if not valid:
        print("\n没有有效结果")
        return

    returns_pct = [r.metrics.get("total_return_pct", 0) for r in valid]
    win_rates = [r.metrics.get("win_rate", 0) for r in valid]
    sharpes = [r.metrics.get("sharpe_ratio", 0) for r in valid]

    print(f"\n{'='*60}")
    print(f"  汇总统计 ({len(valid)} 只)")
    print(f"{'='*60}")
    print(f"  平均收益率:  {sum(returns_pct)/len(returns_pct):.2f}%")
    print(f"  收益率中位数: {sorted(returns_pct)[len(returns_pct)//2]:.2f}%")
    print(f"  平均胜率:    {sum(win_rates)/len(win_rates):.1f}%")
    print(f"  平均夏普:    {sum(sharpes)/len(sharpes):.4f}")
    print(f"  正收益票:    {sum(1 for r in returns_pct if r > 0)}/{len(valid)}")
    print(f"  收益>10%:   {sum(1 for r in returns_pct if r > 10)}/{len(valid)}")
    print(f"  收益<-10%:  {sum(1 for r in returns_pct if r < -10)}/{len(valid)}")

    # 保存
    out_dir = Path("data/results/turtle_backtest")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"result_{start}_{end}.json"
    summary = {
        "config": {
            "start": str(start), "end": str(end),
            "capital": args.capital,
            "allow_short": not args.long_only,
            "symbols": symbols,
        },
        "results": [
            {
                "symbol": r.symbol,
                "stock_name": r.stock_name,
                "metrics": r.metrics,
                "trades": len(r.trades),
            }
            for r in results
        ],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {out_path}")


if __name__ == "__main__":
    main()
