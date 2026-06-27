"""Tests for AI filter components."""
from autotrade.ai.symbol_utils import normalize_a_share_symbol


class TestSymbolNormalization:
    def test_shanghai_600(self):
        assert normalize_a_share_symbol("600519") == "600519.SS"

    def test_shanghai_601(self):
        assert normalize_a_share_symbol("601318") == "601318.SS"

    def test_shanghai_603(self):
        assert normalize_a_share_symbol("603259") == "603259.SS"

    def test_shanghai_688(self):
        assert normalize_a_share_symbol("688981") == "688981.SS"

    def test_shenzhen_000(self):
        assert normalize_a_share_symbol("000001") == "000001.SZ"

    def test_shenzhen_002(self):
        assert normalize_a_share_symbol("002415") == "002415.SZ"

    def test_shenzhen_300(self):
        assert normalize_a_share_symbol("300750") == "300750.SZ"

    def test_unknown_prefix_defaults_sz(self):
        assert normalize_a_share_symbol("123456") == "123456.SZ"
