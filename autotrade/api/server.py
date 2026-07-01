"""AutoTrade Web API —— FastAPI 服务器。

启动: autotrade-api  或  uvicorn autotrade.api.server:app

端点:
  POST /analyze              单股回测
  POST /backtest             多股/分组回测
  POST /portfolio-backtest   组合/账户级回测（Screener + 策略）
  POST /ai/generate-strategy AI生成策略+回测
  POST /strategies/save      保存AI生成的策略
  DELETE /strategies/{name}  删除策略
  POST /bars                 日线数据查询
  GET  /strategies           策略列表
  GET  /groups            分组列表
  POST /groups            创建分组
  GET  /groups/{id}       获取分组
  PUT  /groups/{id}       更新分组
  DELETE /groups/{id}     删除分组
  GET  /datasources       数据源列表
  GET  /health            健康检查
"""

from __future__ import annotations

import logging
import os
import importlib.util
from datetime import datetime, date, timezone
from typing import Optional

from pathlib import Path

# 加载 .env 文件中的环境变量（如 DEEPSEEK_API_KEY）
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass

from fastapi import FastAPI, HTTPException, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from autotrade.core.engine import analyze_stock, run_backtest, run_portfolio_backtest
from autotrade.registry import (
    init_registry, list_datasources, list_strategies,
    is_builtin_strategy, is_builtin_group,
)
from autotrade.ai.session_store import SessionStore, ChatMessage as StoreChatMessage
from autotrade.auth.routes import router as auth_router

# Session store singleton
_session_store = SessionStore(ttl_seconds=7200)

import threading

def _start_session_cleanup():
    """Background thread that periodically cleans expired sessions."""
    import time
    while True:
        time.sleep(1800)  # 30 minutes
        try:
            removed = _session_store.cleanup_expired()
            if removed > 0:
                logger.info("Cleaned up %d expired session(s)", removed)
        except Exception as e:
            logger.warning("Session cleanup error: %s", e)

_cleanup_thread = threading.Thread(target=_start_session_cleanup, daemon=True)
_cleanup_thread.start()

# ---- FastAPI 应用 ----
app = FastAPI(
    title="AutoTrade",
    description="A股自动化交易信号生成与回测系统 API",
    version="0.1.0",
)

# ---- CORS 中间件 ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- API 路由（统一前缀 /api）----
api_router = APIRouter(prefix="/api")

# ---- 认证路由（挂载到 /api/auth）----
app.include_router(auth_router, prefix="/api")

app.include_router(api_router)

logger = logging.getLogger(__name__)


# ---- 请求/响应模型 ----

class AnalyzeRequest(BaseModel):
    symbol: str
    strategy: str = "ma_cross"
    start: Optional[str] = None
    end: Optional[str] = None
    period: Optional[str] = "1y"
    datasource: Optional[str] = None
    strategy_params: Optional[dict] = None  # 策略参数覆盖


class BacktestRequest(BaseModel):
    strategy: str = "ma_cross"
    symbols: Optional[str] = None       # "600522,000001"
    group: Optional[str] = None          # "自选"
    start: Optional[str] = None
    end: Optional[str] = None
    period: Optional[str] = "1y"
    datasource: Optional[str] = None
    strategy_params: Optional[dict] = None  # 策略参数覆盖


class PortfolioBacktestRequest(BaseModel):
    """组合/账户级回测请求。"""
    screener_name: str = "momentum_screener"
    strategy_name: Optional[str] = None    # 策略名（None=纯Screener模式）
    strategy_params: Optional[dict] = None  # 策略参数覆盖
    strategy_buy_window: int = 1           # BUY信号匹配窗口
    start: Optional[str] = None
    end: Optional[str] = None
    symbols: Optional[str] = None          # 逗号分隔代码列表
    group: Optional[str] = None            # 分组ID（优先于 symbols）
    datasource: Optional[str] = None


class GenerateStrategyRequest(BaseModel):
    """AI 策略生成请求。"""
    prompt: str                              # 自然语言策略描述
    symbol: str = "600522"                   # 回测股票代码
    start: Optional[str] = None
    end: Optional[str] = None


class SaveStrategyRequest(BaseModel):
    """保存 AI 生成的策略到文件系统。"""
    name: str
    python_code: str
    yaml_code: str


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    prompt: str
    symbol: str = "600522"
    start: Optional[str] = None
    end: Optional[str] = None


class ChatMessageResponse(BaseModel):
    role: str
    content: str
    timestamp: str
    strategy: Optional[dict] = None
    backtest: Optional[dict] = None


class ChatResponse(BaseModel):
    session_id: str
    message: ChatMessageResponse
    strategy: Optional[dict] = None
    backtest: Optional[dict] = None


class ChatHistoryResponse(BaseModel):
    session: dict
    messages: list[ChatMessageResponse]


# ---- 启动事件 ----

@app.on_event("startup")
def _startup():
    init_registry()


# ---- API 端点 ----

@api_router.post("/analyze")
def api_analyze(req: AnalyzeRequest):
    """单股分析回测。"""
    from autotrade.core.config import get_strategy_params
    s, e = _resolve_dates(req.start, req.end, req.period)
    # 合并 YAML 配置与用户覆盖（用户覆盖优先）
    yaml_params = get_strategy_params(req.strategy)
    merged_params = dict(yaml_params.get("params", {})) if yaml_params else {}
    if req.strategy_params:
        merged_params.update(req.strategy_params)
    name_map = _build_stock_name_map()
    result = analyze_stock(
        symbol=req.symbol,
        strategy_name=req.strategy,
        start=s,
        end=e,
        datasource_name=req.datasource or "failover",
        strategy_params=merged_params if merged_params else None,
        stock_name=name_map.get(req.symbol, ""),
    )
    return _format_result(result, req.symbol)


@api_router.post("/backtest")
def api_backtest(req: BacktestRequest):
    """批量回测（多股或分组）。"""
    from autotrade.triggers.cli import _resolve_input, _load_group_names

    symbols_str = _resolve_input(req.symbols, req.group)
    if not symbols_str:
        return {"error": "请指定 symbols 或 group"}

    names = _load_group_names(req.group) if req.group else None
    s, e = _resolve_dates(req.start, req.end, req.period)

    from autotrade.core.config import get_strategy_params
    yaml_params = get_strategy_params(req.strategy)
    merged_params = dict(yaml_params.get("params", {})) if yaml_params else {}
    if req.strategy_params:
        merged_params.update(req.strategy_params)

    summary = run_backtest(
        strategy_name=req.strategy,
        symbols=symbols_str,
        start=s,
        end=e,
        datasource_name=req.datasource or "failover",
        reporter_names=(),
        stock_names=names,
        strategy_params=merged_params if merged_params else None,
    )
    return summary


@api_router.post("/portfolio-backtest")
def api_portfolio_backtest(req: PortfolioBacktestRequest):
    """组合/账户级回测：单账户多持仓 + Screener选股 + 策略择时。

    支持策略驱动模式（如 turtle 管理买卖），也支持纯 Screener 模式。
    支持 symbols 或 group 两种输入方式。
    """
    from autotrade.triggers.cli import _resolve_input

    s, e = _resolve_dates(req.start, req.end, None)

    # Resolve symbols: group takes priority, fallback to symbols or "all"
    symbols_str = _resolve_input(req.symbols, req.group)
    if not symbols_str:
        symbols_str = "all"

    symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]

    result = run_portfolio_backtest(
        screener_name=req.screener_name,
        start=s,
        end=e,
        symbols=symbols,
        datasource_name=req.datasource or "failover",
        strategy_name=req.strategy_name,
        strategy_params=req.strategy_params,
        strategy_buy_window=req.strategy_buy_window,
        reporter_names=(),  # no console reporter during API call
    )

    if "error" in result:
        return {"error": result["error"]}

    metrics = result.get("metrics", {})
    return {
        "metrics": metrics,
        "trade_count": result.get("trade_count", 0),
        "output_dir": result.get("output_dir", ""),
    }


def _get_deepseek_api_key() -> Optional[str]:
    """Get DeepSeek API key from environment."""
    return os.environ.get("DEEPSEEK_API_KEY")


@api_router.post("/ai/generate-strategy")
def api_generate_strategy(req: GenerateStrategyRequest):
    """AI 生成交易策略 + 单股快速回测。"""
    from autotrade.ai.strategy_generator import StrategyGenerator
    from autotrade.core.engine import analyze_stock

    api_key = _get_deepseek_api_key()
    if not api_key:
        return {"error": "未配置 DEEPSEEK_API_KEY 环境变量"}

    # 1. Generate strategy
    gen = StrategyGenerator(api_key=api_key)
    generated = gen.generate(req.prompt)
    if "error" in generated:
        return generated

    # 2. Dynamically load and run backtest
    s, e = _resolve_dates(req.start, req.end, "1y")
    backtest_result = None
    try:
        strategy_code = generated["python_code"]
        spec = importlib.util.spec_from_loader(
            generated["name"], loader=None, origin="<ai_generated>")
        if spec is None:
            raise RuntimeError("Failed to create module spec")

        module = importlib.util.module_from_spec(spec)
        exec(strategy_code, module.__dict__)

        # Find the strategy class in the module
        strat_class = None
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if (isinstance(obj, type)
                    and hasattr(obj, "generate_signals")
                    and hasattr(obj, "name")
                    and attr_name != "Strategy"):
                strat_class = obj
                break

        if strat_class is None:
            raise RuntimeError("未在生成的代码中找到策略类")

        # Run backtest directly (bypass registry — the strategy isn't registered)
        from autotrade.core.engine import _bars_to_dataframe, _make_backtest_config
        from autotrade.core.backtester import Backtester
        from autotrade.core.datasource_factory import build_datasource_from_name

        # Instantiate the strategy from the dynamically loaded class
        # Try with YAML params first, fall back to no-args if params mismatch
        import yaml
        strategy = None
        try:
            parsed_yaml = yaml.safe_load(generated["yaml_code"])
            yaml_params = parsed_yaml.get("params", {}) if isinstance(parsed_yaml, dict) else {}
            strategy = strat_class(**yaml_params)
        except (TypeError, Exception):
            try:
                strategy = strat_class()
            except Exception:
                # Last resort: try with just the required params
                import inspect
                sig_params = inspect.signature(strat_class.__init__).parameters
                # Filter YAML params to only those accepted by __init__
                accepted = {k: v for k, v in yaml_params.items() if k in sig_params}
                strategy = strat_class(**accepted) if accepted else strat_class()

        ds = build_datasource_from_name("failover")
        bars = ds.get_bars(req.symbol, s, e)
        if not bars:
            logger.warning("No bar data for %s", req.symbol)
        else:
            df = _bars_to_dataframe(bars)
            for ind in strategy.required_indicators:
                df = ind.compute(df)

            raw_signals = strategy.generate_signals(df)
            for sig in raw_signals:
                if not sig.symbol:
                    sig.symbol = req.symbol

            config = _make_backtest_config()
            backtester = Backtester(config)
            result = backtester.run(raw_signals, bars)

            backtest_result = {
                "symbol": req.symbol,
                "return_pct": round(result.metrics.get("total_return_pct", 0), 2),
                "win_rate": round(result.metrics.get("win_rate", 0), 2),
                "sharpe_ratio": round(result.metrics.get("sharpe_ratio", 0), 4),
                "max_drawdown_pct": round(result.metrics.get("max_drawdown_pct", 0), 2),
                "total_trades": len(result.trades),
            }
    except Exception as ex:
        logger.warning("Failed to backtest generated strategy: %s", ex)
        backtest_result = {"error": str(ex)}

    return {
        "name": generated["name"],
        "display_name": generated["display_name"],
        "description": generated["description"],
        "python_code": generated["python_code"],
        "yaml_code": generated["yaml_code"],
        "reasoning": generated.get("reasoning", ""),
        "backtest": backtest_result,
    }


@api_router.post("/ai/chat")
def api_chat(req: ChatRequest):
    """多轮对话式 AI 策略生成与修改。"""
    from autotrade.ai.strategy_generator import StrategyGenerator

    api_key = _get_deepseek_api_key()
    if not api_key:
        return {"error": "未配置 DEEPSEEK_API_KEY 环境变量"}

    # Get or create session
    session = None
    if req.session_id:
        session = _session_store.get_session(req.session_id)
    if session is None:
        title = req.prompt[:50] if len(req.prompt) > 50 else req.prompt
        session = _session_store.create_session(title=title)
        if req.session_id:
            logger.info("Session %s not found, created new: %s", req.session_id, session.session_id)

    session_id = session.session_id

    # Save user message
    user_msg = StoreChatMessage(
        role="user",
        content=req.prompt,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    # Snapshot prior messages BEFORE adding the new one to prevent race
    # conditions when concurrent requests target the same session.
    prior_messages = list(session.messages)
    _session_store.add_message(session_id, user_msg)

    # Build conversation history for AI
    history = []
    for m in prior_messages:
        msg_dict = {"role": m.role, "content": m.content}
        if m.strategy:
            msg_dict["strategy"] = m.strategy
        if m.backtest:
            msg_dict["backtest"] = m.backtest
        history.append(msg_dict)

    # Generate AI response
    gen = StrategyGenerator(api_key=api_key)
    result = gen.chat(history, req.prompt)

    if "error" in result:
        # Save error as assistant message too
        error_msg = StoreChatMessage(
            role="assistant",
            content=result.get("error", "未知错误"),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        _session_store.add_message(session_id, error_msg)
        return ChatResponse(
            session_id=session_id,
            message=ChatMessageResponse(
                role="assistant",
                content=result["error"],
                timestamp=error_msg.timestamp,
            ),
        ).model_dump()

    # Run backtest if strategy was generated/modified
    backtest_result = None
    if result.get("strategy") and result["action"] in ("generate", "modify"):
        strategy_data = result["strategy"]
        s, e = _resolve_dates(req.start, req.end, "1y")
        try:
            strategy_code = strategy_data["python_code"]
            spec = importlib.util.spec_from_loader(
                strategy_data["name"], loader=None, origin="<ai_chat>")
            if spec is None:
                raise RuntimeError("Failed to create module spec")

            module = importlib.util.module_from_spec(spec)
            exec(strategy_code, module.__dict__)

            strat_class = None
            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if (isinstance(obj, type)
                        and hasattr(obj, "generate_signals")
                        and hasattr(obj, "name")
                        and attr_name != "Strategy"):
                    strat_class = obj
                    break

            if strat_class is None:
                raise RuntimeError("未在生成的代码中找到策略类")

            from autotrade.core.engine import _bars_to_dataframe, _make_backtest_config
            from autotrade.core.backtester import Backtester
            from autotrade.core.datasource_factory import build_datasource_from_name

            import yaml
            strategy = None
            try:
                parsed_yaml = yaml.safe_load(strategy_data["yaml_code"])
                yaml_params = parsed_yaml.get("params", {}) if isinstance(parsed_yaml, dict) else {}
                strategy = strat_class(**yaml_params)
            except (TypeError, Exception):
                try:
                    strategy = strat_class()
                except Exception:
                    import inspect
                    sig_params = inspect.signature(strat_class.__init__).parameters
                    accepted = {k: v for k, v in yaml_params.items() if k in sig_params}
                    strategy = strat_class(**accepted) if accepted else strat_class()

            ds = build_datasource_from_name("failover")
            bars = ds.get_bars(req.symbol, s, e)
            if bars:
                df = _bars_to_dataframe(bars)
                for ind in strategy.required_indicators:
                    df = ind.compute(df)

                raw_signals = strategy.generate_signals(df)
                for sig in raw_signals:
                    if not sig.symbol:
                        sig.symbol = req.symbol

                config = _make_backtest_config()
                backtester_obj = Backtester(config)
                bt_result = backtester_obj.run(raw_signals, bars)

                backtest_result = {
                    "symbol": req.symbol,
                    "return_pct": round(bt_result.metrics.get("total_return_pct", 0), 2),
                    "win_rate": round(bt_result.metrics.get("win_rate", 0), 2),
                    "sharpe_ratio": round(bt_result.metrics.get("sharpe_ratio", 0), 4),
                    "max_drawdown_pct": round(bt_result.metrics.get("max_drawdown_pct", 0), 2),
                    "total_trades": len(bt_result.trades),
                }

            # Update session's current strategy
            _session_store.update_strategy(
                session_id,
                strategy_data["python_code"],
                strategy_data["yaml_code"],
            )
        except Exception as ex:
            logger.warning("Failed to backtest in chat: %s", ex)
            backtest_result = {"error": str(ex)}

    # Save assistant message
    assistant_msg = StoreChatMessage(
        role="assistant",
        content=result.get("message", ""),
        timestamp=datetime.now(timezone.utc).isoformat(),
        strategy=result.get("strategy"),
        backtest=backtest_result,
    )
    _session_store.add_message(session_id, assistant_msg)

    return ChatResponse(
        session_id=session_id,
        message=ChatMessageResponse(
            role="assistant",
            content=result.get("message", ""),
            timestamp=assistant_msg.timestamp,
            strategy=result.get("strategy"),
            backtest=backtest_result,
        ),
        strategy=result.get("strategy"),
        backtest=backtest_result,
    ).model_dump()


@api_router.get("/ai/chat/{session_id}")
def api_get_chat(session_id: str):
    """获取会话完整历史。"""
    session = _session_store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = []
    for m in session.messages:
        messages.append(ChatMessageResponse(
            role=m.role,
            content=m.content,
            timestamp=m.timestamp,
            strategy=m.strategy,
            backtest=m.backtest,
        ))

    return ChatHistoryResponse(
        session={
            "session_id": session.session_id,
            "title": session.title,
            "created_at": session.created_at,
            "last_active": session.last_active,
            "message_count": len(session.messages),
        },
        messages=messages,
    ).model_dump()


@api_router.delete("/ai/chat/{session_id}")
def api_delete_chat(session_id: str):
    """删除会话。"""
    deleted = _session_store.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}


@api_router.post("/strategies/save")
def api_save_strategy(req: SaveStrategyRequest):
    """保存 AI 生成的策略到文件系统。"""
    from autotrade.ai.strategy_generator import StrategyGenerator
    from autotrade.registry import init_registry as reload_registry

    if is_builtin_strategy(req.name):
        return {"error": f"不能覆盖内置策略: {req.name}"}

    py_path = Path(__file__).resolve().parent.parent / "strategies" / f"{req.name}.py"
    yaml_path = Path(__file__).resolve().parent.parent.parent / "config" / "strategies" / f"{req.name}.yaml"

    if py_path.exists() or yaml_path.exists():
        return {"error": f"策略 {req.name} 已存在，请先删除或使用不同名称"}

    py_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.parent.mkdir(parents=True, exist_ok=True)

    with open(py_path, "w", encoding="utf-8") as f:
        f.write(req.python_code)
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(req.yaml_code)

    reload_registry(force=True)

    return {
        "success": True,
        "name": req.name,
        "python_path": str(py_path),
        "yaml_path": str(yaml_path),
    }


@api_router.delete("/strategies/{name}")
def api_delete_strategy(name: str):
    """删除 AI 生成的策略。内置策略不可删除。"""
    from autotrade.ai.strategy_generator import StrategyGenerator
    from autotrade.registry import init_registry as reload_registry

    if is_builtin_strategy(name):
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

    reload_registry(force=True)

    return {"success": True, "name": name, "deleted": deleted}


@api_router.get("/strategies")
def api_list_strategies():
    """列出可用策略及其参数信息。"""
    from autotrade.core.config import get_strategy_params
    from autotrade.registry import get_strategy
    import inspect

    result = []
    for name in list_strategies():
        info: dict = {"name": name, "params": {}, "is_builtin": is_builtin_strategy(name)}
        # 加载 YAML 配置的当前参数值
        yaml_cfg = get_strategy_params(name)
        if yaml_cfg and "params" in yaml_cfg:
            info["params"] = yaml_cfg["params"]

        # 从策略类的构造函数提取参数 schema（名称 + 默认值）
        try:
            strategy_cls = get_strategy(name)
            sig = inspect.signature(strategy_cls.__init__)
            param_schema = {}
            for pname, p in sig.parameters.items():
                if pname in ("self", "args", "kwargs"):
                    continue
                entry: dict = {}
                if p.default is not inspect.Parameter.empty:
                    entry["default"] = p.default
                # 推断类型
                if p.annotation is not inspect.Parameter.empty:
                    ann = p.annotation
                    type_str = _annotation_to_type_str(ann)
                    if type_str:
                        entry["type"] = type_str
                elif p.default is not inspect.Parameter.empty:
                    entry["type"] = _python_type_to_str(type(p.default))
                param_schema[pname] = entry
            info["param_schema"] = param_schema
        except Exception:
            pass

        result.append(info)

    return {"strategies": result}


def _annotation_to_type_str(ann) -> str | None:
    """将类型注解转为前端友好的类型字符串。"""
    import typing
    # 处理字符串注解（from __future__ import annotations 导致）
    if isinstance(ann, str):
        ann_lower = ann.lower()
        if ann_lower in ("int", "float", "bool", "str", "list", "dict"):
            return ann_lower
        if ann_lower.startswith("list"):
            return "list"
        if ann_lower.startswith("dict"):
            return "dict"
        return "str"
    origin = typing.get_origin(ann)
    if origin is list:
        return "list"
    if origin is dict:
        return "dict"
    if isinstance(ann, type):
        return _python_type_to_str(ann)
    return None


def _python_type_to_str(t: type) -> str:
    if t is int:
        return "int"
    if t is float:
        return "float"
    if t is bool:
        return "bool"
    if t is str:
        return "str"
    if t is list:
        return "list"
    if t is dict:
        return "dict"
    return "str"


@api_router.get("/datasources")
def api_list_datasources_api():
    """列出可用数据源。"""
    return {"datasources": list_datasources()}


@api_router.get("/groups")
def api_list_groups():
    """列出股票分组。"""
    from pathlib import Path
    from autotrade.triggers.cli import _load_yaml, _extract_symbols

    groups_dir = Path(__file__).resolve().parent.parent.parent / "config" / "groups"
    result = []
    if groups_dir.exists():
        for f in sorted(groups_dir.glob("*.yaml")):
            cfg = _load_yaml(f)
            syms = _extract_symbols(cfg)
            result.append({
                "id": f.stem,
                "name": cfg.get("name", f.stem),
                "symbols": [{"code": c, "name": n} for c, n in syms],
                "is_builtin": is_builtin_group(f.stem),
            })
    return {"groups": result}


# ---- 分组 CRUD ----

class GroupSymbol(BaseModel):
    code: str
    name: str = ""


class GroupCreate(BaseModel):
    id: str
    name: Optional[str] = None
    symbols: list[GroupSymbol] = []


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    symbols: Optional[list[GroupSymbol]] = None


def _groups_dir():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent.parent / "config" / "groups"


def _group_path(group_id: str):
    return _groups_dir() / f"{group_id}.yaml"


def _read_group(group_id: str) -> dict | None:
    from autotrade.triggers.cli import _load_yaml
    path = _group_path(group_id)
    if not path.exists():
        return None
    cfg = _load_yaml(path)
    from autotrade.triggers.cli import _extract_symbols
    syms = _extract_symbols(cfg)
    return {
        "id": group_id,
        "name": cfg.get("name", group_id),
        "symbols": [{"code": c, "name": n} for c, n in syms],
        "is_builtin": is_builtin_group(group_id),
    }


def _write_group(group_id: str, name: str, symbols: list[GroupSymbol]):
    import yaml
    _groups_dir().mkdir(parents=True, exist_ok=True)
    data = {
        "name": name,
        "symbols": {s.code: s.name for s in symbols},
    }
    with open(_group_path(group_id), "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


@api_router.get("/groups/{group_id}")
def api_get_group(group_id: str):
    """获取单个分组详情。"""
    g = _read_group(group_id)
    if g is None:
        return {"error": f"分组不存在: {group_id}"}
    return g


@api_router.post("/groups")
def api_create_group(req: GroupCreate):
    """创建股票分组。"""
    path = _group_path(req.id)
    if path.exists():
        return {"error": f"分组已存在: {req.id}"}
    name = req.name or req.id
    _write_group(req.id, name, req.symbols)
    return _read_group(req.id)


@api_router.put("/groups/{group_id}")
def api_update_group(group_id: str, req: GroupUpdate):
    """更新股票分组。"""
    if is_builtin_group(group_id):
        return {"error": "系统内置分组不可修改"}
    g = _read_group(group_id)
    if g is None:
        return {"error": f"分组不存在: {group_id}"}
    name = req.name or g["name"]
    syms = req.symbols or [GroupSymbol(code=s["code"], name=s["name"]) for s in g["symbols"]]
    _write_group(group_id, name, syms)
    return _read_group(group_id)


@api_router.delete("/groups/{group_id}")
def api_delete_group(group_id: str):
    """删除股票分组。"""
    if is_builtin_group(group_id):
        return {"error": "系统内置分组不可删除"}
    path = _group_path(group_id)
    if not path.exists():
        return {"error": f"分组不存在: {group_id}"}
    path.unlink()
    return {"ok": True, "deleted": group_id}


# ---- 日线数据查询 ----

class BarsRequest(BaseModel):
    symbol: str
    start: Optional[str] = None
    end: Optional[str] = None
    period: Optional[str] = "1y"


@api_router.post("/bars")
def api_get_bars(req: BarsRequest):
    """查询日线数据 (OHLCV)。"""
    from autotrade.core.datasource_factory import build_datasource_from_name

    s, e = _resolve_dates(req.start, req.end, req.period)
    ds = build_datasource_from_name("failover")
    bars = ds.get_bars(req.symbol, s, e)

    if not bars:
        return {"symbol": req.symbol, "stock_name": "", "count": 0, "bars": [], "error": "No data"}

    name_map = _build_stock_name_map()
    return {
        "symbol": req.symbol,
        "stock_name": name_map.get(req.symbol, ""),
        "count": len(bars),
        "start": str(s),
        "end": str(e),
        "bars": [
            {
                "date": str(b.date),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
                "amount": b.amount,
            }
            for b in bars
        ],
    }


@api_router.get("/health")
def health():
    return {"status": "ok"}


# ---- 工具函数 ----

def _resolve_dates(start_str, end_str, period_str):
    """解析日期：显式日期 > period > 默认1年。"""
    from autotrade.triggers.cli import _parse_date, _parse_period

    s = _parse_date(start_str)
    e = _parse_date(end_str)
    if s is None and e is None:
        s, e = _parse_period(period_str or "1y")
    if e is None:
        e = date.today()
    if s is None:
        s = date(e.year - 1, e.month, e.day)
    return s, e


def _format_result(result, symbol: str) -> dict:
    """把 BacktestResult 转成 JSON 友好的 dict，附带运行现金/持仓/原因。"""
    # 信号日期→原因映射
    signal_reasons: dict[str, list[str]] = {}
    for s in result.signals:
        key = f"{s.date}_{s.action}"
        signal_reasons.setdefault(key, []).append(s.reason)

    initial_capital = result.metrics.get("initial_capital", 0)
    cash = initial_capital
    position = 0
    trades_json = []

    for t in result.trades:
        if t.action == "BUY":
            position += t.quantity
            cash -= t.price * t.quantity + t.commission
        else:
            position -= t.quantity
            cash += t.price * t.quantity - t.commission - t.stamp_duty

        total_equity = cash + position * t.price

        key = f"{t.date}_{t.action}"
        reasons = signal_reasons.get(key, [])
        reason = reasons.pop(0) if reasons else ""

        trades_json.append({
            "date": str(t.date),
            "action": t.action,                       # BUY / SELL
            "price": t.price,                         # 成交价
            "quantity": t.quantity,                   # 成交数量（股）
            "commission": t.commission,               # 佣金
            "stamp_duty": t.stamp_duty,               # 印花税
            "position": position,                     # 交易后持仓（股）
            "cash": round(cash, 2),                   # 交易后现金
            "total_equity": round(total_equity, 2),   # 交易后总资产
            "reason": reason,                         # 触发原因
        })

    # 净值曲线（可选，数据量大时前端可选择性请求）
    equity_points = None
    if result.equity_curve is not None:
        import pandas as pd
        ec = result.equity_curve
        cl = result.close_prices  # 收盘价序列
        try:
            if isinstance(ec.index, pd.DatetimeIndex):
                equity_points = []
                for i, (d, v) in enumerate(zip(ec.index, ec.values)):
                    pt = {"date": str(d.date()), "equity": round(float(v), 2)}
                    if cl is not None and i < len(cl):
                        pt["close"] = round(float(cl.iloc[i]), 2)
                    equity_points.append(pt)
            else:
                equity_points = []
                for i, (d, v) in enumerate(zip(ec.index, ec.values)):
                    pt = {"date": str(d) if hasattr(d, 'isoformat') else str(d),
                          "equity": round(float(v), 2)}
                    if cl is not None and i < len(cl):
                        pt["close"] = round(float(cl.iloc[i]), 2)
                    equity_points.append(pt)
        except Exception:
            equity_points = None

    return {
        "symbol": symbol,
        "stock_name": result.stock_name,
        "metrics": result.metrics,
        "trades": trades_json,
        "signal_count": len(result.signals),
        "equity_curve": equity_points,
    }


# ---- 本地缓存 ----

# 项目根目录
_ROOT = Path(__file__).resolve().parent.parent.parent
_STOCK_LIST_CSV = _ROOT / "data" / "a_stock_list.csv"
_METADATA_CACHE = _ROOT / "data" / "cache" / "stocks_metadata.json"
_DAILY_DIR = _ROOT / "data" / "daily"

# 模块级名称映射缓存
_name_map_cache: dict[str, str] | None = None


def _build_stock_name_map(force_reload: bool = False) -> dict[str, str]:
    """构建代码→名称映射。
    
    优先从 data/a_stock_list.csv 加载全量 A 股名称，
    然后以 config/groups/*.yaml 中的自定义名称覆盖。
    结果缓存在模块级变量中。
    """
    global _name_map_cache
    if _name_map_cache is not None and not force_reload:
        return _name_map_cache

    name_map: dict[str, str] = {}

    # ① 从全量 A 股列表 CSV 加载 (code,name,board)
    if _STOCK_LIST_CSV.exists():
        try:
            import csv
            with open(_STOCK_LIST_CSV, "r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    code = row.get("code", "").strip()
                    name = row.get("name", "").strip()
                    if code and name:
                        name_map[code] = name
        except Exception:
            pass

    # ② 从分组 YAML 配置中补充/覆盖（分组中的名称可能更精确）
    try:
        from autotrade.triggers.cli import _load_yaml, _extract_symbols
        groups_dir = _ROOT / "config" / "groups"
        if groups_dir.exists():
            for f in groups_dir.glob("*.yaml"):
                try:
                    cfg = _load_yaml(f)
                    syms = _extract_symbols(cfg)
                    for code, name in syms:
                        if name:
                            name_map[code] = name  # 覆盖 CSV 中的名称
                except Exception:
                    pass
    except Exception:
        pass

    _name_map_cache = name_map
    return name_map


def _build_stocks_metadata_cache(force_rebuild: bool = False) -> list[dict]:
    """构建/读取缓存股票的元数据。

    首次调用时扫描 data/daily/*.parquet，仅读取 date / close 两列
    以提取摘要信息，结果持久化到 data/cache/stocks_metadata.json。
    后续调用直接读取 JSON 缓存，速度极快。

    参数:
        force_rebuild: True 时强制重新扫描 parquet 文件。
    返回:
        元数据列表，每项包含 symbol, name, bars, start, end, last_close。
    """
    import json

    # 确保缓存目录存在
    _METADATA_CACHE.parent.mkdir(parents=True, exist_ok=True)

    # 如果不强制重建且缓存文件存在，直接读取
    if not force_rebuild and _METADATA_CACHE.exists():
        try:
            with open(_METADATA_CACHE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass  # 缓存损坏 → 重建

    # ---- 扫描 parquet 文件，构建元数据 ----
    name_map = _build_stock_name_map()
    result: list[dict] = []

    if not _DAILY_DIR.exists():
        return result

    import pandas as pd

    for f in sorted(_DAILY_DIR.glob("*.parquet")):
        symbol = f.stem
        try:
            # 仅读取 date 和 close 两列，大幅加速
            df = pd.read_parquet(f, columns=["date", "close"])
            if df.empty:
                result.append({"symbol": symbol, "name": name_map.get(symbol, ""),
                               "bars": 0, "start": None, "end": None, "last_close": None})
            else:
                latest = df.iloc[-1]
                result.append({
                    "symbol": symbol,
                    "name": name_map.get(symbol, ""),
                    "bars": len(df),
                    "start": str(df["date"].min().date()),
                    "end": str(df["date"].max().date()),
                    "last_close": float(latest["close"]) if pd.notna(latest["close"]) else None,
                })
        except Exception:
            result.append({"symbol": symbol, "name": name_map.get(symbol, ""),
                           "bars": 0, "start": None, "end": None, "last_close": None})

    # 写入 JSON 缓存
    try:
        with open(_METADATA_CACHE, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False)
    except Exception:
        pass

    return result


@api_router.get("/cache/stocks")
def api_cache_stocks(
    page: int = Query(0, ge=0, description="页码（0=不分页，返回全部）"),
    size: int = Query(50, ge=1, le=500, description="每页条数"),
    keyword: str = Query("", description="按代码或名称模糊搜索"),
    refresh: bool = Query(False, description="强制重建元数据缓存"),
):
    """列出本地已缓存的股票代码及最新数据摘要（含名称）。

    **查询参数**:
    - `page`: 页码，0 表示返回全部（向后兼容默认行为）
    - `size`: 每页条数，默认 50，最大 500
    - `keyword`: 模糊匹配股票代码或名称
    - `refresh`: 设为 true 时强制重新扫描 parquet 文件重建缓存

    **响应**:
    ```json
    {
      "symbols": [...],
      "total": 5216,
      "page": 1,
      "size": 50,
      "pages": 105
    }
    ```
    当 `page=0` 时，不返回分页字段（向后兼容）。
    """
    # 加载元数据（优先从 JSON 缓存读取）
    all_stocks = _build_stocks_metadata_cache(force_rebuild=refresh)

    # ---- 关键词过滤 ----
    if keyword:
        kw = keyword.strip().lower()
        all_stocks = [
            s for s in all_stocks
            if kw in s["symbol"].lower() or kw in (s.get("name", "") or "").lower()
        ]

    total = len(all_stocks)

    # ---- 分页 ----
    if page > 0:
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        page_items = all_stocks[start_idx:end_idx]
        return {
            "symbols": page_items,
            "total": total,
            "page": page,
            "size": size,
            "pages": max(1, (total + size - 1) // size),
        }
    else:
        # 向后兼容：page=0（默认）返回全部
        return {"symbols": all_stocks}
# 注意：必须在所有 API 路由之后注册，否则会拦截 API 请求

# 前端策略：React 构建的 SPA（完整应用）优先，旧前端作为备用
_frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
_react_dir = Path(__file__).resolve().parent.parent.parent / "web" / "dist"

if _react_dir.exists():
    from fastapi.responses import FileResponse, Response
    import mimetypes

    # React SPA 静态资源（JS/CSS/图片等）
    @app.get("/assets/{rest:path}")
    async def serve_react_assets(rest: str):
        requested = _react_dir / "assets" / rest
        if requested.exists() and requested.is_file():
            mt, _ = mimetypes.guess_type(str(requested))
            return FileResponse(requested, media_type=mt or "application/octet-stream")
        return Response(status_code=404)

    # React SPA catch-all：所有非 API 路径返回 index.html
    @app.get("/{rest:path}")
    async def serve_react_spa(rest: str):
        # Try serving a static file from dist first
        requested = _react_dir / rest
        if requested.exists() and requested.is_file():
            mt, _ = mimetypes.guess_type(str(requested))
            return FileResponse(requested, media_type=mt or "application/octet-stream")
        # Otherwise return index.html for SPA routing
        return FileResponse(_react_dir / "index.html")

    @app.get("/")
    async def serve_react_root():
        return FileResponse(_react_dir / "index.html")

elif _frontend_dir.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
