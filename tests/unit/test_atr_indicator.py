"""Tests for ATR indicator."""
import pandas as pd
import numpy as np

from autotrade.indicators.atr import ATR


class TestATRIndicator:
    def test_atr_computes_expected_column(self):
        atr = ATR(period=14)
        assert atr.name == "atr"
        assert atr.params == {"period": 14}

        df = pd.DataFrame({
            "high": [10, 11, 12, 11, 10, 11, 12, 13, 14, 13, 12, 11, 10, 11, 12],
            "low":  [8,   9,  9,  8,  7,  8,  9, 10, 11, 10,  9,  8,  7,  8,  9],
            "close":[9,  10, 11, 10,  9, 10, 11, 12, 13, 12, 11, 10,  9, 10, 11],
        }, dtype=float)

        result = atr.compute(df)
        assert "ind_atr_14" in result.columns
        # First 13 rows should be NaN (need 14 periods)
        assert result["ind_atr_14"].iloc[:13].isna().all()
        # First valid value should exist
        assert not pd.isna(result["ind_atr_14"].iloc[13])
        # ATR should be positive
        assert (result["ind_atr_14"].dropna() > 0).all()

    def test_atr_idempotent(self):
        """Calling compute twice should not duplicate work."""
        atr = ATR(period=14)
        df = pd.DataFrame({
            "high": [10, 11, 12], "low": [9, 10, 11], "close": [10, 11, 12],
        }, dtype=float)
        result1 = atr.compute(df)
        result2 = atr.compute(result1)
        pd.testing.assert_frame_equal(result1, result2)

    def test_atr_custom_period(self):
        atr = ATR(period=5)
        df = pd.DataFrame({
            "high": [10, 11, 12, 11, 10, 11],
            "low":  [9,  10, 11, 10,  9, 10],
            "close":[10, 11, 12, 11, 10, 11],
        }, dtype=float)
        result = atr.compute(df)
        assert "ind_atr_5" in result.columns
