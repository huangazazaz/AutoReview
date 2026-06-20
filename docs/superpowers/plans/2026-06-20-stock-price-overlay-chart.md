# Stock Price Overlay Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stock closing price line (right Y-axis) overlaid on the existing equity curve chart in the single-stock analyze page.

**Architecture:** Pure frontend change to `frontend/js/views/analyze.js`. After `/analyze` returns backtest results, the frontend calls `/bars` with the same parameters to fetch OHLCV data. The closing prices are then passed to the ECharts config which adds a right Y-axis and a new series.

**Tech Stack:** Vanilla JS, Apache ECharts 5.5.1 (CDN), FastAPI backend (no changes)

---

### Task 1: Fetch bars data in submitAnalysis and pass to renderResults

**Files:**
- Modify: `D:\AutoTrade\frontend\js\views\analyze.js`

- [ ] **Step 1: Add bars fetch call after backtest success**

In `submitAnalysis()`, after `safeAsync(() => API.analyze(params), ...)` returns data, add a parallel fetch for bars data. Then pass bars to `renderResults`.

Locate the block (approximately line 233-239):

```js
const data = await safeAsync(() => API.analyze(params), '回测失败');

hideLoading();
btn.disabled = false;
btn.innerHTML = `${Rocket({ size: 18 })} 开始回测`;

if (data) renderResults(data);
```

Replace with:

```js
const data = await safeAsync(() => API.analyze(params), '回测失败');

// 并行获取日线价格数据用于叠加股价折线
let bars = [];
if (data) {
    const barsParams = { symbol: params.symbol };
    if (params.start) barsParams.start = params.start;
    if (params.end) barsParams.end = params.end;
    if (params.period) barsParams.period = params.period;
    const barsData = await safeAsync(() => API.getBars(barsParams), '');
    bars = barsData?.bars || [];
}

hideLoading();
btn.disabled = false;
btn.innerHTML = `${Rocket({ size: 18 })} 开始回测`;

if (data) renderResults(data, bars);
```

- [ ] **Step 2: Update renderResults signature and pass bars to chart**

Change `function renderResults(data) {` to `function renderResults(data, bars = []) {`.

Then find the `renderEquityChart` call (approximately line 414):

```js
if (equityCurve.length > 0 && typeof echarts !== 'undefined') {
    renderEquityChart(equityCurve, data.symbol, data.stock_name, m.initial_capital || 0);
}
```

Replace with:

```js
if (equityCurve.length > 0 && typeof echarts !== 'undefined') {
    renderEquityChart(equityCurve, data.symbol, data.stock_name, m.initial_capital || 0, bars);
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/js/views/analyze.js
git commit -m "feat: fetch bars data alongside backtest results"
```

---

### Task 2: Add close price line and right Y-axis to the chart

**Files:**
- Modify: `D:\AutoTrade\frontend\js\views\analyze.js`

- [ ] **Step 1: Update renderEquityChart signature and extract close prices**

Change:

```js
function renderEquityChart(curve, symbol, stockName, initialCapital) {
```

To:

```js
function renderEquityChart(curve, symbol, stockName, initialCapital, bars = []) {
```

After the existing `const baseline = new Array(dates.length).fill(initialCapital);` line, add close price extraction:

```js
// 提取收盘价（与净值曲线日期对齐）
const closes = dates.map((d, i) => {
    if (i < bars.length) return bars[i].close;
    return null;
});
const hasClosePrice = closes.some(v => v != null);
```

- [ ] **Step 2: Add right Y-axis for close price**

In the `yAxis` array, add a third axis entry after the existing two. Locate the `yAxis: [` block (approximately line 499). After the second entry (the drawdown axis ending around line 525), add:

```js
{
    type: 'value',
    gridIndex: 0,
    scale: true,
    splitLine: { show: false },
    axisLabel: {
        color: '#F59E0B',
        fontSize: 10,
        formatter: v => v.toFixed(2),
    },
    name: '股价 (元)',
    nameTextStyle: { color: '#F59E0B', fontSize: 10 },
},
```

The full yAxis array should now have 3 entries: `[净值轴, 回撤轴, 股价轴]`.

- [ ] **Step 3: Add close price series**

In the `series` array, add a new series entry after the existing three (baseline, equity, drawdown). Append:

```js
...(hasClosePrice ? [{
    name: '收盘价',
    type: 'line',
    data: closes,
    xAxisIndex: 0,
    yAxisIndex: 2,
    lineStyle: { color: '#F59E0B', type: 'solid', width: 1.5 },
    itemStyle: { color: '#F59E0B' },
    symbol: 'none',
    z: 1,
}] : []),
```

- [ ] **Step 4: Update legend to include close price**

Replace:

```js
legend: {
    data: ['基准', '净值', '回撤'],
    ...
},
```

With:

```js
legend: {
    data: ['基准', '净值', '回撤', ...(hasClosePrice ? ['收盘价'] : [])],
    ...
},
```

- [ ] **Step 5: Update tooltip to show close price**

In the tooltip `formatter` function, add close price display. After the existing drawdown line:

```js
html += `📉 回撤: <span style="color:${ddColor};font-weight:600;">${dd.toFixed(2)}%</span>`;
```

Add:

```js
if (hasClosePrice) {
    const closeVal = closes[params[0].dataIndex];
    if (closeVal != null) {
        html += `<br/>📊 收盘价: <span style="color:#F59E0B;font-weight:600;">${closeVal.toFixed(2)}</span>`;
    }
}
```

- [ ] **Step 6: Update chart subtitle to mention close price**

In the `title.subtext`, change:

```js
subtext: `基准线 = 虚线 · 净值 = 紫色实线 · 回撤 = 绿色区域`,
```

To:

```js
subtext: `基准线 = 虚线 · 净值 = 紫色实线 · 股价 = 橙色实线 · 回撤 = 绿色区域`,
```

- [ ] **Step 7: Update screen reader summary**

In the screen reader summary string, add close price info. After the existing summary construction, append a mention of the price line. Locate:

```js
const srSummary = `${symbol}${stockName ? ' ' + stockName : ''} 净值曲线图：初始资金${formatAmount(initialCapital)}，最终净值${formatAmount(finalEquity)}，总收益率${formatPct(totalReturn)}，最大回撤${formatPct(maxDD)}，期间最高净值${formatAmount(maxEquity)}。`;
```

Replace with:

```js
const closeStart = hasClosePrice && closes[0] != null ? closes[0].toFixed(2) : '';
const closeEnd = hasClosePrice && closes[closes.length - 1] != null ? closes[closes.length - 1].toFixed(2) : '';
const closeInfo = hasClosePrice ? `，股价从${closeStart}到${closeEnd}` : '';
const srSummary = `${symbol}${stockName ? ' ' + stockName : ''} 净值曲线图：初始资金${formatAmount(initialCapital)}，最终净值${formatAmount(finalEquity)}，总收益率${formatPct(totalReturn)}，最大回撤${formatPct(maxDD)}，期间最高净值${formatAmount(maxEquity)}${closeInfo}。`;
```

- [ ] **Step 8: Commit**

```bash
git add frontend/js/views/analyze.js
git commit -m "feat: overlay closing price line on equity curve chart with dual Y-axis"
```

---

### Task 3: Manual verification

- [ ] **Step 1: Start the server and test**

```bash
python -m autotrade.api.server
```

Open browser to `http://localhost:8000/#/analyze`, enter a stock code (e.g., 600522), select a strategy, submit.

**Verify:**
- The equity curve chart now shows a fourth series: orange "收盘价" line
- The right Y-axis shows price values in yuan
- The left Y-axis still shows equity values in 万元
- The drawdown sub-chart is unchanged
- Tooltip shows close price when hovering
- Legend includes "收盘价"
- Chart subtitle mentions the orange price line
- If `/bars` fails, chart still renders without the price line (graceful degradation)

- [ ] **Step 2: Commit any final tweaks**

```bash
git add frontend/js/views/analyze.js
git commit -m "chore: finalize price overlay chart"
```
