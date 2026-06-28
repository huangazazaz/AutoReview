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
        try:
            get_strategy(name)
        except KeyError:
            return name  # Name is available
        # Append _v2, _v3, etc.
        suffix = 2
        while True:
            new_name = f"{name}_v{suffix}"
            try:
                get_strategy(new_name)
            except KeyError:
                return new_name
            suffix += 1

    @staticmethod
    def is_builtin(name: str) -> bool:
        """Check if a strategy name is built-in (protected from deletion)."""
        return name in _BUILTIN_STRATEGIES
