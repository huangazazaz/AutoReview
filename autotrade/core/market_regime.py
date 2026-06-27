"""Market regime detector — maps screener output breadth to max positions."""
from __future__ import annotations


class MarketRegime:
    """Detect market regime from screener candidate quality.

    Uses the average score of candidates above a threshold as a proxy
    for market breadth/health. Higher average → more positions allowed.
    """

    def __init__(
        self,
        score_threshold: float = 0.3,
        bullish_threshold: float = 0.6,
        neutral_threshold: float = 0.4,
    ):
        self.score_threshold = score_threshold
        self.bullish_threshold = bullish_threshold
        self.neutral_threshold = neutral_threshold

    def detect(self, candidates: list[tuple[str, float, str]]) -> int:
        """Return max_positions (0|1|2|3) based on candidate quality.

        Args:
            candidates: List of (symbol, score, tag) sorted by score desc.

        Returns:
            Max simultaneous positions: 0 if no candidates, 1-3 otherwise.
        """
        if not candidates:
            return 0

        valid_scores = [s for _, s, _ in candidates if s >= self.score_threshold]
        if not valid_scores:
            return 1

        avg = sum(valid_scores) / len(valid_scores)
        if avg >= self.bullish_threshold:
            return 3
        elif avg >= self.neutral_threshold:
            return 2
        else:
            return 1
