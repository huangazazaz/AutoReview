/**
 * K线数据视图 — 查询日线 OHLCV 数据，可视化蜡烛图
 */
(function () {
    'use strict';

    let chartInstance = null;

    async function render(container) {
        const _ = window.Icon || {};
        const Candlestick = _.candlestick || (() => '');
        const Chart = _.chart || (() => '');
        const Loader = _.loader || (() => '');
        const File = _.folder || (() => '');

        // 清理旧图表
        if (chartInstance) {
            chartInstance.dispose();
            chartInstance = null;
        }

        container.innerHTML = `
            <div class="page-hero">
                <div class="page-header" style="margin-bottom:0;">
                    <h1 class="page-title" style="display:flex;align-items:center;gap:var(--space-3);">
                        <span style="display:flex;align-items:center;justify-content:center;width:40px;height:40px;border-radius:var(--radius);background:var(--gradient-accent);color:#fff;">${Candlestick({ size: 22, class: '' })}</span>
                        K线数据
                    </h1>
                    <p class="page-subtitle" style="margin-top:4px;">查询股票日线 OHLCV 数据，可视化蜡烛图</p>
                </div>
            </div>

            <!-- 表单 -->
            <div class="card card-accent">
                <div class="card-header">
                    <span class="card-title" style="display:flex;align-items:center;gap:var(--space-2);">
                        <span style="color:var(--accent);">⚙</span> 查询参数
                    </span>
                </div>
                <div class="card-body">
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label" for="bars-symbol">股票代码 <span class="required" aria-hidden="true">*</span><span class="sr-only">必填</span></label>
                            <input type="text" class="form-input" id="bars-symbol"
                                placeholder="如 600522, 000001" maxlength="6" autofocus autocomplete="off"
                                list="bars-symbol-list">
                            <datalist id="bars-symbol-list"></datalist>
                        </div>
                        <div class="form-group">
                            <label class="form-label" for="bars-period">周期</label>
                            <select class="form-select" id="bars-period">
                                <option value="1y">最近 1 年</option>
                                <option value="6m">最近 6 个月</option>
                                <option value="3m">最近 3 个月</option>
                                <option value="20d" selected>最近 20 天</option>
                                <option value="60t">最近 60 交易日</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label class="form-label" for="bars-start">开始日期</label>
                            <input type="text" class="form-input date-input" id="bars-start"
                                placeholder="开始日期" autocomplete="off"
                                onfocus="this.type='date';this.showPicker?.()" onblur="if(!this.value)this.type='text'">
                        </div>
                        <div class="form-group">
                            <label class="form-label" for="bars-end">结束日期</label>
                            <input type="text" class="form-input date-input" id="bars-end"
                                placeholder="结束日期" autocomplete="off"
                                onfocus="this.type='date';this.showPicker?.()" onblur="if(!this.value)this.type='text'">
                        </div>
                        <div class="form-group" style="display:flex; align-items:flex-end;">
                            <button class="btn btn-primary" id="bars-submit" style="width:100%;">
                                ${Chart({ size: 18 })} 查询
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 信息条 -->
            <div id="bars-info"></div>

            <!-- 图表 -->
            <div class="chart-container large" id="bars-chart" role="img" aria-label="K线图 — 加载中"></div>

            <!-- 数据表格 -->
            <div id="bars-table-container"></div>
        `;

        // 加载缓存股票列表 → datalist 自动补全
        API.getCachedStocks().then(data => {
            const datalist = document.getElementById('bars-symbol-list');
            if (datalist && data.symbols && data.symbols.length) {
                datalist.innerHTML = data.symbols.map(s => {
                    const namePart = s.name ? ` ${s.name}` : '';
                    return `<option value="${escapeHtml(s.symbol)}">${escapeHtml(s.symbol)}${escapeHtml(namePart)} — ${s.last_close != null ? '¥' + formatNumber(s.last_close, 2) : '?'} · ${s.bars || 0}条</option>`;
                }).join('');
            }
        }).catch(() => {});

        // 提交
        document.getElementById('bars-submit').addEventListener('click', async () => {
            const symbol = document.getElementById('bars-symbol').value.trim();
            if (!symbol) {
                showToast('请输入股票代码', 'warning');
                return;
            }

            const params = { symbol };

            const period = document.getElementById('bars-period').value;
            const start = document.getElementById('bars-start').value;
            const end = document.getElementById('bars-end').value;
            if (start || end) {
                if (start) params.start = start;
                if (end) params.end = end;
            } else {
                params.period = period;
            }

            const btn = document.getElementById('bars-submit');
            btn.disabled = true;
            btn.innerHTML = `${Loader({ size: 18 })} 查询中...`;
            showLoading('正在查询日线数据...');

            const data = await safeAsync(() => API.getBars(params), '查询失败');

            hideLoading();
            btn.disabled = false;
            btn.innerHTML = `${Chart({ size: 18 })} 查询`;

            if (data) {
                renderBars(data);
            }
        });

        // 回车提交
        document.getElementById('bars-symbol').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') document.getElementById('bars-submit').click();
        });
    }

    function renderBars(data) {
        const _ = window.Icon || {};
        const File = _.folder || (() => '');
        const TrendingUp = _.trendingUp || (() => '');
        const TrendingDown = _.trendingDown || (() => '');

        const bars = data.bars || [];
        const count = data.count || 0;

        // 计算统计摘要
        if (count > 0) {
            const latest = bars[bars.length - 1];
            const prev = bars.length > 1 ? bars[bars.length - 2] : latest;
            const change = latest.close - prev.close;
            const changePct = prev.close !== 0 ? (change / prev.close * 100) : 0;
            const isUp = change >= 0;
            const periodHigh = Math.max(...bars.map(b => b.high));
            const periodLow = Math.min(...bars.map(b => b.low));

            // 信息条 + 数值摘要
            const infoEl = document.getElementById('bars-info');
            const stockLabel = data.stock_name
                ? `${escapeHtml(data.symbol)} <span style="color:var(--text-secondary);font-weight:400;">${escapeHtml(data.stock_name)}</span>`
                : escapeHtml(data.symbol);
            infoEl.innerHTML = `
                <div class="card card-gradient" role="status" style="margin:var(--space-4) 0;padding:var(--space-4);">
                    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:var(--space-3);">
                        <div style="display:flex;align-items:center;gap:var(--space-3);">
                            <span style="display:flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:50%;background:${isUp ? 'var(--buy-bg)' : 'var(--sell-bg)'};color:${isUp ? 'var(--buy)' : 'var(--sell)'};">${isUp ? TrendingUp({ size: 20 }) : TrendingDown({ size: 20 })}</span>
                            <strong style="font-size:16px;">${stockLabel}</strong>
                        </div>
                        <div class="kpi-row" style="padding:0;">
                            <div class="kpi-item">
                                <span class="kpi-label">最新价</span>
                                <span class="kpi-value" style="color:${isUp ? 'var(--buy)' : 'var(--sell)'};">${formatNumber(latest.close, 2)}</span>
                            </div>
                            <div class="kpi-item">
                                <span class="kpi-label">涨跌</span>
                                <span class="kpi-value" style="color:${isUp ? 'var(--buy)' : 'var(--sell)'};">${isUp ? '+' : ''}${formatNumber(change, 2)} (${isUp ? '+' : ''}${formatNumber(changePct, 2)}%)</span>
                            </div>
                            <div class="kpi-item">
                                <span class="kpi-label">最高 / 最低</span>
                                <span class="kpi-value" style="font-size:16px;">${formatNumber(periodHigh, 2)} <span style="color:var(--text-muted);font-size:13px;">/</span> ${formatNumber(periodLow, 2)}</span>
                            </div>
                            <div class="kpi-item">
                                <span class="kpi-label">数据条数</span>
                                <span class="kpi-value" style="font-size:16px;">${count}</span>
                            </div>
                        </div>
                    </div>
                </div>`;

            // 数值摘要面板 — 增强样式
            document.getElementById('bars-info').innerHTML += `
                <div class="stats-grid" id="bars-stats-grid" style="margin-bottom:var(--space-4);" role="status" aria-label="K线数值摘要">
                    <div class="stat-card" style="border-top:2px solid ${isUp ? 'var(--buy)' : 'var(--sell)'};">
                        <div class="stat-label" id="bars-stat-label-0">📊 最新收盘</div>
                        <div class="stat-value ${isUp ? 'stat-positive' : 'stat-negative'}" id="bars-stat-val-0">${formatNumber(latest.close, 2)}</div>
                        <div class="stat-sub" id="bars-stat-sub-0">
                            ${isUp ? TrendingUp({ size: 14 }) : TrendingDown({ size: 14 })}
                            ${isUp ? '+' : ''}${formatNumber(change, 2)} (${formatPct(changePct)})
                        </div>
                    </div>
                    <div class="stat-card" style="border-top:2px solid var(--primary);">
                        <div class="stat-label">📈 期间最高 / 📉 最低</div>
                        <div class="stat-value stat-neutral" style="font-size:18px;" id="bars-stat-val-1">
                            <span style="color:var(--buy);">${formatNumber(periodHigh, 2)}</span>
                            <span style="color:var(--text-muted);"> / </span>
                            <span style="color:var(--sell);">${formatNumber(periodLow, 2)}</span>
                        </div>
                        <div class="stat-sub" id="bars-stat-sub-1">区间振幅 ${formatPct((periodHigh - periodLow) / periodLow * 100)}</div>
                    </div>
                    <div class="stat-card" style="border-top:2px solid var(--info);">
                        <div class="stat-label">📋 开盘 / 最高 / 最低</div>
                        <div class="stat-value stat-neutral" style="font-size:16px;" id="bars-stat-val-2">
                            开 ${formatNumber(latest.open, 2)} ·
                            高 ${formatNumber(latest.high, 2)} ·
                            低 ${formatNumber(latest.low, 2)}
                        </div>
                    </div>
                    <div class="stat-card" style="border-top:2px solid var(--accent);">
                        <div class="stat-label" id="bars-stat-label-3">📦 成交量 / 成交额</div>
                        <div class="stat-value stat-neutral" style="font-size:16px;" id="bars-stat-val-3">
                            ${formatVolume(latest.volume)} · ${formatAmount(latest.amount)}
                        </div>
                    </div>
                </div>
                <p id="bars-stats-hint" style="font-size:11px;color:var(--text-muted);margin:-8px 0 8px 0;">
                    💡 点击 K线柱可切换查看具体日期数据
                </p>`;
            // 屏幕阅读器摘要（必须在 if 块内，因为 periodHigh/periodLow 在此作用域）
            const srSummaryId = 'bars-chart-summary';
            const srSummary = `${escapeHtml(data.symbol)} K线图：共${count}条日线数据，最新收盘价${latest.close}元，期间振幅${formatPct((periodHigh - periodLow) / periodLow * 100)}。`;

            const chartDom = document.getElementById('bars-chart');
            chartDom.setAttribute('aria-label', `${escapeHtml(data.symbol)} K线图`);
            chartDom.setAttribute('aria-describedby', srSummaryId);

            // 注入隐藏屏幕阅读器摘要
            if (!document.getElementById(srSummaryId)) {
                const srEl = document.createElement('div');
                srEl.id = srSummaryId;
                srEl.className = 'sr-only';
                srEl.textContent = srSummary;
                chartDom.parentNode.insertBefore(srEl, chartDom);
            }

            // 关闭 if 块
        } else {
            document.getElementById('bars-info').innerHTML = `
                <div class="error-banner" role="alert" style="margin:var(--space-4) 0;">
                    ⚠️ 未查询到 ${escapeHtml(data.symbol)} 的日线数据。${data.error ? escapeHtml(data.error) : ''}
                </div>`;
        }

        const chartDom = document.getElementById('bars-chart');
        if (count === 0) {
            chartDom.innerHTML = `<div class="empty-state-enhanced"><div class="empty-icon-bg">${File({ size: 32 })}</div><div class="empty-title">无数据可显示</div><div class="empty-desc">未查询到K线数据</div></div>`;
            document.getElementById('bars-table-container').innerHTML = '';
            return;
        }

        // 渲染图表（色盲友好：涨=实心填充，跌=空心描边）
        const stockName = data.stock_name || '';
        renderChart(bars, data.symbol, stockName);

        // 表格行高亮 & 点击回调数据暂存在 chartInstance 上
        if (chartInstance) {
            chartInstance._barsData = bars;
            chartInstance._selectedIdx = -1;
        }

        // 渲染表格
        document.getElementById('bars-table-container').innerHTML = `
            <div class="card" style="margin-top:var(--space-4);">
                <div class="card-header">
                    <span class="card-title">数据明细</span>
                    <span style="font-size:11px;color:var(--text-muted);">
                        ● 实心=涨 · ○ 空心=跌（色盲友好）
                    </span>
                </div>
                <div class="card-body">
                    <div class="table-container">
                        <table aria-label="日线数据明细">
                            <thead>
                                <tr>
                                    <th>日期</th>
                                    <th style="text-align:right;">开盘</th>
                                    <th style="text-align:right;">最高</th>
                                    <th style="text-align:right;">最低</th>
                                    <th style="text-align:right;">收盘</th>
                                    <th style="text-align:right;">涨跌</th>
                                    <th style="text-align:right;">成交量</th>
                                    <th style="text-align:right;">成交额</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${bars.map((b, i) => {
                                    const isUp = b.close >= b.open;
                                    const color = isUp ? 'var(--buy)' : 'var(--sell)';
                                    const prevClose = i > 0 ? bars[i - 1].close : b.open;
                                    const dayChange = b.close - prevClose;
                                    const dayChangePct = prevClose ? (dayChange / prevClose * 100) : 0;
                                    return `
                                    <tr>
                                        <td>${escapeHtml(b.date)}</td>
                                        <td style="text-align:right;">${formatNumber(b.open, 2)}</td>
                                        <td style="text-align:right;">${formatNumber(b.high, 2)}</td>
                                        <td style="text-align:right;">${formatNumber(b.low, 2)}</td>
                                        <td style="text-align:right; color:${color}; font-weight:600;">
                                            ${formatNumber(b.close, 2)}
                                            ${isUp ? '▲' : '▼'}
                                        </td>
                                        <td style="text-align:right; color:${dayChange >= 0 ? 'var(--buy)' : 'var(--sell)'};">
                                            ${formatPct(dayChangePct)}
                                        </td>
                                        <td style="text-align:right;">${formatVolume(b.volume)}</td>
                                        <td style="text-align:right;">${formatAmount(b.amount)}</td>
                                    </tr>`;
                                }).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;
    }

    function renderChart(bars, symbol, stockName) {
        const dom = document.getElementById('bars-chart');
        if (!dom || typeof echarts === 'undefined') return;

        if (chartInstance) {
            chartInstance.dispose();
        }

        chartInstance = echarts.init(dom, 'dark');

        const dates = bars.map(b => b.date);
        // [open, close, low, high]
        const ohlc = bars.map(b => [b.open, b.close, b.low, b.high]);
        const volumes = bars.map(b => b.volume);

        // 色盲友好配色 tokens（设计系统语义色 Hex）
        const BULL_COLOR = '#EF4444';   // 涨 — 实心填充
        const BEAR_COLOR = '#22C55E';   // 跌 — 空心描边
        const BULL_VOL = 'rgba(239,68,68,0.45)';
        const BEAR_VOL = 'rgba(34,197,94,0.45)';

        // 预处理: 标记每根K线的涨跌（用于色盲友好模式）
        const isBullish = ohlc.map(o => o[1] >= o[0]);

        const titleText = stockName
            ? `${symbol} ${stockName} 日线图`
            : `${symbol} 日线图`;

        const option = {
            title: {
                text: titleText,
                subtext: '实心 = 上涨 · 空心 = 下跌（色盲友好设计）',
                left: 'center',
                textStyle: { color: '#E2E8F0', fontSize: 14 },
                subtextStyle: { color: '#64748B', fontSize: 10 },
            },
            backgroundColor: '#1E293B',
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross' },
                backgroundColor: '#1A2332',
                borderColor: '#334155',
                textStyle: { color: '#E2E8F0', fontSize: 12 },
                formatter: function (params) {
                    const k = params.find(p => p.seriesName === 'K线');
                    const v = params.find(p => p.seriesName === '成交量');
                    if (!k) return '';
                    const idx = k.dataIndex;
                    // 数据是 { value: [o,c,l,h], itemStyle: {...} } 包装格式
                    const d = Array.isArray(k.data) ? k.data : (k.data.value || ohlc[idx]);
                    const isUp = isBullish[idx];
                    const prevClose = idx > 0 ? ohlc[idx - 1][1] : d[0];
                    const changePct = ((d[1] - prevClose) / prevClose * 100).toFixed(2);
                    return `<strong>${k.axisValue}</strong><br/>
                        开: ${formatNumber(d[0], 2)} &nbsp; 收: <span style="color:${isUp ? BULL_COLOR : BEAR_COLOR};font-weight:600;">${formatNumber(d[1], 2)}</span><br/>
                        高: ${formatNumber(d[3], 2)} &nbsp; 低: ${formatNumber(d[2], 2)}<br/>
                        涨跌: <span style="color:${isUp ? BULL_COLOR : BEAR_COLOR};">${changePct >= 0 ? '+' : ''}${changePct}%</span><br/>
                        量: ${v ? formatVolume(v.data && v.data.value !== undefined ? v.data.value : v.data) : '—'}`;
                },
            },
            grid: [
                { left: '10%', right: '8%', top: '18%', height: '52%' },
                { left: '10%', right: '8%', top: '75%', height: '15%' },
            ],
            xAxis: [
                {
                    type: 'category',
                    data: dates,
                    gridIndex: 0,
                    axisLine: { lineStyle: { color: '#334155' } },
                    axisLabel: { color: '#94A3B8', fontSize: 11 },
                    boundaryGap: true,
                },
                {
                    type: 'category',
                    data: dates,
                    gridIndex: 1,
                    axisLine: { lineStyle: { color: '#334155' } },
                    axisLabel: { show: false },
                    boundaryGap: true,
                },
            ],
            yAxis: [
                {
                    type: 'value',
                    gridIndex: 0,
                    scale: true,
                    splitLine: { lineStyle: { color: '#1E293B' } },
                    axisLabel: { color: '#94A3B8', fontSize: 11 },
                },
                {
                    type: 'value',
                    gridIndex: 1,
                    scale: true,
                    splitLine: { show: false },
                    axisLabel: { color: '#94A3B8', fontSize: 10 },
                },
            ],
            series: [
                {
                    name: 'K线',
                    type: 'candlestick',
                    data: ohlc.map((o, i) => {
                        const bullish = isBullish[i];
                        return {
                            value: o,
                            itemStyle: {
                                // 色盲友好: 涨=实心填充, 跌=透明空心+粗描边
                                color: bullish ? BULL_COLOR : 'transparent',
                                color0: bullish ? BULL_COLOR : 'transparent',
                                borderColor: bullish ? BULL_COLOR : BEAR_COLOR,
                                borderColor0: bullish ? BULL_COLOR : BEAR_COLOR,
                                borderWidth: bullish ? 1 : 2,
                            },
                        };
                    }),
                    xAxisIndex: 0,
                    yAxisIndex: 0,
                },
                {
                    name: '成交量',
                    type: 'bar',
                    data: volumes.map((v, i) => ({
                        value: v,
                        itemStyle: {
                            color: isBullish[i] ? BULL_VOL : BEAR_VOL,
                        },
                    })),
                    xAxisIndex: 1,
                    yAxisIndex: 1,
                },
            ],
        };

        chartInstance.setOption(option);

        // 存储引用供外部使用
        dom.__chartInstance = chartInstance;

        // ★ 点击 K 线柱 → 更新摘要面板
        chartInstance.off('click');
        chartInstance.on('click', function (params) {
            if (params.seriesName === 'K线' && params.dataIndex != null) {
                const idx = params.dataIndex;
                if (chartInstance._selectedIdx === idx) {
                    // 取消选中 = 恢复最新
                    chartInstance._selectedIdx = -1;
                    updateStatsPanel(bars, -1);
                    highlightTableRow(-1);
                    dom.style.cursor = 'crosshair';
                    chartInstance.dispatchAction({ type: 'downplay', seriesIndex: 0 });
                } else {
                    chartInstance._selectedIdx = idx;
                    updateStatsPanel(bars, idx);
                    highlightTableRow(idx);
                    dom.style.cursor = 'pointer';
                    // 高亮选中的 K线
                    chartInstance.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex: idx });
                }
            }
        });

        dom.style.cursor = 'crosshair';

        const resizeHandler = () => chartInstance?.resize();
        window.addEventListener('resize', resizeHandler);
    }

    /**
     * 更新摘要面板为指定日期数据
     * @param {Array} bars - 全部日线数据
     * @param {number} idx - 选中的索引，-1 表示恢复显示最新
     */
    function updateStatsPanel(bars, idx) {
        const _ = window.Icon || {};
        const TrendingUp = _.trendingUp || (() => '');
        const TrendingDown = _.trendingDown || (() => '');
        const Refresh = _.refresh || (() => '');

        const isLatest = idx < 0 || idx >= bars.length - 1;
        const bar = isLatest ? bars[bars.length - 1] : bars[idx];
        const prev = idx > 0 ? bars[idx - 1] : bars[0];
        const change = bar.close - prev.close;
        const changePct = prev.close !== 0 ? (change / prev.close * 100) : 0;
        const isUp = change >= 0;

        // 卡片 0: 收盘价
        const label0 = document.getElementById('bars-stat-label-0');
        const val0 = document.getElementById('bars-stat-val-0');
        const sub0 = document.getElementById('bars-stat-sub-0');
        if (label0) label0.textContent = isLatest ? '最新收盘' : bar.date + ' 收盘';
        if (val0) {
            val0.className = 'stat-value ' + (isUp ? 'stat-positive' : 'stat-negative');
            val0.textContent = formatNumber(bar.close, 2);
        }
        if (sub0) {
            sub0.innerHTML = (isUp ? TrendingUp({ size: 14 }) : TrendingDown({ size: 14 }))
                + ' ' + (isUp ? '+' : '') + formatNumber(change, 2)
                + ' (' + formatPct(changePct) + ')';
        }

        // 卡片 1: 期间最高/最低 — 保持全局不变

        // 卡片 2: 开盘/最高/最低
        const val2 = document.getElementById('bars-stat-val-2');
        if (val2) {
            val2.innerHTML = '开 ' + formatNumber(bar.open, 2)
                + ' · 高 ' + formatNumber(bar.high, 2)
                + ' · 低 ' + formatNumber(bar.low, 2);
        }

        // 卡片 3: 成交量/成交额
        const label3 = document.getElementById('bars-stat-label-3');
        const val3 = document.getElementById('bars-stat-val-3');
        if (label3) label3.textContent = isLatest ? '成交量 / 成交额' : bar.date + ' 成交量 / 成交额';
        if (val3) val3.textContent = formatVolume(bar.volume) + ' · ' + formatAmount(bar.amount);

        // 提示文字 + 返回最新按钮
        const hint = document.getElementById('bars-stats-hint');
        if (hint) {
            if (isLatest) {
                hint.innerHTML = '💡 点击 K线柱可切换查看具体日期数据';
            } else {
                hint.innerHTML = '📌 已选中 <strong>' + bar.date + '</strong> · 再次点击 K线取消选中 或 '
                    + '<button id="bars-reset-btn" style="background:none;border:none;color:var(--accent);cursor:pointer;font-size:11px;text-decoration:underline;padding:0;">'
                    + Refresh({ size: 12 }) + ' 返回最新</button>';
                // 绑定"返回最新"按钮
                setTimeout(() => {
                    const resetBtn = document.getElementById('bars-reset-btn');
                    if (resetBtn) {
                        resetBtn.onclick = function () {
                            const dom = document.getElementById('bars-chart');
                            const ci = dom && dom.__chartInstance;
                            if (ci) {
                                ci._selectedIdx = -1;
                                ci.dispatchAction({ type: 'downplay', seriesIndex: 0 });
                                dom.style.cursor = 'crosshair';
                            }
                            updateStatsPanel(bars, -1);
                            highlightTableRow(-1);
                        };
                    }
                }, 0);
            }
        }
    }

    /**
     * 高亮数据表中对应行，-1 表示清除所有高亮
     */
    function highlightTableRow(idx) {
        const table = document.querySelector('#bars-table-container table tbody');
        if (!table) return;
        const rows = table.querySelectorAll('tr');
        rows.forEach((row, i) => {
            if (i === idx) {
                row.style.background = 'rgba(139,92,246,0.12)';
                row.style.outline = '1px solid var(--accent)';
                row.style.outlineOffset = '-1px';
                row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            } else {
                row.style.background = '';
                row.style.outline = '';
                row.style.outlineOffset = '';
            }
        });
    }

    // 注册路由
    if (typeof Router !== 'undefined') {
        Router.register('/bars', render);
    }
})();
