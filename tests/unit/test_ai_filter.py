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


import tempfile
from pathlib import Path
from autotrade.ai.llm_cache import LLMCache


class TestLLMCache:
    def test_cache_hit(self):
        cache = LLMCache()
        cache.set("000001", "2024-01-15", "Buy")
        assert cache.get("000001", "2024-01-15") == "Buy"

    def test_cache_miss_returns_none(self):
        cache = LLMCache()
        assert cache.get("000001", "2024-01-15") is None

    def test_cache_different_date_different_entry(self):
        cache = LLMCache()
        cache.set("000001", "2024-01-15", "Buy")
        cache.set("000001", "2024-01-16", "Sell")
        assert cache.get("000001", "2024-01-15") == "Buy"
        assert cache.get("000001", "2024-01-16") == "Sell"

    def test_cache_different_symbol_independent(self):
        cache = LLMCache()
        cache.set("000001", "2024-01-15", "Buy")
        cache.set("600519", "2024-01-15", "Sell")
        assert cache.get("000001", "2024-01-15") == "Buy"
        assert cache.get("600519", "2024-01-15") == "Sell"

    def test_cache_persist_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "cache.json"
            cache = LLMCache(cache_dir=str(tmp))
            cache.set("000001", "2024-01-15", "Buy")
            cache.set("600519", "2024-01-16", "Sell")
            cache.save_to_disk()

            # Load into new cache
            cache2 = LLMCache(cache_dir=str(tmp))
            cache2.load_from_disk()
            assert cache2.get("000001", "2024-01-15") == "Buy"
            assert cache2.get("600519", "2024-01-16") == "Sell"
            assert cache2.get("000001", "2024-01-17") is None

    def test_cache_overwrite(self):
        cache = LLMCache()
        cache.set("000001", "2024-01-15", "Buy")
        cache.set("000001", "2024-01-15", "Sell")  # overwrite
        assert cache.get("000001", "2024-01-15") == "Sell"
