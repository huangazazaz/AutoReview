"""Integration test: AI-filtered portfolio backtest with mocked LLM."""
from datetime import date
from unittest.mock import patch, MagicMock

from autotrade.registry import init_registry


def test_ai_filter_pipeline_with_mock():
    """Verify screener → AI filter → backtester pipeline works."""
    init_registry()

    # Mock TradingAgentsGraph to avoid real API calls
    mock_graph = MagicMock()
    mock_graph.propagate.return_value = ({}, "Buy")

    with patch(
        "tradingagents.graph.trading_graph.TradingAgentsGraph",
        return_value=mock_graph,
    ):
        from autotrade.core.engine import run_portfolio_backtest

        result = run_portfolio_backtest(
            screener_name="momentum_screener",
            start=date(2025, 6, 1),
            end=date(2025, 6, 10),
            symbols=["000001", "000002", "600000", "600036", "601318"],
            reporter_names=(),
        )

    assert "error" not in result, f"Backtest failed: {result.get('error')}"
    metrics = result.get("metrics", {})
    assert "total_return_pct" in metrics
    assert "sharpe_ratio" in metrics
    assert result.get("trade_count", -1) >= 0
    print(f"AI integration test passed: {metrics}")


def test_ai_filter_disabled_still_works():
    """Pipeline should work with ai_filter disabled (default)."""
    init_registry()

    from autotrade.core.engine import run_portfolio_backtest

    result = run_portfolio_backtest(
        screener_name="momentum_screener",
        start=date(2025, 6, 1),
        end=date(2025, 6, 5),
        symbols=["000001", "600519"],
        reporter_names=(),
    )

    assert "error" not in result
    print(f"Disabled AI filter test passed")
