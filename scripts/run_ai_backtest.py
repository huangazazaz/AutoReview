#!/usr/bin/env python
"""Progressive AI-enhanced backtest — runs in batches, caches results.

Each run processes candidates not yet in cache. Run multiple times
until all candidates are cached, then the full backtest is instant.
"""
import sys, time, json, os
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autotrade.registry import init_registry, get_screener
from autotrade.core.engine import _load_market_data, _resolve_symbols, _load_st_exclusion_set, _load_screener_params
from autotrade.core.portfolio_backtester import PortfolioBacktestConfig, PortfolioBacktester
from autotrade.ai.local_ai_analyzer import LocalAIAnalyzer
from autotrade.ai.ai_filter import AIFilter
from autotrade.ai.llm_cache import LLMCache


def main():
    init_registry()

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("Error: DEEPSEEK_API_KEY not set")
        return 1

    # Load symbols and data (once, reused)
    symbols = [s for s in _resolve_symbols("all", "failover")
               if s not in _load_st_exclusion_set()]
    print(f"Universe: {len(symbols)} stocks")

    start, end = date(2025, 1, 2), date(2025, 12, 31)
    print(f"Period: {start} → {end}")

    print("Loading market data...")
    t0 = time.time()
    market = _load_market_data(symbols, start, end)
    print(f"  {len(market)} stocks in {time.time()-t0:.0f}s")

    # Run screener
    print("Running screener...")
    t0 = time.time()
    params = _load_screener_params("momentum_screener")
    params["top_n_per_day"] = 15
    params["score_threshold"] = 0.70
    screener = get_screener("momentum_screener")(**params)
    all_dates = set()
    for df in market.values():
        for v in df.index:
            all_dates.add(v.date() if hasattr(v, "date") else v)
    dates = sorted(d for d in all_dates if start <= d <= end)
    selection = screener.scan(market, dates)
    total_picks = sum(len(v) for v in selection.values())
    print(f"  {total_picks} picks across {len(dates)} days in {time.time()-t0:.0f}s")

    # AI filter setup
    analyzer = LocalAIAnalyzer(api_key=api_key)
    cache = LLMCache(cache_dir="data/cache/llm")
    cache.load_from_disk()

    # Count uncached
    uncached = 0
    for d, candidates in selection.items():
        for symbol, _, _ in candidates[:5]:
            if cache.get(symbol, d.isoformat()) is None:
                uncached += 1

    max_to_run = 30  # Process at most 30 new candidates per run (takes ~90s)
    print(f"\nCache status: {uncached} uncached candidates remaining")
    print(f"This run will process up to {max_to_run} new candidates (~{max_to_run*3}s)")

    if uncached == 0:
        print("All candidates cached!")
    else:
        ai = AIFilter(analyzer, cache, {
            "max_candidates_per_day": 5,
            "enabled": True,
        })
        # Monkey-patch to limit total calls
        original_get_decision = ai._get_decision
        call_count = [0]

        def limited_get_decision(symbol, d, market_data):
            date_str = d.isoformat()
            cached = cache.get(symbol, date_str)
            if cached is not None:
                return cached
            if call_count[0] >= max_to_run:
                return "Hold"  # Skip uncached if limit reached
            call_count[0] += 1
            return original_get_decision(symbol, d, market_data)

        ai._get_decision = limited_get_decision

        print("Running AI filter (limited batch)...")
        t0 = time.time()
        ai.filter(selection, market)
        cache.save_to_disk()
        print(f"  Processed {call_count[0]} new candidates in {time.time()-t0:.0f}s")

        # Re-check uncached
        uncached2 = 0
        for d, candidates in selection.items():
            for symbol, _, _ in candidates[:5]:
                if cache.get(symbol, d.isoformat()) is None:
                    uncached2 += 1
        print(f"  Remaining: {uncached2} uncached")

        if uncached2 > 0:
            print("\n⚠ Run again to process more candidates.")
            print(f"  Total ~{uncached2} calls remaining (~{uncached2*3}s)")
            return 0

    # All cached — run full backtest
    print("\nAll candidates cached! Running full backtest...")
    cache.load_from_disk()  # reload
    ai = AIFilter(analyzer, cache, {
        "max_candidates_per_day": 5,
        "enabled": True,
    })
    filtered = ai.filter(selection, market)
    in_count = sum(len(v) for v in selection.values())
    out_count = sum(len(v) for v in filtered.values())
    print(f"  AI filter: {in_count} → {out_count} picks ({out_count/in_count*100:.1f}%)")

    t0 = time.time()
    bt = PortfolioBacktester(PortfolioBacktestConfig(
        start_date=start, end_date=end, initial_capital=1_000_000, cash_buffer=0.05,
        top_n_candidates=15, commission_rate=0.0003, stamp_duty_rate=0.001,
        slippage=0.001, min_commission=5.0, lot_size=100, allow_t_plus_1=True,
        exit_rules={
            "trailing_stop": {"enabled": True, "drawdown_pct": 0.10},
            "hard_stop": {"enabled": True, "loss_pct": 0.08},
            "time_stop": {"enabled": False},
            "signal_decay": {"enabled": True, "rank_threshold": 15},
        },
        market_regime={"score_threshold": 0.3, "bullish_threshold": 0.6, "neutral_threshold": 0.4},
    ))
    result = bt.run(market, filtered)
    print(f"  Backtester: {time.time()-t0:.0f}s, {len(result.trades)} trades")

    # Save
    out = Path("data/results") / f"portfolio_ai_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)
    result.equity_curve.to_csv(out / "equity_curve.csv", header=["equity"])
    import pandas as pd
    pd.DataFrame([{
        "symbol": t.symbol, "buy_date": t.buy_date, "sell_date": t.sell_date,
        "buy_price": t.buy_price, "sell_price": t.sell_price,
        "quantity": t.quantity, "pnl": t.pnl, "pnl_pct": t.pnl_pct,
    } for t in result.trades]).to_csv(out / "trades.csv", index=False)
    with open(out / "summary.json", "w") as f:
        json.dump(result.metrics, f, ensure_ascii=False, indent=2)

    m = result.metrics
    print(f"\n{'='*60}")
    print(f"  AI-ENHANCED 2025 BACKTEST")
    print(f"{'='*60}")
    print(f"  Return:  {m['total_return_pct']:.2f}%")
    print(f"  WinRate: {m['win_rate']:.1f}%")
    print(f"  MaxDD:   {m['max_drawdown_pct']:.1f}%")
    print(f"  Sharpe:  {m['sharpe_ratio']:.4f}")
    print(f"  Trades:  {m['total_trades']}")
    print(f"  Saved:   {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
