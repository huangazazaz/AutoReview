"""Persistent cache for LLM analysis decisions."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class LLMCache:
    """Cache LLM decisions keyed by (symbol, date_str).

    In-memory dict for fast access during a backtest run,
    with JSON persistence for cross-run caching.
    """

    def __init__(self, cache_dir: str = "data/cache/llm"):
        self.cache_dir = Path(cache_dir)
        self._memory: dict[tuple[str, str], str] = {}

    @staticmethod
    def _make_key(symbol: str, date_str: str) -> tuple[str, str]:
        return (symbol, date_str)

    def get(self, symbol: str, date_str: str) -> Optional[str]:
        """Return cached decision or None."""
        return self._memory.get(self._make_key(symbol, date_str))

    def set(self, symbol: str, date_str: str, decision: str):
        """Store a decision in the cache."""
        self._memory[self._make_key(symbol, date_str)] = decision

    def save_to_disk(self):
        """Persist in-memory cache to a JSON file."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self.cache_dir / "decisions.json"
        # Convert tuple keys to string keys for JSON
        serializable = {
            f"{symbol}|{date_str}": decision
            for (symbol, date_str), decision in self._memory.items()
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)

    def load_from_disk(self):
        """Load cache from JSON file into memory."""
        cache_file = self.cache_dir / "decisions.json"
        if not cache_file.exists():
            return
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key, decision in data.items():
            symbol, date_str = key.split("|", 1)
            self._memory[(symbol, date_str)] = decision
