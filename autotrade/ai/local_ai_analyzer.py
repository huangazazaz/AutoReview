"""Local AI analyzer — uses local parquet data + DeepSeek for single-call analysis.

Bypasses yfinance and TradingAgents entirely. Extracts technical indicators
from our parquet cache, sends a structured prompt to DeepSeek, returns Buy/Hold/Sell.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd
from openai import OpenAI

from autotrade.ai.symbol_utils import normalize_a_share_symbol

logger = logging.getLogger(__name__)

# Prompt template for DeepSeek
_ANALYSIS_PROMPT = """You are a quantitative trader analyzing Chinese A-shares. 
Respond with EXACTLY one word: Buy, Hold, or Sell. No explanation.

Stock: {symbol} ({name})
Date: {date_str}
Price: ¥{close:.2f}

Performance:
  5-day:  {mom_5d:+.1f}%
  20-day: {mom_20d:+.1f}%
  60-day: {mom_60d:+.1f}%

Moving Averages:
  MA5:  ¥{ma5:.2f}  (price {ma5_status})
  MA10: ¥{ma10:.2f}  (price {ma10_status})
  MA20: ¥{ma20:.2f}  (price {ma20_status})
  MA60: ¥{ma60:.2f}  (price {ma60_status})
  Bulls: {bull_count}/4

Volume:
  5d avg: {vol_avg:,.0f}
  vs 20d: {vol_ratio:.1f}x

Risk:
  ATR/Close: {atr_ratio:.1f}%
  20d range: {range_20d:.1f}%
  Volatility: {volatility:.1f}%

Decision (Buy/Hold/Sell):"""


class LocalAIAnalyzer:
    """Single-call DeepSeek analysis using local parquet data."""

    def __init__(self, api_key: str, model: str = "deepseek-chat",
                 base_url: str = "https://api.deepseek.com"):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def analyze(
        self,
        symbol: str,
        d: date,
        market_data: dict[str, pd.DataFrame],
        stock_names: Optional[dict[str, str]] = None,
    ) -> str:
        """Analyze one stock on one date. Returns Buy/Hold/Sell."""
        df = market_data.get(symbol)
        if df is None or df.empty:
            return "Hold"

        date_str = d.isoformat()

        # Find the row for this date
        try:
            if d in df.index:
                row_idx = d
            else:
                # Find closest date before d
                before = df.index[df.index <= pd.Timestamp(d)]
                if len(before) == 0:
                    return "Hold"
                row_idx = before[-1]
        except Exception:
            return "Hold"

        # Get data up to this date
        hist = df.loc[:row_idx]
        if len(hist) < 20:
            return "Hold"

        try:
            indicators = self._compute_indicators(hist)
        except Exception as e:
            logger.warning("Indicator computation failed for %s: %s", symbol, e)
            return "Hold"

        name = (stock_names or {}).get(symbol, symbol)
        normalized = normalize_a_share_symbol(symbol)

        prompt = _ANALYSIS_PROMPT.format(
            symbol=normalized,
            name=name,
            date_str=date_str,
            **indicators,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10,
            )
            decision = response.choices[0].message.content.strip()
            # Normalize
            decision = decision.strip().rstrip(".").capitalize()
            if decision not in ("Buy", "Hold", "Sell"):
                if "buy" in decision.lower():
                    decision = "Buy"
                elif "sell" in decision.lower():
                    decision = "Sell"
                else:
                    decision = "Hold"
            logger.info("AI: %s on %s → %s", symbol, date_str, decision)
            return decision
        except Exception as e:
            logger.warning("DeepSeek API error for %s: %s", symbol, e)
            return "Hold"

    @staticmethod
    def _compute_indicators(hist: pd.DataFrame) -> dict:
        """Compute technical indicators from OHLCV history."""
        close = hist["close"].values
        high = hist["high"].values
        low = hist["low"].values
        volume = hist["volume"].values

        current_close = float(close[-1])
        n = len(close)

        # Momentum
        mom_5d = (current_close / close[-6] - 1) * 100 if n >= 6 else 0
        mom_20d = (current_close / close[-21] - 1) * 100 if n >= 21 else 0
        mom_60d = (current_close / close[-61] - 1) * 100 if n >= 61 else 0

        # Moving averages
        def sma(arr, period):
            return float(np.mean(arr[-period:])) if len(arr) >= period else float(arr[-1])

        ma5 = sma(close, 5)
        ma10 = sma(close, 10)
        ma20 = sma(close, 20)
        ma60 = sma(close, 60)

        # Bull count: how many MAs are in bullish order (shorter > longer)
        bull_count = sum([
            1 if current_close > ma5 else 0,
            1 if ma5 > ma10 else 0,
            1 if ma10 > ma20 else 0,
            1 if ma20 > ma60 else 0,
        ])

        # Volume
        vol_5d = float(np.mean(volume[-5:])) if n >= 5 else float(volume[-1])
        vol_20d = float(np.mean(volume[-20:])) if n >= 20 else float(volume[-1])
        vol_ratio = vol_5d / vol_20d if vol_20d > 0 else 1.0

        # ATR
        tr = np.maximum(
            high[-20:] - low[-20:],
            np.maximum(
                np.abs(high[-20:] - np.roll(close[-21:-1], 1)[:20]),
                np.abs(low[-20:] - np.roll(close[-21:-1], 1)[:20]),
            )
        )
        atr = float(np.mean(tr)) if len(tr) > 0 else 0.01
        atr_ratio = (atr / current_close) * 100 if current_close > 0 else 0

        # 20-day range
        h20 = float(np.max(high[-20:])) if n >= 20 else float(high[-1])
        l20 = float(np.min(low[-20:])) if n >= 20 else float(low[-1])
        range_20d = ((h20 - l20) / current_close) * 100 if current_close > 0 else 0

        # Volatility (std of daily returns)
        returns = np.diff(close[-21:]) / close[-21:-1]
        volatility = float(np.std(returns)) * 100 * np.sqrt(252) if len(returns) > 1 else 0

        return {
            "close": current_close,
            "mom_5d": mom_5d,
            "mom_20d": mom_20d,
            "mom_60d": mom_60d,
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "ma60": ma60,
            "ma5_status": "above" if current_close > ma5 else "below",
            "ma10_status": "above" if current_close > ma10 else "below",
            "ma20_status": "above" if current_close > ma20 else "below",
            "ma60_status": "above" if current_close > ma60 else "below",
            "bull_count": bull_count,
            "vol_avg": vol_5d,
            "vol_ratio": vol_ratio,
            "atr_ratio": atr_ratio,
            "range_20d": range_20d,
            "volatility": volatility,
        }
