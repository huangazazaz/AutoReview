# Stock Screener Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a stock screener page where users pick a screener + strategy + date, scan the entire market, and see ranked candidates with buy signals and factor breakdowns.

**Architecture:** New `POST /api/screen` and `GET /api/screeners` endpoints; new `run_screen()` function in `engine.py` orchestrating Screener → Strategy → factor breakdown; new `ScreenerParamsEditor` and `Screener.tsx` frontend page following existing backtest/portfolio patterns.

**Tech Stack:** Python 3.10+ / FastAPI / pandas / React 18 / TypeScript / ECharts

## Global Constraints

- Follow existing code patterns (API endpoints, engine functions, frontend pages)
- No auth dependency on new API endpoints (match existing api_router pattern)
- Screener names use `_screener` suffix: `momentum_screener`, `hot_money_screener`
- Frontend uses lazy-loaded page components via `React.lazy`
- TypeScript types go in `web/src/types/index.ts`
- API client methods go in `web/src/api/client.ts`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `autotrade/core/models.py` | Modify | Add `ScreenResult` dataclass |
| `autotrade/core/interfaces.py` | Modify | Add `Screener.explain()` optional method |
| `autotrade/core/engine.py` | Modify | Add `run_screen()` function |
| `autotrade/screens/momentum.py` | Modify | Implement `explain()` |
| `autotrade/screens/hot_money.py` | Modify | Implement `explain()` |
| `autotrade/api/server.py` | Modify | Add `GET /api/screeners` and `POST /api/screen` |
| `web/src/types/index.ts` | Modify | Add `Screen*` types + `ScreenerInfo` |
| `web/src/api/client.ts` | Modify | Add `getScreeners()` and `screen()` |
| `web/src/components/ScreenerParamsEditor.tsx` | **Create** | Dynamic params form for screeners |
| `web/src/pages/Screener.tsx` | **Create** | Main screener page component |
| `web/src/App.tsx` | Modify | Add `/screener` route |
| `web/src/components/Sidebar.tsx` | Modify | Add "选股" nav item |

---

### Task 1: Add `ScreenResult` Data Model

**Files:**
- Modify: `autotrade/core/models.py` (append at end)

**Interfaces:**
- Produces: `ScreenResult`, `ScreenItem`, `BuySignalInfo` dataclasses used by Task 2 and Task 5

- [ ] **Step 1: Add dataclasses to models.py**

```python
@dataclass
class ScreenItem:
    """单只股票的选股结果。"""
    symbol: str
    name: str = ""
    score: float = 0.0
    signal_tag: str = ""
    factor_breakdown: dict = field(default_factory=dict)        # {因子名: 得分}
    buy_signal: Optional[dict] = None                            # {"date": str, "action": str, "strength": float, "reason": str}
    key_metrics: dict = field(default_factory=dict)              # {"close": ..., "volume": ..., ...}


@dataclass
class ScreenResult:
    """选股扫描完整结果。"""
    date: str = ""
    screener: str = ""
    strategy: str = ""
    universe_size: int = 0
    candidates: int = 0
    with_buy_signal: int = 0
    results: list[ScreenItem] = field(default_factory=list)
```

Note: `ScreenItem` and `ScreenResult` are added right after the existing `BacktestResult` class (after line 99). The `Optional` and `field` imports already exist in models.py.

- [ ] **Step 2: Verify models import cleanly**

Run: `python -c "from autotrade.core.models import ScreenResult, ScreenItem; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add autotrade/core/models.py
git commit -m "feat: add ScreenResult and ScreenItem dataclasses for screener API"
```

---

### Task 2: Add `explain()` to Screener Interface

**Files:**
- Modify: `autotrade/core/interfaces.py` (add method to Screener class)
- Modify: `autotrade/screens/momentum.py` (implement `explain()`)
- Modify: `autotrade/screens/hot_money.py` (implement `explain()`)

**Interfaces:**
- Consumes: `ScreenItem` from Task 1 (for reference only, not code dependency)
- Produces: `Screener.explain(market_data, symbol, date) -> dict[str, float]` — used by Task 4

- [ ] **Step 1: Add `explain()` to Screener base class in interfaces.py**

Open `autotrade/core/interfaces.py` at line 88 (end of `Screener` class, after the `scan()` abstractmethod docstring). Add this method inside the class, after `scan()`:

```python
    def explain(self, market_data: dict[str, pd.DataFrame],
                symbol: str, date: date) -> dict[str, float]:
        """返回指定股票在指定日期的因子明细得分。

        子类可选实现，默认返回空字典。

        Args:
            market_data: {symbol: OHLCV DataFrame}
            symbol: 目标股票代码
            date: 目标日期

        Returns:
            {因子中文名: 得分(0.0~1.0)}
        """
        return {}
```

- [ ] **Step 2: Verify interface change**

Run: `python -c "from autotrade.core.interfaces import Screener; print(hasattr(Screener, 'explain'))"`  
Expected: `True`

- [ ] **Step 3: Implement `explain()` in MomentumScreener**

Open `autotrade/screens/momentum.py`. Add this method inside the `MomentumScreener` class (e.g., after the `scan()` method at line 116, before `_passes_prefilter`):

```python
    def explain(
        self, market_data: dict[str, pd.DataFrame],
        symbol: str, date: date,
    ) -> dict[str, float]:
        """返回动量选股的7因子明细得分。"""
        df = market_data.get(symbol)
        if df is None:
            return {}
        idx = self._index_of(df, date)
        if idx is None or idx < self.exclude_min_history_days:
            return {}

        factors: dict[str, float] = {}

        v = self._calc_momentum_1m(df, idx)
        factors["动量强度"] = round(self._score_s_curve(v, center=0.15, k=15, floor=0.0, ceil=1.0), 4) if v is not None else 0.0

        v = self._calc_momentum_5d(df, idx)
        factors["短期回调"] = round(self._score_s_curve(v, center=-0.02, k=20, floor=0.0, ceil=1.0, reverse=True), 4) if v is not None else 0.0

        v = self._calc_vol_ratio(df, idx)
        factors["量能确认"] = round(self._score_peak(v, peak=1.5, width=1.0, floor=0.0), 4) if v is not None else 0.0

        factors["均线排列"] = round(self._calc_ma_score(df, idx), 4)

        v = self._calc_pullback(df, idx)
        factors["回调距离"] = round(self._score_peak(v, peak=0.02, width=0.04, floor=0.0), 4) if v is not None else 0.0

        v = self._calc_atr_ratio(df, idx)
        factors["波动率"] = round(self._score_peak(v, peak=0.035, width=0.02, floor=0.0), 4) if v is not None else 0.0

        v = self._calc_consistency(df, idx)
        factors["一致性"] = round(self._score_peak(v, peak=0.65, width=0.15, floor=0.0), 4) if v is not None else 0.0

        return factors
```

- [ ] **Step 4: Implement `explain()` in HotMoneyScreener**

Open `autotrade/screens/hot_money.py`. Add this method inside the `HotMoneyScreener` class (after `scan()` at line 153, before `_evaluate`):

```python
    def explain(
        self, market_data: dict[str, pd.DataFrame],
        symbol: str, date: date,
    ) -> dict[str, float]:
        """返回热钱选股的因子明细得分。"""
        df = market_data.get(symbol)
        if df is None:
            return {}
        idx = self._index_of(df, date)
        if idx is None or idx < self.exclude_min_history_days:
            return {}
        if not self._passes_prefilter(df, idx):
            return {}

        factors: dict[str, float] = {}

        # 趋势强度: MA20 / MA60 的比值映射到 0-1
        ma_f = float(df["_ma_fast"].iloc[idx])
        ma_m = float(df["_ma_mid"].iloc[idx])
        if not pd.isna(ma_f) and not pd.isna(ma_m) and ma_m > 0:
            trend = min((ma_f / ma_m - 1) * 5, 1.0)
            factors["趋势强度"] = round(max(trend, 0.0), 4)
        else:
            factors["趋势强度"] = 0.0

        # 动量得分: 60日涨幅映射
        if "_mom_ret" in df.columns:
            mr = float(df["_mom_ret"].iloc[idx])
            if not pd.isna(mr):
                momentum = min(max(mr, 0.05), 0.40) / 0.35
                factors["动量得分"] = round(momentum, 4)
            else:
                factors["动量得分"] = 0.0
        else:
            factors["动量得分"] = 0.0

        # 当日量比
        v = float(df["volume"].iloc[idx])
        vol_ma = float(df["volume"].iloc[max(0, idx - 20):idx].mean()) if idx > 0 else 0
        if vol_ma > 0:
            vol_ratio = v / vol_ma
            factors["量能得分"] = round(min(vol_ratio / 3.0, 1.0), 4)
        else:
            factors["量能得分"] = 0.0

        # 当日涨幅
        c = float(df["close"].iloc[idx])
        c_prev = float(df["close"].iloc[idx - 1])
        if c_prev > 0:
            gain = (c - c_prev) / c_prev
            factors["涨幅得分"] = round(min(max(gain, 0.0) / 0.05, 1.0), 4)
        else:
            factors["涨幅得分"] = 0.0

        # 突破力度（收盘价 vs 10日最高价）
        if idx >= 10:
            recent_high = float(df["high"].iloc[idx - 10:idx].max())
            if recent_high > 0 and c > recent_high:
                break_str = (c - recent_high) / recent_high
                factors["突破力度"] = round(min(break_str * 10, 1.0), 4)
            else:
                factors["突破力度"] = 0.0
        else:
            factors["突破力度"] = 0.0

        return factors
```

- [ ] **Step 5: Verify screeners still work**

Run: `python -c "from autotrade.screens.momentum import MomentumScreener; from autotrade.screens.hot_money import HotMoneyScreener; m = MomentumScreener(); print(m.explain({}, '600522', __import__('datetime').date.today())); h = HotMoneyScreener(); print(h.explain({}, '600522', __import__('datetime').date.today()))"`  
Expected: both print `{}` (empty dicts since market_data is empty)

- [ ] **Step 6: Commit**

```bash
git add autotrade/core/interfaces.py autotrade/screens/momentum.py autotrade/screens/hot_money.py
git commit -m "feat: add explain() method to Screener interface and both screeners"
```

---

### Task 3: Add `run_screen()` to Engine

**Files:**
- Modify: `autotrade/core/engine.py` (add function after `run_screener_backtest`)

**Interfaces:**
- Consumes: `ScreenResult`, `ScreenItem` from Task 1; `Screener.explain()` from Task 2
- Produces: `run_screen(screener_name, strategy_name, target_date, top_n, screener_params, strategy_params) -> ScreenResult` — used by Task 5

- [ ] **Step 1: Add `run_screen()` function**

Open `autotrade/core/engine.py`. Add this function after `run_screener_backtest()` (after line 508, before `# ---- 组合回测 ----`):

```python
# ---- 单日选股 ----

def run_screen(
    screener_name: str,
    strategy_name: str,
    target_date: date,
    top_n: int = 20,
    screener_params: dict[str, Any] | None = None,
    strategy_params: dict[str, Any] | None = None,
    datasource_name: str = FAILOVER_NAME,
) -> ScreenResult:
    """单日选股扫描：Screener 初筛 → Strategy 确认买点 → 因子明细。

    流程:
      1. 加载全市场 OHLCV（回溯窗口由 screener+strategy 所需最大天数决定）
      2. Screener.scan() → 候选列表
      3. 对每只候选跑 Strategy.generate_signals() → 筛选有 BUY 的
      4. Screener.explain() → 因子明细
      5. 提取关键指标 → 排序返回

    Args:
        screener_name: 选股器名称（如 "momentum_screener"）
        strategy_name: 交易策略名称（如 "ma_cross"）
        target_date: 目标日期
        top_n: 返回前 N 只
        screener_params: 选股器参数覆盖
        strategy_params: 策略参数覆盖
        datasource_name: 数据源名称

    Returns:
        ScreenResult 包含候选列表、买点信息和因子明细。
    """
    from autotrade.core.models import ScreenResult, ScreenItem

    init_registry()

    # ---- 1. 确定回溯窗口 ----
    # 默认 120 天，覆盖 screener 和 strategy 所需的最大 lookback
    lookback_days = 120
    start = target_date - pd.Timedelta(days=lookback_days * 2)  # 留足余量
    end = target_date

    # ---- 2. 加载全市场数据 ----
    ds = build_datasource_from_name(datasource_name)
    all_symbols = ds.list_symbols()

    # 排除 ST
    st_exclude = _load_st_exclusion_set()
    if st_exclude:
        all_symbols = [s for s in all_symbols if s not in st_exclude]
        logger.info("排除 ST 后剩余 %d 只", len(all_symbols))

    market_data = _load_market_data(all_symbols, start, end)
    if not market_data:
        return ScreenResult(date=str(target_date), screener=screener_name,
                            strategy=strategy_name, universe_size=0)

    # ---- 3. 运行 Screener ----
    s_params = screener_params
    if s_params is None:
        s_params = _load_screener_params(screener_name)
    screener_cls = get_screener(screener_name)
    screener = screener_cls(**s_params)
    selection = screener.scan(market_data, [target_date])

    candidates = selection.get(target_date, [])
    logger.info("Screener '%s' 在 %s 选出 %d 只候选",
                screener_name, target_date, len(candidates))

    if not candidates:
        return ScreenResult(date=str(target_date), screener=screener_name,
                            strategy=strategy_name, universe_size=len(market_data),
                            candidates=0)

    # ---- 4. 运行 Strategy 确认买点 ----
    t_params = strategy_params
    if t_params is None:
        t_params = get_strategy_params(strategy_name).get("params", {}) or {}
    strategy_cls = get_strategy(strategy_name)
    strategy = strategy_cls(**t_params)

    # 计算指标列
    for indicator in strategy.required_indicators:
        for sym in [s for s, _, _ in candidates]:
            df = market_data.get(sym)
            if df is not None:
                try:
                    indicator.compute(df)
                except Exception:
                    pass

    # ---- 5. 构建结果列表 ----
    results: list[ScreenItem] = []
    name_map = _build_stock_name_map_safe()

    for sym, score, tag in candidates:
        df = market_data.get(sym)
        if df is None:
            continue

        # 提取关键指标
        idx = _screener_index_of(df, target_date)
        if idx is None:
            continue

        key_metrics: dict[str, Any] = {}
        try:
            key_metrics["close"] = round(float(df["close"].iloc[idx]), 2)
            key_metrics["volume"] = int(df["volume"].iloc[idx])
            key_metrics["amount"] = round(float(df.get("amount", pd.Series([0])).iloc[idx]), 0)
            # 提取 MA 列（如果存在）
            for col in df.columns:
                if col.startswith("ind_ma_") or col.startswith("_ma_"):
                    val = float(df[col].iloc[idx])
                    if not pd.isna(val):
                        label = col.replace("ind_ma_", "ma_").replace("_ma_", "ma_")
                        key_metrics[label] = round(val, 2)
        except Exception:
            pass

        # 买点确认
        buy_signal = None
        try:
            signals = strategy.generate_signals(df)
            for sig in signals:
                sig_date = sig.date.date() if hasattr(sig.date, "date") else sig.date
                if sig_date == target_date and sig.action == "BUY":
                    buy_signal = {
                        "date": str(sig_date),
                        "action": sig.action,
                        "strength": sig.strength,
                        "reason": sig.reason,
                    }
                    break
        except Exception:
            pass

        # 因子明细
        factor_breakdown: dict[str, float] = {}
        try:
            factor_breakdown = screener.explain(market_data, sym, target_date)
        except Exception:
            pass

        item = ScreenItem(
            symbol=sym,
            name=name_map.get(sym, ""),
            score=round(score, 4),
            signal_tag=tag,
            factor_breakdown=factor_breakdown,
            buy_signal=buy_signal,
            key_metrics=key_metrics,
        )
        results.append(item)

    # ---- 6. 排序：有 buy_signal 的排前面，组内按 score 降序 ----
    results.sort(key=lambda x: (0 if x.buy_signal else 1, -x.score))
    with_buy = sum(1 for r in results if r.buy_signal is not None)

    return ScreenResult(
        date=str(target_date),
        screener=screener_name,
        strategy=strategy_name,
        universe_size=len(market_data),
        candidates=len(candidates),
        with_buy_signal=with_buy,
        results=results[:top_n],
    )


def _screener_index_of(df: pd.DataFrame, target: date) -> int | None:
    """查找 target date 在 DataFrame 中的整数索引。"""
    for i, val in enumerate(df.index):
        d = val.date() if hasattr(val, "date") else val
        if d == target:
            return i
    return None


def _build_stock_name_map_safe() -> dict[str, str]:
    """安全加载股票名称映射（不依赖 server 模块的缓存）。"""
    import json
    name_map: dict[str, str] = {}
    try:
        csv_path = (
            Path(__file__).resolve().parent.parent.parent
            / "data" / "a_stock_list.csv"
        )
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            if "code" in df.columns and "name" in df.columns:
                for _, row in df.iterrows():
                    name_map[str(row["code"])] = str(row["name"])
    except Exception:
        pass
    return name_map
```

- [ ] **Step 2: Verify engine import**

Run: `python -c "from autotrade.core.engine import run_screen, _screener_index_of; print('OK')"`  
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add autotrade/core/engine.py
git commit -m "feat: add run_screen() for single-date screener + strategy buy-point confirmation"
```

---

### Task 4: Add API Endpoints

**Files:**
- Modify: `autotrade/api/server.py`

**Interfaces:**
- Consumes: `run_screen()` from Task 3; `list_screens()` from registry; `ScreenResult` from Task 1
- Produces: `GET /api/screeners`, `POST /api/screen` — used by frontend Tasks 6-9

- [ ] **Step 1: Add imports and Pydantic models**

In `autotrade/api/server.py`:

At line 48 (after `from autotrade.core.engine import ...`), add `run_screen` to the import:

```python
from autotrade.core.engine import analyze_stock, run_backtest, run_portfolio_backtest, run_screen
```

At line 49 (after `from autotrade.registry import ...`), add `list_screens, get_screener`:

```python
from autotrade.registry import (
    init_registry, list_datasources, list_strategies, list_screens, get_screener,
    is_builtin_strategy, is_builtin_group,
)
```

After the existing `PortfolioBacktestRequest` class (around line 140), add the Pydantic request model:

```python
class ScreenRequest(BaseModel):
    """选股扫描请求。"""
    screener: str = "momentum_screener"
    strategy: str = "ma_cross"
    date: str  # "YYYY-MM-DD"
    top_n: int = 20
    screener_params: Optional[dict] = None
    strategy_params: Optional[dict] = None
```

- [ ] **Step 2: Add `GET /api/screeners` endpoint**

Add after the `api_list_strategies` endpoint (after line 725). Place it right before the `_annotation_to_type_str` helper:

```python
@api_router.get("/screeners")
def api_list_screeners():
    """列出可用选股器及其参数信息。"""
    from autotrade.core.config import _load_screener_params
    import inspect

    result = []
    for name in list_screens():
        info: dict = {"name": name, "params": {}, "param_schema": {}}
        # 加载 YAML 配置的当前参数值
        try:
            s_params = _load_screener_params(name)
        except Exception:
            s_params = {}
        if s_params:
            info["params"] = s_params

        # 从选股器类的构造函数提取参数 schema
        try:
            screener_cls = get_screener(name)
            sig = inspect.signature(screener_cls.__init__)
            param_schema = {}
            for pname, p in sig.parameters.items():
                if pname in ("self", "args", "kwargs"):
                    continue
                entry: dict = {}
                if p.default is not inspect.Parameter.empty:
                    entry["default"] = p.default
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

    return {"screeners": result}
```

Note: `_load_screener_params` is defined in `engine.py` (line 370) but is module-private. We need to either re-define it in server.py or import it. The cleanest way: copy the function logic inline or make it importable. Let's just use the same pattern as `get_strategy_params` — import from config:

Actually, `_load_screener_params` is in `engine.py`. To keep it clean, we duplicate the path logic inline in the endpoint:

```python
@api_router.get("/screeners")
def api_list_screeners():
    """列出可用选股器及其参数信息。"""
    import yaml
    import inspect

    result = []
    for name in list_screens():
        info: dict = {"name": name, "params": {}, "param_schema": {}}
        # 加载 YAML 配置的当前参数值
        cfg_path = _ROOT / "config" / "screens" / f"{name}.yaml"
        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                info["params"] = data.get("params", {}) or {}
            except Exception:
                pass

        # 从选股器类的构造函数提取参数 schema
        try:
            screener_cls = get_screener(name)
            sig = inspect.signature(screener_cls.__init__)
            param_schema = {}
            for pname, p in sig.parameters.items():
                if pname in ("self", "args", "kwargs"):
                    continue
                entry: dict = {}
                if p.default is not inspect.Parameter.empty:
                    entry["default"] = p.default
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

    return {"screeners": result}
```

- [ ] **Step 3: Add `POST /api/screen` endpoint**

Add after `GET /api/screeners`:

```python
@api_router.post("/screen")
def api_screen_stocks(req: ScreenRequest):
    """单日选股扫描：Screener 初筛 + Strategy 买点确认。"""
    from datetime import date as date_cls

    try:
        target_date = date_cls.fromisoformat(req.date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")

    try:
        result = run_screen(
            screener_name=req.screener,
            strategy_name=req.strategy,
            target_date=target_date,
            top_n=req.top_n,
            screener_params=req.screener_params,
            strategy_params=req.strategy_params,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("选股扫描失败")
        raise HTTPException(status_code=500, detail=f"选股扫描失败: {e}")

    # Convert ScreenResult/ScreenItem to dict
    return {
        "date": result.date,
        "screener": result.screener,
        "strategy": result.strategy,
        "universe_size": result.universe_size,
        "candidates": result.candidates,
        "with_buy_signal": result.with_buy_signal,
        "results": [
            {
                "symbol": r.symbol,
                "name": r.name,
                "score": r.score,
                "signal_tag": r.signal_tag,
                "factor_breakdown": r.factor_breakdown,
                "buy_signal": r.buy_signal,
                "key_metrics": r.key_metrics,
            }
            for r in result.results
        ],
    }
```

- [ ] **Step 4: Verify endpoints**

Run: `python -c "from autotrade.api.server import app; print('Server imports OK')"`  
Expected: `Server imports OK`

- [ ] **Step 5: Commit**

```bash
git add autotrade/api/server.py
git commit -m "feat: add GET /api/screeners and POST /api/screen endpoints"
```

---

### Task 5: Add Frontend TypeScript Types

**Files:**
- Modify: `web/src/types/index.ts` (append at end)

**Interfaces:**
- Produces: `ScreenerInfo`, `ScreenRequest`, `ScreenResult`, `ScreenItem`, `BuySignalInfo`, `FactorBreakdown`, `KeyMetrics` — used by Tasks 6, 7, 8

- [ ] **Step 1: Read current types file to find append location**

Read `web/src/types/index.ts` and note the last line number.

- [ ] **Step 2: Append new types**

Append to `web/src/types/index.ts`:

```typescript
// ---- Screener / Stock Picking ----

export interface ParamSchemaEntry {
  type?: string
  default?: unknown
}

export interface ScreenerInfo {
  name: string
  params: Record<string, unknown>
  param_schema: Record<string, ParamSchemaEntry>
}

export interface ScreenRequest {
  screener: string
  strategy: string
  date: string           // "YYYY-MM-DD"
  top_n?: number
  screener_params?: Record<string, unknown>
  strategy_params?: Record<string, unknown>
}

export interface FactorBreakdown {
  [factorName: string]: number
}

export interface BuySignalInfo {
  date: string
  action: 'BUY'
  strength: number
  reason: string
}

export interface KeyMetrics {
  close: number
  volume: number
  amount: number
  [indicator: string]: number
}

export interface ScreenItem {
  symbol: string
  name: string
  score: number
  signal_tag: string
  factor_breakdown: FactorBreakdown
  buy_signal: BuySignalInfo | null
  key_metrics: KeyMetrics
}

export interface ScreenResult {
  date: string
  screener: string
  strategy: string
  universe_size: number
  candidates: number
  with_buy_signal: number
  results: ScreenItem[]
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`  
Expected: no new type errors from these additions

- [ ] **Step 4: Commit**

```bash
git add web/src/types/index.ts
git commit -m "feat: add screener-related TypeScript types"
```

---

### Task 6: Add API Client Methods

**Files:**
- Modify: `web/src/api/client.ts`

**Interfaces:**
- Consumes: Types from Task 5
- Produces: `api.getScreeners()`, `api.screen()` — used by Tasks 7, 8

- [ ] **Step 1: Add import for new types**

In `web/src/api/client.ts`, add to the existing type imports:

```typescript
import type {
  // ... existing imports ...
  ScreenerInfo,
  ScreenRequest,
  ScreenResult,
} from '@/types'
```

- [ ] **Step 2: Add API methods**

Add to the `api` export object:

```typescript
  /** List available screeners with their parameter schemas */
  getScreeners: (): Promise<{ screeners: ScreenerInfo[] }> =>
    request('/api/screeners'),

  /** Run a single-date screener scan with strategy buy-point confirmation */
  screen: (data: ScreenRequest): Promise<ScreenResult> =>
    request('/api/screen', { method: 'POST', body: JSON.stringify(data) }),
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`  
Expected: no errors in client.ts

- [ ] **Step 4: Commit**

```bash
git add web/src/api/client.ts
git commit -m "feat: add getScreeners() and screen() API client methods"
```

---

### Task 7: Create ScreenerParamsEditor Component

**Files:**
- Create: `web/src/components/ScreenerParamsEditor.tsx`

**Interfaces:**
- Consumes: `ScreenerInfo` from Task 5
- Produces: `<ScreenerParamsEditor screener editParams onChange />` — used by Task 8

- [ ] **Step 1: Create the component**

```typescript
import { useState } from 'react'
import type { ScreenerInfo } from '@/types'

interface Props {
  screener: ScreenerInfo | undefined
  /** Current edit values keyed by param name */
  editParams: Record<string, string>
  onChange: (key: string, value: string) => void
}

const SIMPLE_TYPES = new Set(['int', 'float', 'str', 'bool'])

export default function ScreenerParamsEditor({ screener, editParams, onChange }: Props) {
  const [expanded, setExpanded] = useState(false)

  if (!screener?.param_schema || Object.keys(screener.param_schema).length === 0) {
    return null
  }

  const schema = screener.param_schema
  const entries = Object.entries(schema)
  const simpleEntries = entries.filter(([, info]) => SIMPLE_TYPES.has(info.type || 'str'))
  const complexEntries = entries.filter(([, info]) => !SIMPLE_TYPES.has(info.type || 'str'))

  const summary = entries.slice(0, 5).map(([k]) => {
    const v = editParams[k] !== undefined ? editParams[k] : '—'
    return `${k}=${v}`
  }).join(', ') + (entries.length > 5 ? ` +${entries.length - 5}` : '')

  return (
    <div className="params-section" style={{ marginTop: 16 }}>
      <button
        type="button"
        className="params-toggle"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        <span className="toggle-icon">{expanded ? '▼' : '▶'}</span> 选股器参数
        <span className="params-summary">{summary}</span>
      </button>
      {expanded && (
        <div className="params-body">
          <div className="param-grid">
            {simpleEntries.map(([key, info]) => {
              const inputType = info.type === 'int' || info.type === 'float' ? 'number' : 'text'
              const step = info.type === 'float' ? '0.01' : info.type === 'int' ? '1' : undefined
              return (
                <div key={key} className="param-item">
                  <label
                    className="param-label"
                    title={`${key}${info.default !== undefined ? ' · 默认: ' + JSON.stringify(info.default) : ''}`}
                  >
                    {key}
                  </label>
                  <input
                    type={inputType}
                    className="form-input"
                    value={editParams[key] ?? ''}
                    placeholder={info.default !== undefined ? String(info.default) : ''}
                    step={step as number | undefined}
                    onChange={e => onChange(key, e.target.value)}
                  />
                </div>
              )
            })}
          </div>
          {complexEntries.map(([key, info]) => (
            <div key={key} className="param-item param-item-wide">
              <label className="param-label">
                {key} <span className="param-type-tag">{info.type}</span>
              </label>
              <textarea
                className="form-input"
                rows={2}
                value={editParams[key] ?? ''}
                placeholder={info.default !== undefined ? JSON.stringify(info.default) : ''}
                onChange={e => onChange(key, e.target.value)}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`  
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add web/src/components/ScreenerParamsEditor.tsx
git commit -m "feat: add ScreenerParamsEditor component"
```

---

### Task 8: Create Screener Page

**Files:**
- Create: `web/src/pages/Screener.tsx`

**Interfaces:**
- Consumes: All types from Task 5; `api` from Task 6; `ScreenerParamsEditor` from Task 7; `StrategyParamsEditor` (existing); `useCachedStrategies` (existing)
- Produces: `<Screener />` page — used by Task 9 routing

- [ ] **Step 1: Create the full page component**

```typescript
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '@/hooks/useApp'
import { useCachedStrategies } from '@/hooks/useCachedStrategies'
import { api } from '@/api/client'
import ScreenerParamsEditor from '@/components/ScreenerParamsEditor'
import StrategyParamsEditor from '@/components/StrategyParamsEditor'
import type { ScreenerInfo, ScreenResult, ScreenItem, StrategyInfo } from '@/types'

function formatAmount(amount: number): string {
  if (amount >= 1e8) return (amount / 1e8).toFixed(2) + '亿'
  if (amount >= 1e4) return (amount / 1e4).toFixed(0) + '万'
  return String(amount)
}

function formatVolume(vol: number): string {
  if (vol >= 1e6) return (vol / 1e6).toFixed(1) + 'M'
  if (vol >= 1e3) return (vol / 1e3).toFixed(0) + 'K'
  return String(vol)
}

export default function Screener() {
  const navigate = useNavigate()
  const { showToast, showLoading, hideLoading } = useApp()
  const { strategies } = useCachedStrategies()

  // Form state
  const [screeners, setScreeners] = useState<ScreenerInfo[]>([])
  const [screenerName, setScreenerName] = useState('momentum_screener')
  const [strategyName, setStrategyName] = useState('ma_cross')
  const [date, setDate] = useState('')
  const [topN, setTopN] = useState(20)
  const [screenerParams, setScreenerParams] = useState<Record<string, string>>({})
  const [strategyParams, setStrategyParams] = useState<Record<string, string>>({})

  // Result state
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ScreenResult | null>(null)
  const [showBuyOnly, setShowBuyOnly] = useState(false)

  // Derived
  const selectedScreener = screeners.find(s => s.name === screenerName)
  const selectedStrategy = strategies.find(s => s.name === strategyName)
  const filteredResults = result
    ? (showBuyOnly ? result.results.filter(r => r.buy_signal !== null) : result.results)
    : []

  // Load screeners on mount
  useEffect(() => {
    api.getScreeners().then(data => {
      setScreeners(data.screeners)
      if (data.screeners.length > 0 && !data.screeners.find(s => s.name === screenerName)) {
        setScreenerName(data.screeners[0].name)
      }
    }).catch(() => {})
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  // Set default date to today
  useEffect(() => {
    if (!date) {
      setDate(new Date().toISOString().slice(0, 10))
    }
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  // Search handler
  const handleSearch = useCallback(async () => {
    if (!date) {
      setError('请选择日期')
      return
    }
    setLoading(true)
    setError(null)
    showLoading('正在扫描全市场...')
    try {
      // Build params from form values (only include non-empty)
      const sp: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(screenerParams)) {
        if (v !== '' && v !== undefined) {
          const schema = selectedScreener?.param_schema?.[k]
          if (schema?.type === 'float') sp[k] = parseFloat(v)
          else if (schema?.type === 'int') sp[k] = parseInt(v, 10)
          else if (schema?.type === 'bool') sp[k] = v === 'true'
          else sp[k] = v
        }
      }
      const tp: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(strategyParams)) {
        if (v !== '' && v !== undefined) {
          const schema = selectedStrategy?.param_schema?.[k]
          if (schema?.type === 'float') tp[k] = parseFloat(v)
          else if (schema?.type === 'int') tp[k] = parseInt(v, 10)
          else if (schema?.type === 'bool') tp[k] = v === 'true'
          else tp[k] = v
        }
      }

      const res = await api.screen({
        screener: screenerName,
        strategy: strategyName,
        date,
        top_n: topN,
        screener_params: Object.keys(sp).length > 0 ? sp : undefined,
        strategy_params: Object.keys(tp).length > 0 ? tp : undefined,
      })
      setResult(res)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '选股扫描失败'
      setError(msg)
      showToast(msg, 'error')
    } finally {
      setLoading(false)
      hideLoading()
    }
  }, [date, screenerName, strategyName, topN, screenerParams, strategyParams, selectedScreener, selectedStrategy, showLoading, hideLoading, showToast])

  // Score color helper
  const scoreColor = (score: number) => {
    if (score >= 0.8) return 'var(--success)'
    if (score >= 0.6) return 'var(--warning)'
    return 'var(--text-muted)'
  }

  const hitRate = result && result.universe_size > 0
    ? ((result.with_buy_signal / result.universe_size) * 100).toFixed(2)
    : '0.00'

  return (
    <div className="page">
      {/* Hero */}
      <div className="page-hero">
        <h1 className="page-hero__title">📊 智能选股</h1>
        <p className="page-hero__desc">
          基于选股器扫描 + 策略买点确认，发现当天最佳入场机会
        </p>
      </div>

      {/* Form Card */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-body">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, alignItems: 'end' }}>
            {/* Screener selector */}
            <div>
              <label className="form-label">选股器</label>
              <select
                className="form-input"
                value={screenerName}
                onChange={e => { setScreenerName(e.target.value); setScreenerParams({}) }}
              >
                {screeners.map(s => (
                  <option key={s.name} value={s.name}>{s.name}</option>
                ))}
              </select>
            </div>

            {/* Strategy selector */}
            <div>
              <label className="form-label">交易策略</label>
              <select
                className="form-input"
                value={strategyName}
                onChange={e => { setStrategyName(e.target.value); setStrategyParams({}) }}
              >
                {strategies.map(s => (
                  <option key={s.name} value={s.name}>{s.name}</option>
                ))}
              </select>
            </div>

            {/* Date picker */}
            <div>
              <label className="form-label">日期</label>
              <input
                type="date"
                className="form-input"
                value={date}
                max={new Date().toISOString().slice(0, 10)}
                onChange={e => setDate(e.target.value)}
              />
            </div>

            {/* Top N */}
            <div>
              <label className="form-label">返回数量</label>
              <input
                type="number"
                className="form-input"
                value={topN}
                min={5}
                max={100}
                onChange={e => setTopN(parseInt(e.target.value, 10) || 20)}
              />
            </div>

            {/* Submit */}
            <div>
              <button className="btn btn-primary" onClick={handleSearch} disabled={loading} style={{ width: '100%' }}>
                {loading ? '扫描中...' : '🔍 开始选股'}
              </button>
            </div>
          </div>

          {/* Parameter editors */}
          <ScreenerParamsEditor
            screener={selectedScreener}
            editParams={screenerParams}
            onChange={(k, v) => setScreenerParams(prev => ({ ...prev, [k]: v }))}
          />
          <StrategyParamsEditor
            strategy={selectedStrategy}
            editParams={strategyParams}
            onChange={(k, v) => setStrategyParams(prev => ({ ...prev, [k]: v }))}
          />
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="card" style={{ marginBottom: 24, borderLeft: '3px solid var(--danger)' }}>
          <div className="card-body" style={{ color: 'var(--danger)' }}>
            ⚠️ {error}
          </div>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-body">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="skeleton" style={{ height: 80, borderRadius: 8 }} />
              ))}
            </div>
            <div className="skeleton" style={{ height: 400, borderRadius: 8 }} />
          </div>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <>
          {/* Summary cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16, marginBottom: 24 }}>
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>扫描股票</div>
                <div style={{ fontSize: 28, fontWeight: 700 }}>{result.universe_size.toLocaleString()}</div>
              </div>
            </div>
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>候选股票</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--warning)' }}>{result.candidates}</div>
              </div>
            </div>
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>有买点</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--success)' }}>{result.with_buy_signal}</div>
              </div>
            </div>
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>命中率</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--info)' }}>{hitRate}%</div>
              </div>
            </div>
          </div>

          {/* Filter bar */}
          <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 13 }}>
              <input
                type="checkbox"
                checked={showBuyOnly}
                onChange={e => setShowBuyOnly(e.target.checked)}
              />
              仅看有买点
            </label>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              显示 {filteredResults.length} / {result.results.length} 只
            </span>
          </div>

          {/* Results table */}
          {filteredResults.length > 0 ? (
            <div className="card" style={{ overflow: 'auto' }}>
              <table className="table" style={{ minWidth: 900 }}>
                <thead>
                  <tr>
                    <th style={{ width: 40 }}>#</th>
                    <th style={{ width: 100 }}>代码</th>
                    <th style={{ width: 100 }}>名称</th>
                    <th style={{ width: 80 }}>评分</th>
                    <th style={{ width: 140 }}>信号标签</th>
                    <th style={{ width: 200 }}>因子明细</th>
                    <th style={{ width: 100 }}>买点</th>
                    <th style={{ width: 200 }}>关键指标</th>
                    <th style={{ width: 60 }}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredResults.map((item, idx) => (
                    <tr key={item.symbol}>
                      <td>
                        {idx === 0 && item.buy_signal ? '🥇' : idx === 1 && item.buy_signal ? '🥈' : idx === 2 && item.buy_signal ? '🥉' : idx + 1}
                      </td>
                      <td>
                        <button
                          className="btn-link"
                          style={{ fontWeight: 600, fontFamily: 'monospace' }}
                          onClick={() => navigate(`/analyze?symbol=${item.symbol}&strategy=${strategyName}`)}
                        >
                          {item.symbol}
                        </button>
                      </td>
                      <td style={{ fontSize: 13 }}>{item.name}</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <div style={{
                            width: 60, height: 6, borderRadius: 3,
                            background: 'var(--border-light)', overflow: 'hidden',
                          }}>
                            <div style={{
                              width: `${(item.score * 100).toFixed(0)}%`,
                              height: '100%',
                              background: scoreColor(item.score),
                              borderRadius: 3,
                            }} />
                          </div>
                          <span style={{ fontSize: 13, fontWeight: 600, color: scoreColor(item.score) }}>
                            {item.score.toFixed(2)}
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className="badge" style={{
                          background: 'var(--bg-secondary)',
                          color: 'var(--text-secondary)',
                          fontSize: 11,
                          padding: '2px 8px',
                          borderRadius: 4,
                        }}>
                          {item.signal_tag}
                        </span>
                      </td>
                      <td>
                        {Object.keys(item.factor_breakdown).length > 0 ? (
                          <div className="tooltip-wrapper" style={{ position: 'relative', cursor: 'help' }}>
                            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                              {Object.keys(item.factor_breakdown).length} 个因子
                            </span>
                            <div className="tooltip-content" style={{
                              display: 'none',
                              position: 'absolute',
                              bottom: '100%',
                              left: 0,
                              background: 'var(--bg-card)',
                              border: '1px solid var(--border)',
                              borderRadius: 8,
                              padding: 12,
                              minWidth: 200,
                              boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                              zIndex: 100,
                            }}>
                              {Object.entries(item.factor_breakdown).map(([name, val]) => (
                                <div key={name} style={{ marginBottom: 6 }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 2 }}>
                                    <span>{name}</span>
                                    <span style={{ fontWeight: 600 }}>{(val * 100).toFixed(0)}%</span>
                                  </div>
                                  <div style={{
                                    width: '100%', height: 4, borderRadius: 2,
                                    background: 'var(--border-light)', overflow: 'hidden',
                                  }}>
                                    <div style={{
                                      width: `${(val * 100).toFixed(0)}%`,
                                      height: '100%',
                                      background: 'var(--primary)',
                                      borderRadius: 2,
                                    }} />
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>—</span>
                        )}
                      </td>
                      <td>
                        {item.buy_signal ? (
                          <div>
                            <span className="badge" style={{
                              background: 'rgba(34,197,94,0.1)',
                              color: 'var(--success)',
                              fontSize: 11,
                              padding: '2px 8px',
                              borderRadius: 4,
                              marginRight: 4,
                            }}>
                              BUY {((item.buy_signal.strength ?? 0) * 100).toFixed(0)}%
                            </span>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                              title={item.buy_signal.reason}>
                              {item.buy_signal.reason}
                            </div>
                          </div>
                        ) : (
                          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>—</span>
                        )}
                      </td>
                      <td style={{ fontSize: 11 }}>
                        <div>收盘: {item.key_metrics.close?.toFixed(2) ?? '—'}</div>
                        <div>量: {item.key_metrics.volume ? formatVolume(item.key_metrics.volume) : '—'}</div>
                        <div>额: {item.key_metrics.amount ? formatAmount(item.key_metrics.amount) : '—'}</div>
                      </td>
                      <td>
                        <button
                          className="btn-link"
                          style={{ fontSize: 12 }}
                          onClick={() => navigate(`/analyze?symbol=${item.symbol}&strategy=${strategyName}`)}
                        >
                          查看 →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                <div style={{ fontSize: 40, marginBottom: 12 }}>📭</div>
                <p>当天没有符合条件的股票</p>
                <p style={{ fontSize: 12 }}>试试更换选股器、策略，或调整参数</p>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`  
Expected: no errors in Screener.tsx

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/Screener.tsx
git commit -m "feat: add Screener page with form, summary cards, results table"
```

---

### Task 9: Add Route and Sidebar Navigation

**Files:**
- Modify: `web/src/App.tsx`
- Modify: `web/src/components/Sidebar.tsx`

**Interfaces:**
- Consumes: `Screener` page from Task 8
- Produces: `/screener` route accessible from sidebar

- [ ] **Step 1: Add lazy import and route in App.tsx**

In `web/src/App.tsx`, after the `Groups` import:

```typescript
const Screener = lazy(() => import('@/pages/Screener'))
```

Add route inside the protected `<Route element={<Layout />}>` block, after the dashboard route:

```typescript
<Route path="/screener" element={<Suspense fallback={<PageLoader />}><Screener /></Suspense>} />
```

- [ ] **Step 2: Add nav item in Sidebar.tsx**

In `web/src/components/Sidebar.tsx`, add a new nav item entry in the `navItems` array after the dashboard item (`{ path: '/', label: '仪表盘', icon: 'dashboard' },`):

```typescript
  { path: '/screener', label: '选股', icon: 'target' },
```

Add the `target` SVG icon in the `svgIcons` record:

```typescript
  target: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" fill="currentColor" fillOpacity="0.5" />
    </svg>
  ),
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`  
Expected: no errors

- [ ] **Step 4: Verify Vite dev build**

Run: `cd web && npx vite build --mode development`  
Expected: successful build with new chunk for Screener page

- [ ] **Step 5: Commit**

```bash
git add web/src/App.tsx web/src/components/Sidebar.tsx
git commit -m "feat: add /screener route and sidebar navigation"
```

---

### Task 10: Integration Smoke Test

**Files:**
- No file changes — verification only

- [ ] **Step 1: Start backend server and test GET /api/screeners**

Run: `python -m autotrade.api.server` (or equivalent)
Test: `curl http://localhost:8000/api/screeners`
Expected: JSON with `screeners` array containing `momentum_screener` and `hot_money_screener` with params and param_schema

- [ ] **Step 2: Test POST /api/screen with a specific date**

Test: `curl -X POST http://localhost:8000/api/screen -H "Content-Type: application/json" -d '{"screener":"momentum_screener","strategy":"ma_cross","date":"2025-06-30","top_n":5}'`
Expected: JSON with `universe_size`, `candidates`, `with_buy_signal`, `results` array

- [ ] **Step 3: Build frontend and test in browser**

Run: `cd web && npm run build`
Open browser, navigate to `/screener`, verify:
- Page loads with form (screener dropdown, strategy dropdown, date picker)
- Parameter editors expand/collapse
- Submit triggers scan, shows loading state, then results
- Summary cards show correct counts
- Table rows show scores with colored bars, signal tags, factor tooltips, buy signals
- Clicking a stock navigates to `/analyze?symbol=...&strategy=...`
- Empty state shows when no results
- Sidebar "选股" nav item active state works

- [ ] **Step 4: Commit** (if any fixes needed)

```bash
git add -A
git commit -m "fix: integration tweaks for screener page"
```
