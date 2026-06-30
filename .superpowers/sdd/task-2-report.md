# Task 2 Report: Multi-Turn Prompt in StrategyGenerator

## Summary
Added multi-turn chat functionality to `StrategyGenerator` with a context-aware prompt (`CHAT_SYSTEM_PROMPT`), a `chat()` method, and a `_build_chat_prompt()` helper.

## What Was Done

### Files Modified

1. **`autotrade/ai/strategy_generator.py`** — Added:
   - `CHAT_SYSTEM_PROMPT` constant (lines 61–112): A system prompt for multi-turn conversations that tells DeepSeek it's in a chat context, with rules for `generate`/`modify`/`chat` actions.
   - `chat()` method (lines 165–231): Accepts `conversation_history` (list of `{role, content, strategy?}` dicts) and `current_prompt`, sends to DeepSeek, parses the JSON response, validates action type, and returns `{action, message, strategy?}`.
   - `_build_chat_prompt()` method (lines 233–252): Formats conversation history into readable Chinese-labeled text, with strategy code truncation (>500 chars) for token efficiency, and injects it into `CHAT_SYSTEM_PROMPT`.

2. **`tests/unit/test_strategy_generator.py`** — Added:
   - `TestStrategyGeneratorChat` class with 4 test methods:
     - `test_chat_sends_conversation_history` — verifies conversation history is embedded in the API call's user message
     - `test_chat_handles_generate_action` — verifies parsing of `action: "generate"` with strategy code
     - `test_chat_handles_modify_action` — verifies parsing of `action: "modify"` with modified code
     - `test_chat_build_prompt_includes_history_context` — verifies `_build_chat_prompt` includes prior strategy and user intent

## Deviations from Brief

The task brief had two internal inconsistencies that required pragmatic fixes:

1. **Chat response JSON format**: The brief's `chat()` called `_parse_response()` which validates top-level fields (`name`, `display_name`, etc.) — but the chat response format nests those under a `strategy` key. Fixed by implementing inline JSON parsing in `chat()` with chat-specific field validation (checking `action`/`message` at top level, and strategy fields only when `action` is `generate`/`modify`).

2. **Test assertion on message count**: The brief's test asserted `len(messages) >= 3` (system + separate history messages), but the implementation sends history inline within a single user prompt (2 messages total). Fixed the test to assert `len(messages) == 2` while still verifying history content is present in the user message.

## Test Results

```
tests/unit/test_strategy_generator.py::TestStrategyGeneratorChat::test_chat_sends_conversation_history PASSED
tests/unit/test_strategy_generator.py::TestStrategyGeneratorChat::test_chat_handles_generate_action PASSED
tests/unit/test_strategy_generator.py::TestStrategyGeneratorChat::test_chat_handles_modify_action PASSED
tests/unit/test_strategy_generator.py::TestStrategyGeneratorChat::test_chat_build_prompt_includes_history_context PASSED

4 passed in 1.62s
```

## Regression Check

All existing `TestStrategyGenerator` tests pass (8/9). The one pre-existing failure (`test_name_conflict_resolution`) was verified to exist before Task 2 changes — it's a registry initialization issue unrelated to this task.

```
12 passed, 1 failed (pre-existing: test_name_conflict_resolution)
```

## Commit

```
65fb832 feat: add multi-turn chat() method with context-aware prompt to StrategyGenerator
```

2 files changed, 257 insertions(+).

## Fix Report

### Issues Addressed

**1. Code duplication in JSON extraction** (`autotrade/ai/strategy_generator.py`)

The markdown-fence-stripping + `json.loads()` pattern was duplicated verbatim in both `chat()` and `_parse_response()`. Extracted into a shared private method:

```python
def _extract_json(self, raw: str) -> dict:
```

Both callers now use `self._extract_json(raw)` and check for `"error"` in the result before proceeding. `_parse_response` focuses purely on field validation after extraction.

**2. Missing isinstance guard after json.loads()**

Added a guard in `_extract_json` against the AI returning a JSON array instead of an object:

```python
if not isinstance(data, dict):
    return {"error": "AI 返回格式异常", "raw": raw}
```

This prevents `AttributeError` crashes when `.get()` is called on a non-dict result.

### Test Results (after fix)

```
tests/unit/test_strategy_generator.py::TestStrategyGenerator::test_build_prompt_includes_user_input PASSED
tests/unit/test_strategy_generator.py::TestStrategyGenerator::test_parse_valid_json_response PASSED
tests/unit/test_strategy_generator.py::TestStrategyGenerator::test_parse_invalid_json_returns_error PASSED
tests/unit/test_strategy_generator.py::TestStrategyGenerator::test_parse_missing_fields_returns_error PASSED
tests/unit/test_strategy_generator.py::TestStrategyGenerator::test_validate_python_syntax_ok PASSED
tests/unit/test_strategy_generator.py::TestStrategyGenerator::test_validate_python_syntax_error PASSED
tests/unit/test_strategy_generator.py::TestStrategyGenerator::test_name_conflict_resolution FAILED (pre-existing)
tests/unit/test_strategy_generator.py::TestStrategyGenerator::test_generate_success PASSED
tests/unit/test_strategy_generator.py::TestStrategyGenerator::test_generate_api_error PASSED
tests/unit/test_strategy_generator.py::TestStrategyGeneratorChat::test_chat_sends_conversation_history PASSED
tests/unit/test_strategy_generator.py::TestStrategyGeneratorChat::test_chat_handles_generate_action PASSED
tests/unit/test_strategy_generator.py::TestStrategyGeneratorChat::test_chat_handles_modify_action PASSED
tests/unit/test_strategy_generator.py::TestStrategyGeneratorChat::test_chat_build_prompt_includes_history_context PASSED

12 passed, 1 failed (pre-existing: test_name_conflict_resolution — registry init issue, unrelated)
```
