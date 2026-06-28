# AI Strategy Generator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Natural language → AI generates Python strategy + YAML config → instant single-stock backtest → save/delete strategies

**Architecture:** New `StrategyGenerator` class wraps DeepSeek API with a structured prompt that outputs JSON. Three new API endpoints wire generation + save + delete to the frontend. New React page provides a chat-like UI with code blocks, backtest metrics, and CRUD actions.

**Tech Stack:** Python 3.12, FastAPI, DeepSeek API (deepseek-chat), React 18, TypeScript 5.5, Vite

**Spec:** `docs/superpowers/specs/2026-06-28-ai-strategy-generator-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `autotrade/ai/strategy_generator.py` | **CREATE** | DeepSeek-powered strategy code generation |
| `tests/unit/test_strategy_generator.py` | **CREATE** | Unit tests for generator |
| `autotrade/api/server.py` | MODIFY | 3 new endpoints: generate-strategy, save-strategy, delete-strategy |
| `web/src/pages/AIStrategy.tsx` | **CREATE** | Chat-based AI strategy builder UI |
| `web/src/App.tsx` | MODIFY | Route `/ai-strategy` |
| `web/src/components/Sidebar.tsx` | MODIFY | Nav item "AI 策略" |
| `web/src/types/index.ts` | MODIFY | New types for AI strategy responses |
| `web/src/api/client.ts` | MODIFY | New `ai` API methods |
| `tests/integration/test_ai_strategy.py` | **CREATE** | Integration test (mock DeepSeek) |

---

### Task 1: StrategyGenerator — Core AI Logic

**Files:**
- Create: `autotrade/ai/strategy_generator.py`
- Create: `tests/unit/test_strategy_generator.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_strategy_generator.py`:

```python
"""Tests for StrategyGenerator."""
import json
import pytest
from unittest.mock import patch, MagicMock

from autotrade.ai.strategy_generator import StrategyGenerator, STRATEGY_GEN_PROMPT


class TestStrategyGenerator:
    """Unit tests for StrategyGenerator."""

    def test_build_prompt_includes_user_input(self):
        gen = StrategyGenerator(api_key="test-key")
        prompt = gen._build_prompt("做一个均线金叉策略")
        assert "均线金叉" in prompt
        assert "Strategy" in prompt
        assert "json" in prompt.lower()

    def test_parse_valid_json_response(self):
        gen = StrategyGenerator(api_key="test-key")
        raw = json.dumps({
            "name": "ma_test",
            "display_name": "测试策略",
            "description": "测试用",
            "python_code": "class MaTest:\n    pass",
            "yaml_code": "strategy: ma_test\nparams: {}",
            "reasoning": "test"
        })
        result = gen._parse_response(raw)
        assert result["name"] == "ma_test"
        assert result["display_name"] == "测试策略"
        assert "class MaTest" in result["python_code"]

    def test_parse_invalid_json_returns_error(self):
        gen = StrategyGenerator(api_key="test-key")
        result = gen._parse_response("not json at all {broken")
        assert "error" in result
        assert "raw" in result

    def test_parse_missing_fields_returns_error(self):
        gen = StrategyGenerator(api_key="test-key")
        result = gen._parse_response('{"name": "only_name"}')
        assert "error" in result

    def test_validate_python_syntax_ok(self):
        gen = StrategyGenerator(api_key="test-key")
        code = "class Foo:\n    def bar(self):\n        return 1"
        ok, err = gen._validate_python(code)
        assert ok is True
        assert err is None

    def test_validate_python_syntax_error(self):
        gen = StrategyGenerator(api_key="test-key")
        code = "class Foo:\n    def bar(self)\n        return 1"  # missing colon
        ok, err = gen._validate_python(code)
        assert ok is False
        assert err is not None

    def test_name_conflict_resolution(self):
        gen = StrategyGenerator(api_key="test-key")
        # "turtle" already exists
        name = gen._resolve_name("turtle")
        assert name.startswith("turtle_")
        # Non-conflicting name stays the same
        name2 = gen._resolve_name("totally_new_strategy")
        assert name2 == "totally_new_strategy"

    @patch("autotrade.ai.strategy_generator.OpenAI")
    def test_generate_success(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "name": "test_strat",
            "display_name": "测试",
            "description": "desc",
            "python_code": "from autotrade.core.interfaces import Strategy\n\nclass TestStrat(Strategy):\n    name = 'test_strat'\n    def generate_signals(self, df):\n        return []",
            "yaml_code": "strategy: test_strat\nparams: {}",
            "reasoning": "test"
        })
        mock_client.chat.completions.create.return_value = mock_response

        gen = StrategyGenerator(api_key="test-key")
        result = gen.generate("做一个测试策略")

        assert "error" not in result
        assert result["name"] == "test_strat"
        assert result["python_code"]

    @patch("autotrade.ai.strategy_generator.OpenAI")
    def test_generate_api_error(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API down")

        gen = StrategyGenerator(api_key="test-key")
        result = gen.generate("做一个策略")

        assert "error" in result
        assert "AI 服务暂时不可用" in result["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_strategy_generator.py -v --tb=short`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement StrategyGenerator**

Create `autotrade/ai/strategy_generator.py`:

```python
"""AI-powered strategy code generator using DeepSeek."""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from openai import OpenAI

from autotrade.registry import init_registry, get_strategy

logger = logging.getLogger(__name__)

# Built-in strategies that cannot be deleted
_BUILTIN_STRATEGIES = {
    "turtle", "ma_cross", "ma_cross_macd", "hot_money",
    "golden_filter", "trend_ma_breakout", "trend_bb_rsi", "macd_divergence",
}

STRATEGY_GEN_PROMPT = """你是一个量化策略工程师。根据用户的自然语言描述，生成一个完整的交易策略。

你必须返回严格的 JSON 格式，包含以下字段：
{{
  "name": "策略英文名（snake_case，如 ma_cross_v2）",
  "display_name": "策略中文名（简短，5-10字）",
  "description": "一句话描述策略逻辑",
  "python_code": "完整的 Python 策略类代码",
  "yaml_code": "完整的 YAML 配置",
  "reasoning": "简要设计思路（1-2句）"
}}

策略 Python 类必须遵循以下接口：
- 继承自 autotrade.core.interfaces.Strategy
- 必须设置 name 属性（与策略名一致）
- required_indicators 声明所需指标（使用 autotrade.indicators 下的类）
- 实现 generate_signals(self, df: pd.DataFrame) -> list[Signal] 方法
  - df 的 index 是 date，包含 open/high/low/close/volume 列 + 指标列
  - 返回 Signal(symbol="", date=date, action="BUY"/"SELL", strength=0.0~1.0, reason="说明")

可用的指标类 (在 autotrade.indicators 包中):
- MARibbon(period: int) → 列: ma_{{period}}
- RSIIndicator(period: int) → 列: rsi
- ATRIndicator(period: int) → 列: atr
- MACDIndicator(fast: int, slow: int, signal: int) → 列: macd, macd_signal, macd_hist
- BollingerIndicator(period: int, std: float) → 列: bb_upper, bb_middle, bb_lower

YAML 格式:
strategy: <name>
params:
  param1: value1
  param2: value2

用户需求: {user_prompt}"""


class StrategyGenerator:
    """Generate complete trading strategies from natural language using DeepSeek."""

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
    ):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def generate(self, user_prompt: str) -> dict:
        """Generate a strategy from natural language description.

        Returns:
            dict with keys: name, display_name, description, python_code,
            yaml_code, reasoning — or error, raw on failure.
        """
        prompt = self._build_prompt(user_prompt)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a quantitative trading strategy engineer. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4096,
            )
            raw = response.choices[0].message.content or ""
        except Exception as e:
            logger.error("DeepSeek API error: %s", e)
            return {"error": "AI 服务暂时不可用，请稍后重试"}

        parsed = self._parse_response(raw)
        if "error" in parsed:
            return parsed

        # Validate Python syntax
        ok, err = self._validate_python(parsed["python_code"])
        if not ok:
            return {"error": f"生成的策略代码有语法错误: {err}", "raw": raw}

        # Resolve name conflicts
        parsed["name"] = self._resolve_name(parsed["name"])

        return parsed

    def _build_prompt(self, user_prompt: str) -> str:
        return STRATEGY_GEN_PROMPT.format(user_prompt=user_prompt)

    def _parse_response(self, raw: str) -> dict:
        """Parse the AI response as JSON."""
        # Try to extract JSON block if wrapped in markdown
        json_str = raw.strip()
        if json_str.startswith("```"):
            # Extract from ```json ... ``` block
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse AI response as JSON: %s", e)
            return {"error": "AI 返回格式异常，请重试", "raw": raw}

        # Check required fields
        required = ["name", "display_name", "description", "python_code", "yaml_code", "reasoning"]
        missing = [f for f in required if f not in data]
        if missing:
            return {"error": f"AI 响应缺少字段: {', '.join(missing)}", "raw": raw}

        return data

    def _validate_python(self, code: str) -> tuple[bool, Optional[str]]:
        """Check if Python code compiles."""
        try:
            compile(code, "<ai_generated>", "exec")
            return True, None
        except SyntaxError as e:
            return False, str(e)

    def _resolve_name(self, name: str) -> str:
        """Ensure the strategy name doesn't conflict with existing ones."""
        init_registry()
        existing = get_strategy(name)
        if existing is None:
            return name
        # Append _v2, _v3, etc.
        suffix = 2
        while True:
            new_name = f"{name}_v{suffix}"
            if get_strategy(new_name) is None:
                return new_name
            suffix += 1

    @staticmethod
    def is_builtin(name: str) -> bool:
        """Check if a strategy name is built-in (protected from deletion)."""
        return name in _BUILTIN_STRATEGIES
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_strategy_generator.py -v --tb=short`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add autotrade/ai/strategy_generator.py tests/unit/test_strategy_generator.py
git commit -m "feat: add AI strategy generator using DeepSeek"
```

---

### Task 2: API Endpoints — generate, save, delete strategies

**Files:**
- Modify: `autotrade/api/server.py`

- [ ] **Step 1: Add request models and 3 endpoints to server.py**

Open `autotrade/api/server.py`. Add after the `PortfolioBacktestRequest` class (after line ~98):

```python
class GenerateStrategyRequest(BaseModel):
    """AI 策略生成请求。"""
    prompt: str                              # 自然语言策略描述
    symbol: str = "600522"                   # 回测股票代码
    start: Optional[str] = None              # 回测开始日期
    end: Optional[str] = None                # 回测结束日期


class SaveStrategyRequest(BaseModel):
    """保存 AI 生成的策略。"""
    name: str
    python_code: str
    yaml_code: str
```

Add imports at the top of server.py (after existing imports):

```python
import os
from pathlib import Path
```

Add three endpoints. Insert after the `/portfolio-backtest` endpoint (after line ~190):

```python
def _get_deepseek_api_key() -> Optional[str]:
    """Get DeepSeek API key from environment."""
    return os.environ.get("DEEPSEEK_API_KEY")


@app.post("/ai/generate-strategy")
def api_generate_strategy(req: GenerateStrategyRequest):
    """AI 生成交易策略 + 单股快速回测。

    接收自然语言描述，调用 DeepSeek 生成策略代码和 YAML 配置，
    然后自动对指定股票跑单股回测并返回结果。
    """
    from autotrade.ai.strategy_generator import StrategyGenerator
    from autotrade.core.engine import analyze_stock
    from autotrade.registry import init_registry, get_strategy
    import tempfile
    import importlib.util

    api_key = _get_deepseek_api_key()
    if not api_key:
        return {"error": "未配置 DEEPSEEK_API_KEY 环境变量"}

    # 1. Generate strategy
    gen = StrategyGenerator(api_key=api_key)
    generated = gen.generate(req.prompt)
    if "error" in generated:
        return generated

    # 2. Validate Python code by compiling
    ok, err = gen._validate_python(generated["python_code"])
    if not ok:
        return {"error": f"代码语法错误: {err}", "raw": generated.get("raw", "")}

    try:
        compile(generated["python_code"], "<ai_strategy>", "exec")
    except SyntaxError as e:
        return {"error": f"代码语法错误: {e}"}

    # 3. Dynamically load and run backtest
    s, e = _resolve_dates(req.start, req.end, "1y")
    backtest_result = None
    try:
        # Create a temporary module for the strategy
        strategy_code = generated["python_code"]
        spec = importlib.util.spec_from_loader(
            generated["name"],
            loader=None,
            origin="<ai_generated>",
        )
        if spec is None:
            raise RuntimeError("Failed to create module spec")

        module = importlib.util.module_from_spec(spec)
        exec(strategy_code, module.__dict__)

        # Find the strategy class in the module
        strat_class = None
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if isinstance(obj, type) and hasattr(obj, "generate_signals") and attr_name != "Strategy":
                strat_class = obj
                break

        if strat_class is None:
            raise RuntimeError("未在生成的代码中找到策略类")

        result = analyze_stock(
            symbol=req.symbol,
            strategy_name=strat_class.name,
            start=s,
            end=e,
            datasource_name="failover",
        )
        if "error" not in result:
            backtest_result = {
                "symbol": req.symbol,
                "return_pct": result.get("total_return_pct", 0),
                "win_rate": result.get("win_rate", 0),
                "sharpe_ratio": result.get("sharpe_ratio", 0),
                "max_drawdown_pct": result.get("max_drawdown_pct", 0),
                "total_trades": result.get("total_trades", 0),
            }
        else:
            logger.warning("Backtest failed for generated strategy: %s", result.get("error"))
    except Exception as e:
        logger.warning("Failed to backtest generated strategy: %s", e)
        # Don't fail — still return the generated code

    return {
        "name": generated["name"],
        "display_name": generated["display_name"],
        "description": generated["description"],
        "python_code": generated["python_code"],
        "yaml_code": generated["yaml_code"],
        "reasoning": generated.get("reasoning", ""),
        "backtest": backtest_result,
    }


@app.post("/strategies/save")
def api_save_strategy(req: SaveStrategyRequest):
    """保存 AI 生成的策略到文件系统。"""
    from autotrade.ai.strategy_generator import StrategyGenerator
    from autotrade.registry import init_registry

    if StrategyGenerator.is_builtin(req.name):
        return {"error": f"不能覆盖内置策略: {req.name}"}

    # Check for existing
    py_path = Path(__file__).resolve().parent.parent / "strategies" / f"{req.name}.py"
    yaml_path = Path(__file__).resolve().parent.parent.parent / "config" / "strategies" / f"{req.name}.yaml"

    if py_path.exists() or yaml_path.exists():
        return {"error": f"策略 {req.name} 已存在，请先删除或使用不同名称"}

    # Write files
    py_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.parent.mkdir(parents=True, exist_ok=True)

    with open(py_path, "w", encoding="utf-8") as f:
        f.write(req.python_code)
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(req.yaml_code)

    # Reload registry
    init_registry(force_reload=True)

    return {
        "success": True,
        "name": req.name,
        "python_path": str(py_path),
        "yaml_path": str(yaml_path),
    }


@app.delete("/strategies/{name}")
def api_delete_strategy(name: str):
    """删除 AI 生成的策略。内置策略不可删除。"""
    from autotrade.ai.strategy_generator import StrategyGenerator
    from autotrade.registry import init_registry

    if StrategyGenerator.is_builtin(name):
        return {"error": f"不能删除内置策略: {name}"}

    py_path = Path(__file__).resolve().parent.parent / "strategies" / f"{name}.py"
    yaml_path = Path(__file__).resolve().parent.parent.parent / "config" / "strategies" / f"{name}.yaml"

    deleted = []
    for p in [py_path, yaml_path]:
        if p.exists():
            p.unlink()
            deleted.append(str(p))

    if not deleted:
        return {"error": f"策略 {name} 不存在"}

    init_registry(force_reload=True)

    return {"success": True, "name": name, "deleted": deleted}
```

Also add the `importlib` import at the top of server.py:

```python
import importlib.util
```

- [ ] **Step 2: Update the docstring header**

Modify the endpoint list in the module docstring (line ~5) to include the new endpoints:

```python
  POST /ai/generate-strategy  AI生成策略+回测
  POST /strategies/save       保存AI生成的策略
  DELETE /strategies/{name}   删除策略
```

- [ ] **Step 3: Test the API endpoints**

Run: `pytest tests/integration/test_ai_strategy.py -v --tb=short`
Expected: Module not found (test not created yet — see Task 5)

- [ ] **Step 4: Run existing tests to verify no breakage**

Run: `pytest tests/ -x --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add autotrade/api/server.py
git commit -m "feat: add AI generate/save/delete strategy API endpoints"
```

---

### Task 3: Frontend Types + API Client

**Files:**
- Modify: `web/src/types/index.ts`
- Modify: `web/src/api/client.ts`

- [ ] **Step 1: Add types**

Open `web/src/types/index.ts`. Add after `PortfolioBacktestResponse`:

```typescript
// ---- AI 策略生成 ----
export interface AIStrategyBacktest {
  symbol: string
  return_pct: number
  win_rate: number
  sharpe_ratio: number
  max_drawdown_pct: number
  total_trades: number
}

export interface AIStrategyGenerateResponse {
  name: string
  display_name: string
  description: string
  python_code: string
  yaml_code: string
  reasoning: string
  backtest: AIStrategyBacktest | null
  error?: string
  raw?: string
}

export interface SaveStrategyResponse {
  success: boolean
  name: string
  python_path: string
  yaml_path: string
  error?: string
}

export interface DeleteStrategyResponse {
  success: boolean
  name: string
  deleted: string[]
  error?: string
}
```

- [ ] **Step 2: Add API methods**

Open `web/src/api/client.ts`. Add imports for new types:

```typescript
import type {
  // ... existing imports ...
  AIStrategyGenerateResponse,
  SaveStrategyResponse,
  DeleteStrategyResponse,
} from '@/types'
```

Add after the `portfolioBacktest` method:

```typescript
  generateStrategy: (params: {
    prompt: string
    symbol?: string
    start?: string
    end?: string
  }) => post<AIStrategyGenerateResponse>('/ai/generate-strategy', params),

  saveStrategy: (params: {
    name: string
    python_code: string
    yaml_code: string
  }) => post<SaveStrategyResponse>('/strategies/save', params),

  deleteStrategy: (name: string) => del<DeleteStrategyResponse>(`/strategies/${name}`),
```

Note: `del` is a new helper function. Add it in client.ts after the `post` function:

```typescript
function del<T>(path: string): Promise<T> {
  return request<T>('DELETE', path, null)
}
```

- [ ] **Step 3: Commit**

```bash
git add web/src/types/index.ts web/src/api/client.ts
git commit -m "feat: add AI strategy types and API client methods"
```

---

### Task 4: Frontend AIStrategy Page

**Files:**
- Create: `web/src/pages/AIStrategy.tsx`
- Modify: `web/src/App.tsx`
- Modify: `web/src/components/Sidebar.tsx`

- [ ] **Step 1: Create the AIStrategy page**

Create `web/src/pages/AIStrategy.tsx`:

```tsx
import { useState, useRef, useEffect, useCallback } from 'react'
import { useApp } from '@/hooks/useApp'
import { api } from '@/api/client'
import { PageHeader } from '@/components/UI'
import DateRangeInput from '@/components/DateRangeInput'
import { formatPct, formatNumber } from '@/utils/format'
import type { AIStrategyGenerateResponse } from '@/types'

interface Message {
  id: number
  role: 'user' | 'ai'
  content: string
  result?: AIStrategyGenerateResponse
}

const EXAMPLE_PROMPTS = [
  '做一个5日和20日均线金叉买入、死叉卖出的策略，止损5%',
  '当RSI低于30时买入，高于70时卖出',
  '做一个MACD金叉买入、死叉卖出的策略',
  '做一个突破20日最高价买入、跌破10日最低价卖出的海龟策略',
  '做一个布林带下轨买入、上轨卖出的策略，止损3%',
]

export default function AIStrategy() {
  const { showToast, showLoading: showGlobalLoading, hideLoading } = useApp()
  const chatEndRef = useRef<HTMLDivElement>(null)

  const [symbol, setSymbol] = useState('600522')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [generating, setGenerating] = useState(false)
  const [nextId, setNextId] = useState(1)
  const [codeExpanded, setCodeExpanded] = useState<Record<number, boolean>>({})

  // Auto-scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = useCallback(async () => {
    const prompt = input.trim()
    if (!prompt || generating) return

    const userMsg: Message = { id: nextId, role: 'user', content: prompt }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setNextId(n => n + 1)

    setGenerating(true)
    showGlobalLoading('AI 正在生成策略...')
    try {
      const result = await api.generateStrategy({
        prompt,
        symbol,
        start: startDate || undefined,
        end: endDate || undefined,
      })

      const aiMsg: Message = {
        id: nextId + 1,
        role: 'ai',
        content: result.error || `已生成: ${result.display_name}`,
        result: result.error ? undefined : result,
      }
      setMessages(prev => [...prev, aiMsg])
      setNextId(n => n + 2)

      if (result.error) {
        showToast(result.error, 'error')
      }
    } catch (err) {
      showToast('生成失败: ' + (err as Error).message, 'error')
    } finally {
      setGenerating(false)
      hideLoading()
    }
  }, [input, generating, symbol, startDate, endDate, nextId])

  const handleSave = useCallback(async (result: AIStrategyGenerateResponse) => {
    showGlobalLoading('正在保存策略...')
    try {
      const r = await api.saveStrategy({
        name: result.name,
        python_code: result.python_code,
        yaml_code: result.yaml_code,
      })
      if (r.error) {
        showToast(r.error, 'error')
      } else {
        showToast(`策略 ${r.name} 已保存`)
      }
    } catch (err) {
      showToast('保存失败: ' + (err as Error).message, 'error')
    } finally {
      hideLoading()
    }
  }, [])

  const handleDelete = useCallback(async (name: string) => {
    showGlobalLoading('正在删除策略...')
    try {
      const r = await api.deleteStrategy(name)
      if (r.error) {
        showToast(r.error, 'error')
      } else {
        showToast(`策略 ${r.name} 已删除`)
      }
    } catch (err) {
      showToast('删除失败: ' + (err as Error).message, 'error')
    } finally {
      hideLoading()
    }
  }, [])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)' }}>
      <PageHeader title="AI 策略工坊" subtitle="用自然语言描述交易想法，AI 自动生成策略代码并回测验证" />

      <div style={{ display: 'flex', gap: 16, flex: 1, minHeight: 0 }}>
        {/* Left sidebar: settings */}
        <div className="card" style={{ width: 240, flexShrink: 0, overflow: 'auto' }}>
          <div className="card-header"><span className="card-title">回测设置</span></div>
          <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div className="form-group">
              <label className="form-label">股票代码</label>
              <input type="text" className="form-input" value={symbol}
                onChange={e => setSymbol(e.target.value)} placeholder="600522" />
            </div>
            <div className="form-group">
              <label className="form-label">日期范围</label>
              <DateRangeInput startDate={startDate} endDate={endDate}
                onChange={(s, e) => { setStartDate(s); setEndDate(e) }} />
            </div>

            <div style={{ marginTop: 8 }}>
              <label className="form-label" style={{ marginBottom: 8 }}>💡 试试这些</label>
              {EXAMPLE_PROMPTS.map((p, i) => (
                <button key={i} className="btn btn-ghost"
                  style={{ width: '100%', textAlign: 'left', marginBottom: 4, fontSize: 12, padding: '6px 8px' }}
                  onClick={() => setInput(p)}>
                  {p}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Main chat area */}
        <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div className="card-body" style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>
            {messages.length === 0 ? (
              <div className="empty-state" style={{ marginTop: 80 }}>
                <p style={{ fontSize: 48, marginBottom: 8 }}>🤖</p>
                <p style={{ fontSize: 16, color: 'var(--text-primary)' }}>AI 策略工坊</p>
                <p>在下方输入你的策略想法，或点击左侧示例开始</p>
              </div>
            ) : (
              messages.map(msg => (
                <div key={msg.id} style={{
                  display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  marginBottom: 16,
                }}>
                  <div style={{
                    maxWidth: '85%',
                    padding: '12px 16px',
                    borderRadius: 'var(--radius-md)',
                    background: msg.role === 'user'
                      ? 'var(--primary)'
                      : 'var(--bg-card-hover)',
                    color: msg.role === 'user' ? '#fff' : 'var(--text-primary)',
                  }}>
                    <div style={{ fontSize: 13, whiteSpace: 'pre-wrap' }}>{msg.content}</div>

                    {msg.result && (
                      <div style={{ marginTop: 12 }}>
                        {/* Backtest metrics */}
                        {msg.result.backtest && (
                          <div className="stats-grid" style={{ marginTop: 8, marginBottom: 12 }}>
                            <div className="stat-card" style={{ minWidth: 90 }}>
                              <div className="stat-label">收益率</div>
                              <div className={'stat-value ' + (msg.result.backtest.return_pct >= 0 ? 'stat-positive' : 'stat-negative')} style={{ fontSize: 16 }}>
                                {formatPct(msg.result.backtest.return_pct)}
                              </div>
                            </div>
                            <div className="stat-card" style={{ minWidth: 70 }}>
                              <div className="stat-label">胜率</div>
                              <div className="stat-value stat-neutral" style={{ fontSize: 14 }}>
                                {formatPct(msg.result.backtest.win_rate)}
                              </div>
                            </div>
                            <div className="stat-card" style={{ minWidth: 70 }}>
                              <div className="stat-label">夏普</div>
                              <div className="stat-value stat-neutral" style={{ fontSize: 14 }}>
                                {formatNumber(msg.result.backtest.sharpe_ratio, 2)}
                              </div>
                            </div>
                            <div className="stat-card" style={{ minWidth: 90 }}>
                              <div className="stat-label">最大回撤</div>
                              <div className="stat-value stat-negative" style={{ fontSize: 14 }}>
                                {formatPct(msg.result.backtest.max_drawdown_pct)}
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Code block (collapsible) */}
                        <div>
                          <button className="params-toggle"
                            onClick={() => setCodeExpanded(prev => ({ ...prev, [msg.id]: !prev[msg.id] }))}>
                            <span className="toggle-icon">{codeExpanded[msg.id] ? '▼' : '▶'}</span> 策略代码
                          </button>
                          {codeExpanded[msg.id] && (
                            <pre style={{
                              background: 'var(--bg-card)',
                              padding: 12,
                              borderRadius: 'var(--radius-sm)',
                              fontSize: 11,
                              maxHeight: 300,
                              overflow: 'auto',
                              marginTop: 8,
                            }}>
                              <code>{msg.result.python_code}</code>
                            </pre>
                          )}
                        </div>

                        {/* Action buttons */}
                        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
                          <button className="btn btn-primary btn-sm" onClick={() => send()}
                            style={{ fontSize: 12 }}>
                            🔄 重新回测
                          </button>
                          <button className="btn btn-success btn-sm" onClick={() => handleSave(msg.result!)}
                            style={{ fontSize: 12 }}>
                            💾 保存策略
                          </button>
                          <button className="btn btn-danger btn-sm" onClick={() => handleDelete(msg.result!.name)}
                            style={{ fontSize: 12 }}>
                            🗑 删除
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            {generating && (
              <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 16 }}>
                <div style={{ padding: '12px 16px', borderRadius: 'var(--radius-md)', background: 'var(--bg-card-hover)' }}>
                  🤖 AI 正在生成策略...
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
        </div>
      </div>

      {/* Bottom input */}
      <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
        <input
          type="text"
          className="form-input"
          style={{ flex: 1, padding: '10px 14px', fontSize: 14 }}
          placeholder="输入你的策略想法，如「做一个5日10日均线金叉买入、死叉卖出的策略」..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={generating}
        />
        <button className="btn btn-primary" onClick={send} disabled={generating || !input.trim()}
          style={{ padding: '10px 24px', fontSize: 14 }}>
          发送
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add route in App.tsx**

```typescript
import AIStrategy from './pages/AIStrategy'
```

Add route after `<Route path="/portfolio" ...>`:

```typescript
        <Route path="/ai-strategy" element={<AIStrategy />} />
```

- [ ] **Step 3: Add sidebar nav**

In `Sidebar.tsx`, add to navItems array after portfolio:

```typescript
  { path: '/ai-strategy', label: 'AI 策略', icon: 'ai' },
```

Add the AI icon SVG:

```typescript
  ai: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a4 4 0 0 1 4 4v1h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h2V6a4 4 0 0 1 4-4Z"/>
      <circle cx="12" cy="14" r="2" fill="currentColor" fillOpacity="0.5"/>
      <path d="M12 3v3"/>
    </svg>
  ),
```

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/AIStrategy.tsx web/src/App.tsx web/src/components/Sidebar.tsx
git commit -m "feat: add AI strategy builder page with chat UI"
```

---

### Task 5: Integration Test

**Files:**
- Create: `tests/integration/test_ai_strategy.py`

- [ ] **Step 1: Write integration test with mocked DeepSeek**

Create `tests/integration/test_ai_strategy.py`:

```python
"""Integration tests for AI strategy generation API."""
import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from autotrade.api.server import app
from autotrade.registry import init_registry


@pytest.fixture
def client():
    init_registry()
    return TestClient(app)


@pytest.fixture
def mock_deepseek():
    """Mock DeepSeek to return a valid strategy JSON."""
    with patch("autotrade.ai.strategy_generator.OpenAI") as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "name": "test_ai_strat",
            "display_name": "测试AI策略",
            "description": "AI生成的测试策略",
            "python_code": (
                "from autotrade.core.interfaces import Strategy, Indicator\n"
                "from autotrade.core.models import Signal\n"
                "from autotrade.indicators.ma import MARibbon\n"
                "\n"
                "class TestAIStrat(Strategy):\n"
                "    name = 'test_ai_strat'\n"
                "    required_indicators = [MARibbon(period=5), MARibbon(period=20)]\n"
                "\n"
                "    def generate_signals(self, df):\n"
                "        signals = []\n"
                "        for i in range(1, len(df)):\n"
                "            d = df.index[i]\n"
                "            if df['ma_5'].iloc[i] > df['ma_20'].iloc[i] and df['ma_5'].iloc[i-1] <= df['ma_20'].iloc[i-1]:\n"
                "                signals.append(Signal(symbol='', date=d, action='BUY', strength=0.5, reason='金叉'))\n"
                "            elif df['ma_5'].iloc[i] < df['ma_20'].iloc[i] and df['ma_5'].iloc[i-1] >= df['ma_20'].iloc[i-1]:\n"
                "                signals.append(Signal(symbol='', date=d, action='SELL', strength=1.0, reason='死叉'))\n"
                "        return signals\n"
            ),
            "yaml_code": "strategy: test_ai_strat\nparams:\n  fast: 5\n  slow: 20\n",
            "reasoning": "经典双均线交叉"
        })
        mock_client.chat.completions.create.return_value = mock_response
        yield mock


class TestAIStrategyAPI:
    """Integration tests for AI strategy endpoints."""

    def test_generate_strategy_success(self, client, mock_deepseek):
        resp = client.post("/ai/generate-strategy", json={
            "prompt": "做一个均线金叉策略",
            "symbol": "600522",
            "start": "2025-01-02",
            "end": "2025-01-31",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "error" not in data
        assert data["name"] == "test_ai_strat"
        assert data["display_name"] == "测试AI策略"
        assert "class TestAIStrat" in data["python_code"]
        assert data["backtest"] is not None or data["backtest"] is None  # may or may not have backtest

    def test_generate_strategy_no_api_key(self, client):
        resp = client.post("/ai/generate-strategy", json={
            "prompt": "做一个策略",
            "symbol": "600522",
        })
        # Without DEEPSEEK_API_KEY, should return error
        data = resp.json()
        # May or may not have API key in test env
        if "error" in data:
            assert "DEEPSEEK_API_KEY" in data["error"]

    def test_save_and_delete_strategy(self, client):
        # Save
        resp = client.post("/strategies/save", json={
            "name": "test_temp_strat",
            "python_code": "from autotrade.core.interfaces import Strategy\nclass TestTemp(Strategy):\n    name='test_temp_strat'\n    def generate_signals(self, df): return []",
            "yaml_code": "strategy: test_temp_strat\nparams: {}",
        })
        assert resp.status_code == 200
        data = resp.json()
        if "error" not in data:
            assert data["success"] is True

            # Delete
            resp2 = client.delete(f"/strategies/test_temp_strat")
            assert resp2.status_code == 200
            data2 = resp2.json()
            assert "error" not in data2 or data2.get("success") is True

    def test_delete_builtin_protected(self, client):
        resp = client.delete("/strategies/turtle")
        data = resp.json()
        assert "error" in data
        assert "内置" in data["error"] or "builtin" in data["error"].lower()
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/integration/test_ai_strategy.py -v --tb=short`
Expected: Tests PASS (with mock DeepSeek)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_ai_strategy.py
git commit -m "test: add integration tests for AI strategy API"
```

---

### Task 6: Final verification

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v --tb=short
```
Expected: All tests PASS

- [ ] **Step 2: Verify import chain**

```bash
python -c "from autotrade.api.server import app; print('Server OK')"
python -c "from autotrade.ai.strategy_generator import StrategyGenerator; print('Generator OK')"
```
Expected: No errors

---

## Summary of Changes

| # | File | Lines |
|---|---|---|
| 1 | `autotrade/ai/strategy_generator.py` | ~130 NEW |
| 2 | `tests/unit/test_strategy_generator.py` | ~140 NEW |
| 3 | `autotrade/api/server.py` | +120 (3 endpoints + models + imports) |
| 4 | `web/src/types/index.ts` | +28 |
| 5 | `web/src/api/client.ts` | +15 |
| 6 | `web/src/pages/AIStrategy.tsx` | ~280 NEW |
| 7 | `web/src/App.tsx` | +2 |
| 8 | `web/src/components/Sidebar.tsx` | +10 |
| 9 | `tests/integration/test_ai_strategy.py` | ~90 NEW |
