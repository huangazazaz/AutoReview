# 单股回测页 — 叠加股价折线图

**日期**: 2026-06-20  
**状态**: approved  
**分支**: dev/autotrade-mvp

## 背景

当前单股分析页面 (`#/analyze`) 已有净值曲线图（紫色净值线 + 灰色基准线 + 绿色回撤子图），用户希望在同一个图表上叠加股票收盘价折线，便于直观对比策略表现与股价走势的关系。

## 方案

**双Y轴叠加**：
- 左Y轴：净值（万元），对应策略净值曲线和基准线
- 右Y轴：收盘价（元），对应股价折线
- 下方子图：回撤区域（保持不变）

**数据获取**：
- 前端在获取 `/analyze` 回测结果后，额外调用 `/bars` 接口获取日线 OHLCV（使用相同的 symbol/start/end/period 参数）
- 后端无需改动

## 改动范围

**仅改一个文件**：`frontend/js/views/analyze.js`

### 改动点 1：`submitAnalysis()` — 并行获取股价数据

在回测成功后，用同参数调用 `API.getBars()`，将 bars 数据传入 `renderResults()`。

```js
// 伪代码
const barsData = await safeAsync(() => API.getBars({
    symbol, start: params.start, end: params.end, period: params.period
}), '');
if (data) renderResults(data, barsData?.bars || []);
```

### 改动点 2：`renderResults()` — 传递 bars 到图表

签名增加 `bars` 参数，传给 `renderEquityChart()`。

### 改动点 3：`renderEquityChart()` — 增加收盘价折线和右Y轴

在现有 ECharts option 中：

| 新增 | 配置 |
|------|------|
| 右Y轴 (`yAxis[2]`) | `type: 'value'`, `gridIndex: 0`, 与左Y轴共用主图网格 |
| 收盘价 series | `name: '收盘价'`, `type: 'line'`, `yAxisIndex: 2`（右Y轴），颜色 `#F59E0B`（橙金），实线宽 1.5，`symbol: 'none'`, `z: 1` |
| 图例更新 | 增加 `'收盘价'` |
| tooltip 更新 | 增加收盘价显示行 |

**保持不变**：
- 净值曲线（`#8B5CF6` 紫色，实线 2.5，渐变填充）
- 基准线（`#64748B` 灰色，虚线 1.5）
- 回撤子图（下方 grid，绿色区域）
- markPoint 最高/最低标注

## 兼容性

- 如果 `/bars` 请求失败或无数据，图表仍正常展示（仅无收盘价线）
- 如果 bars 日期与净值曲线日期不完全对齐，ECharts 的 category 轴按索引对齐，需确保两者长度一致（以 bars 日期为基准，净值曲线按日期匹配）
- 暗色主题 (dark) 保持不变

## 不涉及

- 后端接口
- CSS 样式
- 其他视图页面
