"""Integration test: small-scale portfolio backtest with real data."""
from datetime import date

from autotrade.core.engine import run_portfolio_backtest
from autotrade.registry import init_registry


def test_portfolio_backtest_small_scale():
    """Run a 1-month portfolio backtest with a small symbol set."""
    init_registry()

    result = run_portfolio_backtest(
        screener_name="momentum_screener",
        start=date(2025, 1, 2),
        end=date(2025, 1, 31),
        symbols=["000001", "000002", "600000", "600036", "601318"],
        reporter_names=(),  # no report output during test
    )

    # Should not error
    assert "error" not in result, f"Backtest failed: {result.get('error')}"

    # Should have metrics
    metrics = result.get("metrics", {})
    assert "total_return_pct" in metrics, f"Missing total_return_pct in {metrics}"
    assert "sharpe_ratio" in metrics
    assert "max_drawdown_pct" in metrics

    # Trade count should be non-negative
    assert result.get("trade_count", -1) >= 0

    print(f"Integration test passed: {metrics}")
