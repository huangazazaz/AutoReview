#!/usr/bin/env python
"""Standalone script to run a portfolio backtest.

Usage:
    python scripts/run_portfolio_backtest.py

Configuration is read from config/backtest/portfolio.yaml.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autotrade.core.engine import run_portfolio_backtest
from autotrade.registry import init_registry


def main():
    init_registry()

    print("=" * 60)
    print("  AutoTrade — Portfolio Backtest")
    print("=" * 60)

    result = run_portfolio_backtest(
        screener_name="momentum_screener",
        symbols="all",
        reporter_names=("console", "plot"),
    )

    if "error" in result:
        print(f"\n  ✗ Backtest failed: {result['error']}")
        return 1

    print("\n  ✓ Backtest complete")
    if "output_dir" in result:
        print(f"  Results saved to: {result['output_dir']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
