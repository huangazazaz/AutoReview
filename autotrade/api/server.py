"""AutoTrade Web API —— FastAPI 服务器。

启动: autotrade-api  或  uvicorn autotrade.api.server:app

端点:
  POST /analyze           单股回测
  POST /backtest          多股/分组回测
  POST /bars              日线数据查询
  GET  /strategies        策略列表
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
from datetime import date
from typing import Optional

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from autotrade.core.engine import analyze_stock, run_backtest
from autotrade.registry import (
    init_registry, list_datasources, list_strategies,
)

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


# ---- 启动事件 ----

@app.on_event("startup")
def _startup():
    init_registry()


# ---- API 端点 ----

@app.post("/analyze")
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


@app.post("/backtest")
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


@app.get("/strategies")
def api_list_strategies():
    """列出可用策略及其参数信息。"""
    from autotrade.core.config import get_strategy_params
    from autotrade.registry import get_strategy
    import inspect

    result = []
    for name in list_strategies():
        info: dict = {"name": name, "params": {}}
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


@app.get("/datasources")
def api_list_datasources_api():
    """列出可用数据源。"""
    return {"datasources": list_datasources()}


@app.get("/groups")
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


@app.get("/groups/{group_id}")
def api_get_group(group_id: str):
    """获取单个分组详情。"""
    g = _read_group(group_id)
    if g is None:
        return {"error": f"分组不存在: {group_id}"}
    return g


@app.post("/groups")
def api_create_group(req: GroupCreate):
    """创建股票分组。"""
    path = _group_path(req.id)
    if path.exists():
        return {"error": f"分组已存在: {req.id}"}
    name = req.name or req.id
    _write_group(req.id, name, req.symbols)
    return _read_group(req.id)


@app.put("/groups/{group_id}")
def api_update_group(group_id: str, req: GroupUpdate):
    """更新股票分组。"""
    g = _read_group(group_id)
    if g is None:
        return {"error": f"分组不存在: {group_id}"}
    name = req.name or g["name"]
    syms = req.symbols or [GroupSymbol(code=s["code"], name=s["name"]) for s in g["symbols"]]
    _write_group(group_id, name, syms)
    return _read_group(group_id)


@app.delete("/groups/{group_id}")
def api_delete_group(group_id: str):
    """删除股票分组。"""
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


@app.post("/bars")
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


@app.get("/health")
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
        # 提取日期和净值：兼容 DatetimeIndex 和普通 date 对象索引
        try:
            if isinstance(ec.index, pd.DatetimeIndex):
                equity_points = [
                    {"date": str(d.date()), "equity": round(float(v), 2)}
                    for d, v in zip(ec.index, ec.values)
                ]
            else:
                equity_points = [
                    {"date": str(d) if hasattr(d, 'isoformat') else str(d),
                     "equity": round(float(v), 2)}
                    for d, v in zip(ec.index, ec.values)
                ]
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

def _build_stock_name_map() -> dict[str, str]:
    """从所有分组配置中提取代码→名称映射。"""
    from pathlib import Path
    from autotrade.triggers.cli import _load_yaml, _extract_symbols
    groups_dir = Path(__file__).resolve().parent.parent.parent / "config" / "groups"
    name_map: dict[str, str] = {}
    if groups_dir.exists():
        for f in groups_dir.glob("*.yaml"):
            try:
                cfg = _load_yaml(f)
                syms = _extract_symbols(cfg)
                for code, name in syms:
                    if name and code not in name_map:
                        name_map[code] = name
            except Exception:
                pass
    return name_map


@app.get("/cache/stocks")
def api_cache_stocks():
    """列出本地已缓存的股票代码及最新数据摘要（含名称）。"""
    from pathlib import Path
    data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "daily"
    if not data_dir.exists():
        return {"symbols": []}

    name_map = _build_stock_name_map()
    result = []
    for f in sorted(data_dir.glob("*.parquet")):
        symbol = f.stem
        try:
            import pandas as pd
            df = pd.read_parquet(f)
            latest = df.iloc[-1] if not df.empty else None
            result.append({
                "symbol": symbol,
                "name": name_map.get(symbol, ""),
                "bars": len(df),
                "start": str(df["date"].min().date()) if "date" in df.columns and not df.empty else None,
                "end": str(df["date"].max().date()) if "date" in df.columns and not df.empty else None,
                "last_close": float(latest["close"]) if latest is not None and "close" in latest else None,
            })
        except Exception:
            result.append({"symbol": symbol, "name": name_map.get(symbol, ""), "bars": 0})

    return {"symbols": result}
# 注意：必须在所有 API 路由之后注册，否则会拦截 API 请求

_frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend" 
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
