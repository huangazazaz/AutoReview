"""AI-powered strategy code generator using DeepSeek."""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from openai import OpenAI

from autotrade.registry import init_registry, get_strategy, is_builtin_strategy

logger = logging.getLogger(__name__)

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
- from autotrade.core.interfaces import Strategy  # 基类
- from autotrade.core.models import Signal        # 信号类
- 必须设置 name 属性（与策略名一致）
- required_indicators 声明所需指标（使用 autotrade.indicators 下的类）
- 实现 generate_signals(self, df: pd.DataFrame) -> list[Signal] 方法
  - df 的 index 是 date，包含 open/high/low/close/volume 列 + 指标列
  - 返回 Signal(symbol="", date=date, action="BUY"/"SELL", strength=0.0~1.0, reason="说明")
- __init__ 中不要调用 super().__init__()，直接设置 self.xxx 即可
- 所有 __init__ 参数必须有默认值，否则注册时无法自动发现

可用的指标类（导入路径 → 类名 → 输出列）:
- from autotrade.indicators.ma import MA(period: int) → 列: ind_ma_{{period}}
- from autotrade.indicators.ma import EMA(period: int) → 列: ind_ema_{{period}}
- from autotrade.indicators.rsi import RSI(period: int) → 列: ind_rsi_{{period}}
- from autotrade.indicators.atr import ATR(period: int) → 列: ind_atr_{{period}}
- from autotrade.indicators.macd import MACD(fast: int, slow: int, signal: int) → 列: ind_macd_macd, ind_macd_signal, ind_macd_histogram
- from autotrade.indicators.bollinger import BollingerBands(period: int, std: float) → 列: ind_bb_lower_{{period}}, ind_bb_middle_{{period}}, ind_bb_upper_{{period}}, ind_bb_width_{{period}}（注意列名仅含 period，不含 std！）

重要: 所有列名都有 ind_ 前缀！例如 MA(5) 产生列 ind_ma_5，RSI(14) 产生列 ind_rsi_14。

YAML 格式:
strategy: <name>
params:
  param1: value1
  param2: value2

重要: YAML 中的 params 必须全部在 Python 类的 __init__ 中声明为参数，否则策略无法实例化。例如 YAML 有 stop_loss_pct: 5，则 __init__ 必须有 def __init__(self, stop_loss_pct=5):

用户需求: {user_prompt}"""

CHAT_SYSTEM_PROMPT = """你是一个量化策略工程师，正在多轮对话中帮助交易者设计、优化和回测 A 股交易策略。

上下文: 对话历史中可能包含之前生成的策略代码。当用户要求修改时，找到最近的策略代码并应用更改。

规则:
1. NEW strategy → action="generate": 从零创建完整的 Python 策略类 + YAML 配置。运行回测。
2. MODIFY strategy → action="modify": 从对话上下文中获取最新策略，应用用户请求的更改，输出完整修改后的代码。运行回测。
3. CHAT only → action="chat": 用户提问或讨论想法。用自然中文回复。不要输出策略代码。

始终返回严格的 JSON 格式:
{{
  "action": "generate" | "modify" | "chat",
  "message": "你的自然语言回复",
  "strategy": {{                           // action=chat 时为 null
    "name": "strategy_name",
    "display_name": "策略中文名",
    "description": "一句话描述",
    "python_code": "完整的 Python 策略类代码",
    "yaml_code": "完整的 YAML 配置",
    "reasoning": "设计思路"
  }}
}}

策略 Python 类必须遵循以下接口:
- from autotrade.core.interfaces import Strategy  # 基类
- from autotrade.core.models import Signal        # 信号类
- 必须设置 name 属性（与策略名一致）
- required_indicators 声明所需指标（使用 autotrade.indicators 下的类）
- 实现 generate_signals(self, df: pd.DataFrame) -> list[Signal] 方法
  - df 的 index 是 date，包含 open/high/low/close/volume 列 + 指标列
  - 返回 Signal(symbol="", date=date, action="BUY"/"SELL", strength=0.0~1.0, reason="说明")
- __init__ 中不要调用 super().__init__()，直接设置 self.xxx 即可
- 所有 __init__ 参数必须有默认值，否则注册时无法自动发现

可用的指标类（导入路径 → 类名 → 输出列）:
- from autotrade.indicators.ma import MA(period: int) → 列: ind_ma_{{period}}
- from autotrade.indicators.ma import EMA(period: int) → 列: ind_ema_{{period}}
- from autotrade.indicators.rsi import RSI(period: int) → 列: ind_rsi_{{period}}
- from autotrade.indicators.atr import ATR(period: int) → 列: ind_atr_{{period}}
- from autotrade.indicators.macd import MACD(fast: int, slow: int, signal: int) → 列: ind_macd_macd, ind_macd_signal, ind_macd_histogram
- from autotrade.indicators.bollinger import BollingerBands(period: int, std: float) → 列: ind_bb_lower_{{period}}, ind_bb_middle_{{period}}, ind_bb_upper_{{period}}, ind_bb_width_{{period}}（注意列名仅含 period，不含 std！）

重要: 所有列名都有 ind_ 前缀！例如 MA(5) 产生列 ind_ma_5，RSI(14) 产生列 ind_rsi_14。

YAML 格式:
strategy: <name>
params:
  param1: value1

重要: YAML 中的 params 必须全部在 Python 类的 __init__ 中声明为参数，否则策略无法实例化。

对话历史:
{conversation_history}

用户最新消息: {user_prompt}"""


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

    def chat(self, conversation_history: list[dict], current_prompt: str) -> dict:
        """Multi-turn chat: send full conversation to AI and parse response.

        Args:
            conversation_history: List of {role, content, strategy?} dicts.
            current_prompt: The user's latest message.

        Returns:
            dict with action, message, and optionally strategy fields.
            On error: dict with error and optionally raw.
        """
        prompt = self._build_chat_prompt(conversation_history, current_prompt)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a quantitative trading strategy engineer in a multi-turn conversation. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4096,
            )
            raw = response.choices[0].message.content or ""
        except Exception as e:
            logger.error("DeepSeek API error in chat: %s", e)
            return {"error": "AI 服务暂时不可用，请稍后重试"}

        # Parse JSON — chat response format differs from generate()
        parsed = self._extract_json(raw)
        if "error" in parsed:
            return parsed

        # Validate action field
        action = parsed.get("action", "chat")
        if action not in ("generate", "modify", "chat"):
            action = "chat"

        result: dict = {
            "action": action,
            "message": parsed.get("message", ""),
            "strategy": None,
        }

        if action in ("generate", "modify") and parsed.get("strategy"):
            strat = parsed["strategy"]
            # Check required strategy fields
            required = ["name", "display_name", "description", "python_code", "yaml_code", "reasoning"]
            missing = [f for f in required if f not in strat]
            if missing:
                return {"error": f"AI 响应缺少字段: {', '.join(missing)}", "raw": raw}
            # Validate python_code syntax
            if "python_code" in strat:
                ok, err = self._validate_python(strat["python_code"])
                if not ok:
                    return {"error": f"生成的策略代码有语法错误: {err}", "raw": raw}
                strat["name"] = self._resolve_name(strat["name"])
            result["strategy"] = strat

        return result

    def fix_strategy(
        self,
        history: list[dict],
        user_prompt: str,
        failed_code: str,
        error_msg: str,
    ) -> dict:
        """将回测错误反馈给 AI，让它修复策略代码。

        Args:
            history: 对话历史
            user_prompt: 用户原始需求
            failed_code: 失败的策略 Python 代码
            error_msg: 回测错误信息

        Returns:
            与 chat() 相同格式的响应 dict
        """
        # 截断过长代码，保留后 3000 字符（包含核心逻辑）
        truncated = failed_code
        if len(failed_code) > 3000:
            truncated = "# ... (前段省略)\n" + failed_code[-3000:]

        fix_prompt = (
            f"之前生成的策略在回测时出现错误，请分析并修复。\n\n"
            f"错误信息: {error_msg}\n\n"
            f"失败的策略代码:\n```python\n{truncated}\n```\n\n"
            f"请修复错误并重新输出完整的策略代码（name 保持不变，action=modify）。"
        )
        return self.chat(history, fix_prompt)

    def _build_chat_prompt(self, conversation_history: list[dict], current_prompt: str) -> str:
        """Build the chat prompt with conversation history context."""
        # Format history as readable text, compressing strategy code for token efficiency
        history_lines = []
        history_slice = conversation_history[-20:]  # Last 20 rounds
        for i, msg in enumerate(history_slice):
            role_label = "用户" if msg["role"] == "user" else "AI"
            content = msg.get("content", "")
            # For the latest strategy (last assistant message with code), keep FULL code
            # For older strategies, truncate at 500 chars
            if msg["role"] == "assistant" and msg.get("strategy") and msg["strategy"].get("python_code"):
                code = msg["strategy"]["python_code"]
                is_latest_strategy = (i == len(history_slice) - 1 or
                    not any(m.get("strategy") and m.get("strategy", {}).get("python_code")
                            for m in history_slice[i+1:]))
                if not is_latest_strategy and len(code) > 500:
                    code = code[:500] + "\n# ... (truncated)"
                history_lines.append(f"[{role_label}]: {content}\n[策略代码]:\n```python\n{code}\n```")
            else:
                history_lines.append(f"[{role_label}]: {content}")
        history_text = "\n\n".join(history_lines) if history_lines else "(新对话)"
        return CHAT_SYSTEM_PROMPT.format(
            conversation_history=history_text,
            user_prompt=current_prompt,
        )

    def _build_prompt(self, user_prompt: str) -> str:
        return STRATEGY_GEN_PROMPT.format(user_prompt=user_prompt)

    def _extract_json(self, raw: str) -> dict:
        """Extract JSON from raw AI response, stripping markdown fences.

        Returns a dict on success, or a dict with 'error' and 'raw' keys on failure.
        Guards against AI returning a non-dict (e.g. JSON array).
        """
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

        if not isinstance(data, dict):
            return {"error": "AI 返回格式异常", "raw": raw}

        return data

    def _parse_response(self, raw: str) -> dict:
        """Parse the AI response as JSON and validate required fields."""
        data = self._extract_json(raw)
        if "error" in data:
            return data

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
        return is_builtin_strategy(name)
