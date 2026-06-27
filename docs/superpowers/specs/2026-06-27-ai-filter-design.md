# AI-Enhanced Portfolio Backtest — Design Spec

**Date**: 2026-06-27  
**Status**: Draft  
**Branch**: dev/autotrade-mvp

---

## 1. Motivation

The current portfolio backtest uses the rule-based MomentumScreener for stock selection. While fast and scalable (5000+ stocks in minutes), it lacks deep qualitative analysis — it can't read news, evaluate sentiment, or perform multi-perspective reasoning.

TradingAgents (https://github.com/TauricResearch/TradingAgents) brings LLM-powered multi-agent analysis: analyst teams debate, a trader proposes actions, and risk management approves/rejects. By layering this AI analysis on top of the screener's candidate pool, we get the best of both worlds: **screener speed for breadth + LLM depth for precision**.

---

## 2. Goals

1. **Integrate TradingAgents** as a secondary filter after the MomentumScreener
2. **Screener → AI → Backtest pipeline**: screener picks top N candidates, AI filters to only "Buy"-rated stocks, backtester executes
3. **LLM caching**: same stock on same date never analyzed twice; results persisted to disk
4. **Cost-aware**: configurable max candidates per day, DeepSeek as default provider
5. **Fault-tolerant**: LLM failures/timeouts default to "Hold" (skip), never block the backtest
6. **Backtest-compatible**: the full 3-year pipeline runs end-to-end with AI filtering

---

## 3. Non-Goals

- Real-time trading or live AI analysis
- Multiple LLM provider failover (v1: DeepSeek only)
- Per-stock detailed AI reports in backtest output (v1: binary Buy/Not-Buy)
- AI-based exit decisions (exits remain rule-based)
- Replacing the screener entirely with AI

---

## 4. Architecture

### 4.1 Component Diagram

```
config/backtest/portfolio.yaml  (updated)
       │
       ▼
engine.run_portfolio_backtest()
       │
       ├──► Screener.scan(market_data, dates)
       │       └──► {date: [(symbol, score, tag), ...]}   (top 50 per day)
       │
       ├──► NEW: AIFilter.analyze_batch(screener_results, market_data)
       │       │
       │       ├──► TradingAgentsWrapper.propagate(symbol, date) → "Buy"/"Hold"/"Sell"
       │       │       └──► DeepSeek LLM (via TradingAgents)
       │       │
       │       ├──► LLMCache: {(symbol, date): decision}  (disk + memory)
       │       │
       │       └──► {date: [(symbol, score, tag), ...]}   (only "Buy" rated)
       │
       └──► PortfolioBacktester.run(market_data, filtered_selection)
               └──► equity_curve, trades, metrics
```

### 4.2 New Files

| File | Purpose |
|------|---------|
| `autotrade/ai/__init__.py` | Package init |
| `autotrade/ai/trading_agents_wrapper.py` | Wraps TradingAgentsGraph for batch analysis |
| `autotrade/ai/llm_cache.py` | Persistent cache for LLM decisions |
| `autotrade/ai/ai_filter.py` | Pipe: receives screener output, returns AI-filtered subset |

### 4.3 Modified Files

| File | Change |
|------|--------|
| `autotrade/core/engine.py` | Add AI filter step in `run_portfolio_backtest()` |
| `config/backtest/portfolio.yaml` | Add `ai_filter` config section |
| `requirements.txt` / `pyproject.toml` | Add `tradingagents` dependency |

---

## 5. Component Details

### 5.1 TradingAgentsWrapper (`trading_agents_wrapper.py`)

Thin wrapper around `TradingAgentsGraph`:

```python
class TradingAgentsWrapper:
    def __init__(self, config: dict):
        self.llm_provider = config.get("llm_provider", "deepseek")
        self.deep_think_llm = config.get("deep_think_llm", "deepseek-chat")
        self.quick_think_llm = config.get("quick_think_llm", "deepseek-chat")
        self.max_debate_rounds = config.get("max_debate_rounds", 1)
        self.timeout = config.get("timeout_seconds", 120)
        self._graph = None  # lazy init

    def analyze(self, symbol: str, date_str: str) -> str:
        """Returns one of: 'Buy', 'Overweight', 'Hold', 'Underweight', 'Sell'"""
        # Normalize A-share symbol (e.g., "000001" → "000001.SZ")
        # Call TradingAgentsGraph.propagate(normalized_symbol, date_str)
        # Return decision string
```

**Symbol normalization**: A-share codes need exchange suffixes for yfinance:
- `000xxx`, `002xxx`, `003xxx`, `300xxx` → `.SZ` (Shenzhen)
- `600xxx`, `601xxx`, `603xxx`, `605xxx`, `688xxx` → `.SS` (Shanghai)
- `001xxx` → check market_data for exchange hint, default `.SZ`

**Provider config**: DeepSeek via TradingAgents' built-in support. Requires `DEEPSEEK_API_KEY` env var.

**Error handling**: 
- Timeout → return `"Hold"` after `timeout_seconds`
- API error → return `"Hold"`, log warning
- Invalid response → return `"Hold"`, log warning

### 5.2 LLMCache (`llm_cache.py`)

```python
class LLMCache:
    def __init__(self, cache_dir: str = "data/cache/llm"):
        self.cache_dir = Path(cache_dir)
        self._memory: dict[tuple[str, str], str] = {}  # (symbol, date) → decision

    def get(self, symbol: str, date_str: str) -> Optional[str]:
        ...

    def set(self, symbol: str, date_str: str, decision: str):
        ...

    def save_to_disk(self):
        """Persist memory cache to JSON file."""

    def load_from_disk(self):
        """Load cache from JSON file."""
```

Cache key: `(symbol, date_str)`. Cache is loaded at startup, written after each batch or on completion. Avoids re-analyzing the same stock on the same date across multiple backtest runs.

### 5.3 AIFilter (`ai_filter.py`)

```python
class AIFilter:
    def __init__(self, wrapper: TradingAgentsWrapper, cache: LLMCache,
                 config: dict):
        self.wrapper = wrapper
        self.cache = cache
        self.max_candidates_per_day = config.get("max_candidates_per_day", 10)
        self.enabled = config.get("enabled", True)

    def filter(self, screener_results: dict[date, list[tuple[str, float, str]]],
               market_data: dict[str, pd.DataFrame]) -> dict[date, list[tuple[str, float, str]]]:
        """For each day, analyze top N candidates via AI, keep only 'Buy' rated.

        Returns filtered results in same format as screener output.
        """
        if not self.enabled:
            return screener_results

        filtered: dict = {}
        for d, candidates in screener_results.items():
            to_analyze = candidates[:self.max_candidates_per_day]
            kept = []
            for symbol, score, tag in to_analyze:
                decision = self._get_decision(symbol, d)
                if decision in ("Buy", "Overweight"):
                    kept.append((symbol, score, tag))
            if kept:
                filtered[d] = kept
        return filtered

    def _get_decision(self, symbol: str, d: date) -> str:
        date_str = d.isoformat()
        cached = self.cache.get(symbol, date_str)
        if cached:
            return cached
        try:
            decision = self.wrapper.analyze(symbol, date_str)
        except Exception as e:
            logger.warning(f"AI analysis failed for {symbol} on {date_str}: {e}")
            decision = "Hold"
        self.cache.set(symbol, date_str, decision)
        return decision
```

### 5.4 Configuration (`portfolio.yaml` additions)

```yaml
portfolio_backtest:
  # ... existing config ...

  # AI 增强筛选 (基于 TradingAgents)
  ai_filter:
    enabled: true                   # 启用 AI 二次过滤
    max_candidates_per_day: 10      # 每天最多分析多少只候选股
    llm_provider: "deepseek"        # LLM 供应商
    deep_think_llm: "deepseek-chat" # 深度推理模型
    quick_think_llm: "deepseek-chat"# 快速推理模型
    max_debate_rounds: 1            # 牛熊辩论轮数
    timeout_seconds: 120            # 单次分析超时（秒）
    cache_dir: "data/cache/llm"     # 缓存目录
```

---

## 6. Data Flow (Per Trading Day, Updated)

```
For each trading day D:

  EVENING (after D's close):
    1. Screener.scan(all_market_data, [D]) → top 50 candidates
    2. AIFilter.filter(candidates[D]) → analyze top 10 via AI
       - For each of the 10 candidates:
         - Check LLMCache: already analyzed today? → use cached
         - Normalize symbol (add .SZ/.SS suffix)
         - Call TradingAgentsWrapper.analyze(symbol, D.isoformat())
         - TradingAgents internally:
           - Analyst team: market, sentiment, news, fundamentals
           - Bull/Bear debate
           - Trader proposal
           - Risk management review
           - Final decision: Buy/Overweight/Hold/Underweight/Sell
         - Cache the decision
       - Keep only "Buy" or "Overweight" rated stocks
    3. MarketRegime.detect(filtered_candidates) → max_positions
    4. Plan buys for D+1 from filtered candidates

  MORNING (D+1's open):
    5. Execute pending buys, check exits, record equity
```

---

## 7. AI Analysis Timing

The AI analysis happens in the "evening" phase (after close), so it has access to that day's data but doesn't delay the next day's trading. This introduces no look-ahead bias — the AI sees data available as of D's close, and trades execute at D+1's open.

**Important**: The screener already uses D's close data. The AI filter uses the same D's close data (via yfinance, which has end-of-day data by the time we query). No future information leaks.

---

## 8. Symbol Normalization

A-share codes in our system are 6-digit strings without exchange suffix. TradingAgents/yfinance requires exchange suffixes:

```python
def normalize_a_share_symbol(symbol: str) -> str:
    """Map 6-digit A-share code to yfinance symbol."""
    if symbol.startswith(("600", "601", "603", "605", "688")):
        return f"{symbol}.SS"   # Shanghai
    elif symbol.startswith(("000", "001", "002", "003", "300", "301")):
        return f"{symbol}.SZ"   # Shenzhen
    else:
        return f"{symbol}.SZ"   # default Shenzhen
```

---

## 9. Error Handling & Resilience

| Scenario | Behavior |
|----------|----------|
| TradingAgents import fails | Log warning, disable AI filter, continue with screener-only |
| DEEPSEEK_API_KEY not set | Log error, disable AI filter |
| LLM API timeout (>120s) | Return "Hold" for that stock, continue with next |
| LLM returns gibberish | Parse fails → "Hold" |
| Network error during analysis | Retry once, then "Hold" |
| All candidates filtered out | No buys for that day (account stays in cash) |
| Cache file corrupted | Delete cache, start fresh |

---

## 10. Testing Strategy

### Unit Tests

| # | Test | What it validates |
|---|------|-------------------|
| 1 | `test_symbol_normalization_ss` | 600xxx → .SS |
| 2 | `test_symbol_normalization_sz` | 000xxx → .SZ |
| 3 | `test_cache_hit` | Same (symbol, date) returns cached value |
| 4 | `test_cache_miss_returns_none` | Uncached key returns None |
| 5 | `test_cache_persist_and_load` | Save → load → same values |
| 6 | `test_ai_filter_keep_buy` | "Buy" decision → stock kept |
| 7 | `test_ai_filter_drop_hold` | "Hold" decision → stock filtered out |
| 8 | `test_ai_filter_drop_sell` | "Sell" decision → stock filtered out |
| 9 | `test_ai_filter_respects_max_candidates` | Only top N analyzed |
| 10 | `test_ai_filter_disabled_passthrough` | ai_filter.enabled=false → no filtering |
| 11 | `test_wrapper_error_returns_hold` | API failure → "Hold" |
| 12 | `test_empty_candidates_no_error` | Empty list → empty result |

### Integration Test

- Run a 1-week backtest with a small symbol set and `ai_filter.enabled=true`
- Mock `TradingAgentsWrapper` to avoid real API calls
- Verify pipeline: screener → AI filter → backtester runs without error

---

## 11. Implementation Order

1. **Install TradingAgents** — pip install, verify import, test with DeepSeek
2. **`symbol_utils.py`** — A-share symbol normalization
3. **`llm_cache.py`** — Persistent cache for LLM decisions
4. **`trading_agents_wrapper.py`** — Wrap TradingAgentsGraph for batch use
5. **`ai_filter.py`** — AIFilter pipe component
6. **`portfolio.yaml` update** — Add ai_filter config section
7. **`engine.py` update** — Wire AIFilter into run_portfolio_backtest()
8. **Unit tests** — 12 tests
9. **Integration test** — Mocked end-to-end pipeline
10. **Full backtest run** — 3-year with AI filter enabled (with caching for progressive runs)

---

## 12. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LLM API cost (DeepSeek charges per token) | Max 10 candidates/day × 722 days = 7220 calls max, but caching makes repeated runs nearly free |
| LLM latency (10 calls × 30s = 5 min/day) | Batched sequentially; 10 stocks/day × 30s ≈ 5 min per trading day — too slow for 722 days. **Mitigation**: pre-compute AI decisions as a separate phase before backtest, or use aggressive caching across runs |
| yfinance data quality for A-shares | TradingAgents uses yfinance for fundamentals/news — quality may vary. Accept as experimental |
| DeepSeek API stability | Timeout + retry; failures default to Hold (safe) |
| TradingAgents version compatibility | Pin version in requirements |
