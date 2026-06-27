"""A-share symbol normalization for yfinance/TradingAgents compatibility."""
from __future__ import annotations

# Shanghai Stock Exchange prefixes
_SHANGHAI_PREFIXES = ("600", "601", "603", "605", "688")

# Shenzhen Stock Exchange prefixes
_SHENZHEN_PREFIXES = ("000", "001", "002", "003", "300", "301")


def normalize_a_share_symbol(symbol: str) -> str:
    """Map a 6-digit A-share code to a yfinance-compatible symbol.

    Args:
        symbol: 6-digit stock code, e.g. "600519" or "000001".

    Returns:
        Symbol with exchange suffix, e.g. "600519.SS" or "000001.SZ".
    """
    if symbol.startswith(_SHANGHAI_PREFIXES):
        return f"{symbol}.SS"
    elif symbol.startswith(_SHENZHEN_PREFIXES):
        return f"{symbol}.SZ"
    else:
        return f"{symbol}.SZ"
