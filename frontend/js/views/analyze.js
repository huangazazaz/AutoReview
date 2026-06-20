/**
 * 单股分析视图 — 对单只股票进行策略回测，查看详细指标和交易记录
 */
(function () {
    'use strict';

    console.log('[analyze] 模块加载 v2');

    let chartInstance = null;

    async function render(container) {
        const _ = window.Icon || {};
        const Search = _.search || (() => '');
        const Rocket = _.rocket || (() => '');
        const Loader = _.loader || (() => '');
        const TrendingUp = _.trendingUp || (() => '');
        const TrendingDown = _.trendingDown || (() => '');
        const File = _.folder || (() => '');
        const XCircle = _.xCircle || (() => '');

        // 清理旧图表
        if (chartInstance) { chartInstance.dispose(); chartInstance = null; }

        container.innerHTML = `
            <div class="page-header">
                <h1 class="page-title">${Search({ size: 24 })} 单股分析</h1>
                <p class="page-subtitle">选择股票和策略，运行回测查看详细指标与交易记录</p>
            </div>

            <!-- 表单 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">回测参数</span>
                </div>
                <div class="card-body">
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label" for="analyze-symbol">股票代码 <span class="required" aria-hidden="true">*</span><span class="sr-only">必填</span></label>
                            <div class="input-with-clear">
                                <input type="text" class="form-input" id="analyze-symbol"
                                    placeholder="如 600522, 000001" maxlength="6" autofocus autocomplete="off"
                                    list="analyze-symbol-list">
                                <button type="button" class="input-clear-btn" id="analyze-symbol-clear"
                                    title="清空" aria-label="清空股票代码" tabindex="-1">&times;</button>
                            </div>
                            <datalist id="analyze-symbol-list"></datalist>
                        </div>
                        <div class="form-group">
                            <label class="form-label" for="analyze-strategy">策略</label>
                            <select class="form-select" id="analyze-strategy"></select>
                        </div>
                        <div class="form-group">
                            <label class="form-label" for="analyze-period">周期</label>
                            <select class="form-select" id="analyze-period">
                                <option value="1y">最近 1 年</option>
                                <option value="6m">最近 6 个月</option>
                                <option value="3m">最近 3 个月</option>
                                <option value="20d">最近 20 天</option>
                                <option value="60t">最近 60 交易日</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label class="form-label" for="analyze-datasource">数据源</label>
                            <select class="form-select" id="analyze-datasource">
                                <option value="">自动（主备降级）</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label" for="analyze-start">开始日期</label>
                            <input type="text" class="form-input date-input" id="analyze-start"
                                placeholder="开始日期" autocomplete="off"
                                onfocus="this.type='date';this.showPicker?.()" onblur="if(!this.value)this.type='text'">
                        </div>
                        <div class="form-group">
                            <label class="form-label" for="analyze-end">结束日期</label>
                            <input type="text" class="form-input date-input" id="analyze-end"
                                placeholder="结束日期" autocomplete="off"
                                onfocus="this.type='date';this.showPicker?.()" onblur="if(!this.value)this.type='text'">
                        </div>
                        <div class="form-group" style="display:flex; align-items:flex-end;">
                            <button class="btn btn-primary" id="analyze-submit" style="width:100%;">
                                ${Rocket({ size: 18 })} 开始回测
                            </button>
                        </div>
                    </div>

                    <!-- 策略参数 - 独立可折叠区域 -->
                    <div class="params-section" id="analyze-params-panel" style="display:none;">
                        <button type="button" class="params-toggle" id="analyze-params-toggle" aria-expanded="false">
                            <span class="toggle-icon">&#9654;</span> 策略参数
                            <span class="params-summary" id="analyze-params-summary"></span>
                        </button>
                        <div class="params-body" id="analyze-params-body" style="display:none;">
                            <div id="analyze-params" class="strategy-params"></div>
                        </div>
                    </div>

                    <p class="form-hint">
                        提示：开始/结束日期优先于周期；留空则使用周期参数
                    </p>
                </div>
            </div>

            <!-- 结果区 -->
            <div id="analyze-results"></div>
        `;

        // 加载策略、数据源和缓存股票列表
        const [strategiesData, datasourcesData, cachedData] = await Promise.allSettled([
            API.getStrategies(),
            API.getDatasources(),
            API.getCachedStocks(),
        ]);

        const strategySelect = document.getElementById('analyze-strategy');
        let strategiesList = [];
        if (strategiesData.status === 'fulfilled') {
            strategiesList = strategiesData.value.strategies || [];
            strategySelect.innerHTML = strategiesList
                .map(s => {
                    const name = typeof s === 'string' ? s : s.name;
                    return `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`;
                }).join('');
        } else {
            strategySelect.innerHTML = '<option value="ma_cross">ma_cross</option><option value="macd_divergence">macd_divergence</option>';
        }

        // 策略参数面板
        const paramPanel = document.getElementById('analyze-params-panel');
        const paramContainer = document.getElementById('analyze-params');
        const paramToggle = document.getElementById('analyze-params-toggle');
        const paramBody = document.getElementById('analyze-params-body');

        if (strategiesList.length > 0 && paramContainer) {
            renderAnalyzeParams(strategiesList, strategySelect.value, paramContainer, paramPanel, paramBody, paramToggle);
        }
        strategySelect.addEventListener('change', () => {
            if (strategiesList.length > 0 && paramContainer) {
                renderAnalyzeParams(strategiesList, strategySelect.value, paramContainer, paramPanel, paramBody, paramToggle);
            }
        });

        // 参数面板折叠/展开切换
        if (paramToggle) {
            paramToggle.addEventListener('click', () => {
                const expanded = paramToggle.getAttribute('aria-expanded') === 'true';
                paramToggle.setAttribute('aria-expanded', String(!expanded));
                paramToggle.querySelector('.toggle-icon').innerHTML = expanded ? '&#9654;' : '&#9660;';
                paramBody.style.display = expanded ? 'none' : '';
            });
        }

        // 缓存股票 datalist（输入时自动补全）
        const datalist = document.getElementById('analyze-symbol-list');
        if (cachedData.status === 'fulfilled' && cachedData.value.symbols && cachedData.value.symbols.length) {
            datalist.innerHTML = cachedData.value.symbols.map(s => {
                const namePart = s.name ? ` ${s.name}` : '';
                return `<option value="${escapeHtml(s.symbol)}">${escapeHtml(s.symbol)}${escapeHtml(namePart)} — ${s.last_close != null ? '¥' + formatNumber(s.last_close, 2) : ''} (${s.bars || 0}条)</option>`;
            }).join('');
        }

        const dsSelect = document.getElementById('analyze-datasource');
        if (datasourcesData.status === 'fulfilled') {
            dsSelect.innerHTML += datasourcesData.value.datasources
                .map(d => `<option value="${escapeHtml(d)}">${escapeHtml(d)}</option>`).join('');
        }

        // 股票代码输入框快捷清空
        const symbolInput = document.getElementById('analyze-symbol');
        const symbolClear = document.getElementById('analyze-symbol-clear');
        if (symbolInput && symbolClear) {
            const toggleClearBtn = () => {
                symbolClear.classList.toggle('visible', !!symbolInput.value);
            };
            symbolInput.addEventListener('input', toggleClearBtn);
            symbolClear.addEventListener('click', () => {
                symbolInput.value = '';
                symbolClear.classList.remove('visible');
                symbolInput.focus();
            });
            toggleClearBtn();
        }

        // 提交事件
        document.getElementById('analyze-submit').addEventListener('click', submitAnalysis);
        document.getElementById('analyze-symbol').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') submitAnalysis();
        });

        async function submitAnalysis() {
            const symbol = document.getElementById('analyze-symbol').value.trim();
            if (!symbol) { showToast('请输入股票代码', 'warning'); return; }

            const params = {
                symbol: symbol,
                strategy: document.getElementById('analyze-strategy').value,
                period: document.getElementById('analyze-period').value,
            };
            const ds = document.getElementById('analyze-datasource').value;
            if (ds) params.datasource = ds;
            const start = document.getElementById('analyze-start').value;
            const end = document.getElementById('analyze-end').value;
            if (start) params.start = start;
            if (end) params.end = end;
            if (start || end) delete params.period;

            // 收集策略参数覆盖值
            const paramInputs = document.querySelectorAll('#analyze-params .param-input');
            if (paramInputs.length > 0) {
                const strategyParams = {};
                paramInputs.forEach(input => {
                    const key = input.dataset.paramKey;
                    const type = input.dataset.paramType;
                    let val = input.value.trim();
                    if (val === '') return;  // 跳过空值，使用默认
                    if (type === 'int') val = parseInt(val, 10);
                    else if (type === 'float') val = parseFloat(val);
                    else if (type === 'list') {
                        try { val = JSON.parse(val); } catch(e) { return; }
                    }
                    strategyParams[key] = val;
                });
                if (Object.keys(strategyParams).length > 0) {
                    params.strategy_params = strategyParams;
                }
            }

            const btn = document.getElementById('analyze-submit');
            btn.disabled = true;
            btn.innerHTML = `${Loader({ size: 18 })} 回测中...`;
            showLoading('正在运行回测...');

            console.log('[analyze] 开始回测...', params.symbol, params.strategy);
            const data = await safeAsync(() => API.analyze(params), '回测失败');
            console.log('[analyze] 回测结果:', data ? 'success' : 'failed', 'equity_curve长度:', data?.equity_curve?.length || 0);

            // 获取日线价格数据用于叠加股价折线（回测完成后获取，确保时间范围一致）
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
        }
    }

    function renderResults(data, bars = []) {
        console.log('[analyze] renderResults 调用, bars长度:', bars.length);
        const _ = window.Icon || {};
        const TrendingUp = _.trendingUp || (() => '');
        const TrendingDown = _.trendingDown || (() => '');
        const File = _.folder || (() => '');
        const XCircle = _.xCircle || (() => '');
        const Chart = _.chart || (() => '');

        const m = data.metrics || {};
        const trades = data.trades || [];
        const equityCurve = data.equity_curve || [];
        const ret = m.total_return_pct || 0;
        const isPositive = ret >= 0;

        // 计算交易汇总
        let totalBuyAmount = 0, totalSellAmount = 0;
        let totalCommission = 0, totalStampDuty = 0;
        trades.forEach(t => {
            const amt = t.price * t.quantity;
            if (t.action === 'BUY') totalBuyAmount += amt;
            else totalSellAmount += amt;
            totalCommission += t.commission || 0;
            totalStampDuty += t.stamp_duty || 0;
        });

        const stockDisplay = data.stock_name
            ? `${escapeHtml(data.symbol)} <span style="color:var(--text-secondary);font-weight:400;">${escapeHtml(data.stock_name)}</span>`
            : escapeHtml(data.symbol);

        document.getElementById('analyze-results').innerHTML = `
            <!-- 股票名称标题 -->
            <div style="margin:var(--space-4) 0 var(--space-2);">
                <span style="font-size:20px;font-weight:700;color:var(--text-bright);">${stockDisplay}</span>
                <span style="font-size:13px;color:var(--text-muted);margin-left:8px;">回测结果</span>
            </div>

            <!-- 核心指标卡片 -->
            <div class="stats-grid" style="margin-top:var(--space-4);" role="status" aria-label="回测核心指标">
                <div class="stat-card">
                    <div class="stat-label">总收益率</div>
                    <div class="stat-value ${isPositive ? 'stat-positive' : 'stat-negative'}">${formatPct(ret)}</div>
                    <div class="stat-sub">初始 ${formatAmount(m.initial_capital)} → 终值 ${formatAmount(m.final_equity)}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">胜率</div>
                    <div class="stat-value stat-neutral">${formatPct(m.win_rate)}</div>
                    <div class="stat-sub">按持仓周期统计</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">最大回撤</div>
                    <div class="stat-value stat-negative">${formatPct(m.max_drawdown_pct)}</div>
                    <div class="stat-sub">从最高点计算</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">夏普比率</div>
                    <div class="stat-value ${(m.sharpe_ratio || 0) >= 0 ? 'stat-positive' : 'stat-negative'}">${formatNumber(m.sharpe_ratio)}</div>
                    <div class="stat-sub">年化风险调整收益</div>
                </div>
            </div>

            <!-- 第二行：交易概况 -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">总交易笔数</div>
                    <div class="stat-value stat-neutral">${m.total_trades || 0}</div>
                    <div class="stat-sub">
                        买 <span style="color:var(--buy);">${m.buy_trades || 0}</span> ·
                        卖 <span style="color:var(--sell);">${m.sell_trades || 0}</span> ·
                        信号 <span style="color:var(--info);">${data.signal_count || 0}</span>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">买入总额 / 卖出总额</div>
                    <div class="stat-value stat-neutral" style="font-size:18px;">
                        <span style="color:var(--buy);">${formatAmount(totalBuyAmount)}</span>
                        <span style="color:var(--text-muted);"> / </span>
                        <span style="color:var(--sell);">${formatAmount(totalSellAmount)}</span>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">总佣金 / 总印花税</div>
                    <div class="stat-value stat-neutral" style="font-size:18px;">
                        ${formatAmount(totalCommission)} / ${formatAmount(totalStampDuty)}
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">净收益</div>
                    <div class="stat-value ${isPositive ? 'stat-positive' : 'stat-negative'}">
                        ${formatAmount((m.final_equity || 0) - (m.initial_capital || 0))}
                    </div>
                    <div class="stat-sub">${isPositive ? '盈利' : '亏损'}（含税费）</div>
                </div>
            </div>

            <!-- 净值曲线图 -->
            ${equityCurve.length > 0 ? `
            <div class="card">
                <div class="card-header">
                    <span class="card-title">${Chart({ size: 18 })} 净值曲线</span>
                    <span style="font-size:12px;color:var(--text-muted);">${escapeHtml(data.symbol)} ${escapeHtml(data.stock_name || '')}</span>
                </div>
                <div class="card-body" style="padding:0;">
                    <div class="chart-container large" id="analyze-equity-chart" role="img" aria-label="净值曲线图 — ${escapeHtml(data.symbol)}"></div>
                </div>
            </div>` : ''}

            <!-- 交易记录 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">交易记录</span>
                    <span style="font-size:12px;color:var(--text-muted);">共 ${trades.length} 笔 · 点击行可查看信号原因</span>
                </div>
                <div class="card-body" style="padding:0;">
                    ${trades.length === 0 ? `<div class="empty-state" style="padding:var(--space-8);"><span class="empty-icon">${File({ size: 48 })}</span><p>暂无交易记录</p></div>` : `
                    <div class="table-container" style="border:none;">
                        <table aria-label="交易记录明细">
                            <thead>
                                <tr>
                                    <th>日期</th>
                                    <th>操作</th>
                                    <th style="text-align:right;">成交价</th>
                                    <th style="text-align:right;">数量</th>
                                    <th style="text-align:right;">成交金额</th>
                                    <th style="text-align:right;">佣金</th>
                                    <th style="text-align:right;">印花税</th>
                                    <th style="text-align:right;">持仓</th>
                                    <th style="text-align:right;">现金</th>
                                    <th style="text-align:right;">总资产</th>
                                    <th>触发原因</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${trades.map(t => {
                                    const isBuy = t.action === 'BUY';
                                    const amount = t.price * t.quantity;
                                    const reason = t.reason || '';
                                    // 简短原因标签
                                    let reasonTag = reason;
                                    if (reason.includes('金叉')) reasonTag = '金叉';
                                    else if (reason.includes('死叉')) reasonTag = '死叉';
                                    else if (reason.includes('止盈')) reasonTag = '止盈';
                                    else if (reason.includes('止损')) reasonTag = '止损';
                                    else if (reason.includes('回撤')) reasonTag = '回撤';
                                    else if (reason.includes('加仓') || reason.includes('批次')) reasonTag = '加仓';
                                    else if (reason.includes('底背离')) reasonTag = '底背离';
                                    else if (reason.includes('顶背离')) reasonTag = '顶背离';
                                    return `
                                    <tr title="${escapeHtml(reason)}">
                                        <td>${escapeHtml(t.date)}</td>
                                        <td><span class="badge ${isBuy ? 'badge-buy' : 'badge-sell'}">${isBuy ? 'BUY' : 'SELL'}</span></td>
                                        <td style="text-align:right;">${formatNumber(t.price, 2)}</td>
                                        <td style="text-align:right;">${formatVolume(t.quantity)}</td>
                                        <td style="text-align:right; color:${isBuy ? 'var(--buy)' : 'var(--sell)'};">${formatAmount(amount)}</td>
                                        <td style="text-align:right;">${formatNumber(t.commission, 2)}</td>
                                        <td style="text-align:right;">${formatNumber(t.stamp_duty, 2)}</td>
                                        <td style="text-align:right; font-weight:600;">${formatVolume(t.position)}</td>
                                        <td style="text-align:right;">${formatAmount(t.cash)}</td>
                                        <td style="text-align:right; font-weight:600;">${formatAmount(t.total_equity)}</td>
                                        <td style="font-size:12px; max-width:140px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;"
                                            title="${escapeHtml(reason)}">${escapeHtml(reasonTag)}</td>
                                    </tr>`;
                                }).join('')}
                            </tbody>
                        </table>
                    </div>`}
                </div>
            </div>
        `;

        // 渲染净值曲线图
        if (equityCurve.length > 0 && typeof echarts !== 'undefined') {
            renderEquityChart(equityCurve, data.symbol, data.stock_name, m.initial_capital || 0, bars, trades);
        }
    }

    function renderEquityChart(curve, symbol, stockName, initialCapital, bars = [], trades = []) {
        console.log('[analyze] renderEquityChart 调用, curve长度:', curve.length, 'bars长度:', bars.length, 'trades长度:', trades.length);
        const dom = document.getElementById('analyze-equity-chart');
        if (!dom) return;

        if (chartInstance) chartInstance.dispose();

        const dates = curve.map(p => p.date);
        const equities = curve.map(p => p.equity);

        // 计算回撤
        let peak = equities[0];
        const drawdowns = equities.map(e => {
            if (e > peak) peak = e;
            return ((e - peak) / peak * 100);
        });

        const baseline = new Array(dates.length).fill(initialCapital);

        // 提取收盘价（按日期对齐，避免索引偏移）
        const closeByDate = Object.create(null);
        for (const bar of bars) {
            if (bar.close != null) closeByDate[bar.date] = bar.close;
        }
        const closes = dates.map(d => closeByDate[d] ?? null);
        const hasClosePrice = closes.some(v => v != null);

        // 诊断日志：排查价格线不显示的原因
        console.log('[analyze] bars count:', bars.length, 'equity curve points:', dates.length);
        if (bars.length > 0) {
            console.log('[analyze] first bar date:', bars[0]?.date, 'close:', bars[0]?.close);
            console.log('[analyze] first equity date:', dates[0]);
            console.log('[analyze] hasClosePrice:', hasClosePrice, 'matched closes:', closes.filter(v => v != null).length);
            if (!hasClosePrice) {
                console.warn('[analyze] 日期对齐失败！bars日期样本:', bars.slice(0, 3).map(b => b.date),
                    'equity日期样本:', dates.slice(0, 3));
            }
        } else {
            console.warn('[analyze] bars数据为空，无法叠加股价折线');
        }

        // 构建日期→净值映射，用于买卖点定位
        const equityByDate = Object.create(null);
        dates.forEach((d, i) => { equityByDate[d] = equities[i]; });

        // 提取买卖点坐标
        const buyPoints = [];
        const sellPoints = [];
        trades.forEach(t => {
            const eq = equityByDate[t.date];
            if (eq == null) return;
            if (t.action === 'BUY') {
                buyPoints.push([t.date, eq]);
            } else if (t.action === 'SELL') {
                sellPoints.push([t.date, eq]);
            }
        });
        const hasTradeMarkers = buyPoints.length > 0 || sellPoints.length > 0;
        console.log('[analyze] 买卖点: 买入', buyPoints.length, '卖出', sellPoints.length);
        if (buyPoints.length > 0) console.log('[analyze] 首个买入点:', buyPoints[0]);
        if (sellPoints.length > 0) console.log('[analyze] 首个卖出点:', sellPoints[0]);

        // 计算摘要数据
        const finalEquity = equities[equities.length - 1];
        const totalReturn = initialCapital > 0 ? ((finalEquity - initialCapital) / initialCapital * 100) : 0;
        const maxDD = Math.min(...drawdowns);
        const maxEquity = Math.max(...equities);

        chartInstance = echarts.init(dom, 'dark');

        const option = {
            title: {
                text: `${symbol}${stockName ? ' ' + stockName : ''} 净值曲线`,
                subtext: `基准线 = 虚线 · 净值 = 紫色实线 · 股价 = 橙色实线 · 回撤 = 绿色区域` + (bars.length > 0 && !hasClosePrice ? ' ⚠️ 价格数据日期未对齐' : '') + (bars.length === 0 ? ' ℹ️ 未加载价格数据' : ''),
                left: 'center',
                textStyle: { color: '#E2E8F0', fontSize: 13, fontWeight: 600 },
                subtextStyle: { color: '#64748B', fontSize: 10 },
            },
            backgroundColor: '#1E293B',
            // 图例（色盲友好：每条线都有文字标签）
            legend: {
                data: ['基准', '净值', '回撤', ...(hasClosePrice ? ['收盘价'] : []), ...(hasTradeMarkers ? ['买入', '卖出'] : [])],
                bottom: 0,
                textStyle: { color: '#94A3B8', fontSize: 11 },
            },
            tooltip: {
                trigger: 'axis',
                backgroundColor: '#1A2332',
                borderColor: '#334155',
                textStyle: { color: '#E2E8F0', fontSize: 12 },
                formatter: function (params) {
                    const date = params[0].axisValue;
                    let html = `<strong>${date}</strong><br/>`;
                    params.forEach(p => {
                        if (p.seriesName === '净值') html += `💰 净值: <strong>${formatAmount(p.value)}</strong><br/>`;
                        if (p.seriesName === '基准') html += `📏 基准: ${formatAmount(p.value)}<br/>`;
                    });
                    const dd = drawdowns[params[0].dataIndex];
                    const ddColor = dd === 0 ? '#94A3B8' : '#22C55E';
                    html += `📉 回撤: <span style="color:${ddColor};font-weight:600;">${dd.toFixed(2)}%</span>`;
                    if (hasClosePrice) {
                        const closeVal = closes[params[0].dataIndex];
                        if (closeVal != null) {
                            html += `<br/>📊 收盘价: <span style="color:#F59E0B;font-weight:600;">${closeVal.toFixed(2)}</span>`;
                        }
                    }
                    return html;
                },
            },
            grid: [
                { left: '8%', right: '8%', top: '18%', height: '50%', bottom: '10%' },
                { left: '8%', right: '8%', top: '73%', height: '15%', bottom: '10%' },
            ],
            xAxis: [
                {
                    type: 'category',
                    data: dates,
                    gridIndex: 0,
                    axisLine: { lineStyle: { color: '#334155' } },
                    axisLabel: { color: '#94A3B8', fontSize: 10, rotate: dates.length > 30 ? 30 : 0 },
                    boundaryGap: false,
                },
                {
                    type: 'category',
                    data: dates,
                    gridIndex: 1,
                    axisLine: { lineStyle: { color: '#334155' } },
                    axisLabel: { show: false },
                    boundaryGap: false,
                },
            ],
            yAxis: [
                {
                    type: 'value',
                    gridIndex: 0,
                    scale: true,
                    splitLine: { lineStyle: { color: '#1E293B' } },
                    axisLabel: {
                        color: '#94A3B8',
                        fontSize: 11,
                        formatter: v => (v / 10000).toFixed(0) + '万',
                    },
                    name: '净值 (万元)',
                    nameTextStyle: { color: '#64748B', fontSize: 10 },
                },
                {
                    type: 'value',
                    gridIndex: 1,
                    scale: true,
                    splitLine: { show: false },
                    axisLabel: {
                        color: '#94A3B8',
                        fontSize: 10,
                        formatter: '{value}%',
                    },
                    name: '回撤 (%)',
                    nameTextStyle: { color: '#64748B', fontSize: 10 },
                },
                {
                    type: 'value',
                    gridIndex: 0,
                    position: 'right',
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
            ],
            series: [
                {
                    name: '基准',
                    type: 'line',
                    data: baseline,
                    xAxisIndex: 0,
                    yAxisIndex: 0,
                    // ★ 线型区分: 虚线（色盲友好）
                    lineStyle: { color: '#64748B', type: 'dashed', width: 1.5, dashOffset: 2 },
                    itemStyle: { color: '#64748B' },
                    symbol: 'none',
                    z: 1,
                },
                {
                    name: '净值',
                    type: 'line',
                    data: equities,
                    xAxisIndex: 0,
                    yAxisIndex: 0,
                    // ★ 线型区分: 实线
                    lineStyle: { color: '#8B5CF6', type: 'solid', width: 2.5 },
                    itemStyle: { color: '#8B5CF6' },
                    symbol: 'none',
                    areaStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: 'rgba(139,92,246,0.22)' },
                            { offset: 1, color: 'rgba(139,92,246,0.01)' },
                        ]),
                    },
                    // ★ 标记最高/最低点
                    markPoint: equities.length > 5 ? {
                        data: [
                            { type: 'max', name: '最高', symbol: 'pin', symbolSize: 40,
                              itemStyle: { color: '#F59E0B' },
                              label: { color: '#F59E0B', fontSize: 11, fontWeight: 600,
                                        formatter: p => formatAmount(p.value) } },
                                    { type: 'min', name: '最低', symbol: 'pin', symbolSize: 40,
                                      itemStyle: { color: '#EF4444' },
                                      label: { color: '#EF4444', fontSize: 11, fontWeight: 600,
                                        formatter: p => formatAmount(p.value) } },
                        ],
                    } : undefined,
                    z: 2,
                },
                {
                    name: '回撤',
                    type: 'line',
                    data: drawdowns,
                    xAxisIndex: 1,
                    yAxisIndex: 1,
                    // ★ 线型区分: 点线
                    lineStyle: { color: '#22C55E', type: 'dotted', width: 1.5 },
                    itemStyle: { color: '#22C55E' },
                    symbol: 'none',
                    areaStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: 'rgba(34,197,94,0.18)' },
                            { offset: 1, color: 'rgba(34,197,94,0.0)' },
                        ]),
                    },
                    z: 1,
                },
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
                ...(hasTradeMarkers ? [{
                    name: '买入',
                    type: 'scatter',
                    data: buyPoints,
                    xAxisIndex: 0,
                    yAxisIndex: 0,
                    encode: { x: 0, y: 1 },
                    symbol: 'triangle',
                    symbolSize: 14,
                    symbolRotate: 0,
                    itemStyle: { color: '#EF4444' },
                    label: { show: true, position: 'top', color: '#EF4444', fontSize: 10, fontWeight: 600,
                             formatter: 'B' },
                    z: 10,
                }, {
                    name: '卖出',
                    type: 'scatter',
                    data: sellPoints,
                    xAxisIndex: 0,
                    yAxisIndex: 0,
                    encode: { x: 0, y: 1 },
                    symbol: 'triangle',
                    symbolSize: 14,
                    symbolRotate: 180,
                    itemStyle: { color: '#22C55E' },
                    label: { show: true, position: 'bottom', color: '#22C55E', fontSize: 10, fontWeight: 600,
                             formatter: 'S' },
                    z: 10,
                }] : []),
            ],
        };

        chartInstance.setOption(option);

        // 屏幕阅读器摘要
        const srSummaryId = 'analyze-equity-summary';
        const nonNullCloses = closes.filter(v => v != null);
        const closeInfo = nonNullCloses.length > 0
            ? `，股价从${nonNullCloses[0].toFixed(2)}到${nonNullCloses[nonNullCloses.length - 1].toFixed(2)}`
            : '';
        const srSummary = `${symbol}${stockName ? ' ' + stockName : ''} 净值曲线图：初始资金${formatAmount(initialCapital)}，最终净值${formatAmount(finalEquity)}，总收益率${formatPct(totalReturn)}，最大回撤${formatPct(maxDD)}，期间最高净值${formatAmount(maxEquity)}${closeInfo}。`;

        dom.setAttribute('aria-describedby', srSummaryId);
        let srEl = document.getElementById(srSummaryId);
        if (!srEl) {
            srEl = document.createElement('div');
            srEl.id = srSummaryId;
            srEl.className = 'sr-only';
            srEl.setAttribute('role', 'status');
            dom.parentNode.insertBefore(srEl, dom);
        }
        srEl.textContent = srSummary;

        const resizeHandler = () => chartInstance?.resize();
        window.addEventListener('resize', resizeHandler);
    }

    /**
     * 渲染策略参数编辑表单（独立可折叠面板）
     */
    function renderAnalyzeParams(strategiesList, strategyName, container, panel, body, toggle) {
        const strategy = strategiesList.find(s => (typeof s === 'string' ? s : s.name) === strategyName);

        if (!strategy || typeof strategy === 'string' || !strategy.param_schema) {
            if (panel) panel.style.display = 'none';
            container.innerHTML = '';
            return;
        }

        const schema = strategy.param_schema;
        const values = strategy.params || {};
        const entries = Object.entries(schema);

        if (entries.length === 0) {
            if (panel) panel.style.display = 'none';
            container.innerHTML = '';
            return;
        }

        // 显示面板
        if (panel) panel.style.display = '';

        // 更新摘要（显示当前参数值概览）
        const summaryEl = document.getElementById('analyze-params-summary');
        if (summaryEl) {
            const summaryParts = entries.slice(0, 5).map(([k]) => {
                const v = values[k] !== undefined ? values[k] : (schema[k].default !== undefined ? schema[k].default : '—');
                const displayVal = typeof v === 'object' ? JSON.stringify(v) : String(v);
                return `${k}=${displayVal}`;
            });
            const more = entries.length > 5 ? ` +${entries.length - 5}` : '';
            summaryEl.textContent = summaryParts.join(', ') + more;
        }

        // 简单类型参数用单行输入，复杂类型用 JSON textarea
        const simpleTypes = ['int', 'float', 'str', 'bool'];
        const simpleParams = entries.filter(([, info]) => simpleTypes.includes(info.type));
        const complexParams = entries.filter(([, info]) => !simpleTypes.includes(info.type));

        let html = '<div class="param-grid">';

        simpleParams.forEach(([key, info]) => {
            const val = values[key] !== undefined ? values[key] : (info.default !== undefined ? info.default : '');
            const inputType = info.type === 'int' || info.type === 'float' ? 'number' : 'text';
            const step = info.type === 'float' ? '0.01' : (info.type === 'int' ? '1' : undefined);
            html += `
                <div class="param-item">
                    <label class="param-label" title="${escapeHtml(key)}${info.default !== undefined ? ' · 默认: ' + JSON.stringify(info.default) : ''}">${escapeHtml(key)}</label>
                    <input type="${inputType}" class="form-input param-input" data-param-key="${escapeHtml(key)}" data-param-type="${escapeHtml(info.type)}"
                        value="${escapeHtml(String(val))}" placeholder="${escapeHtml(info.default !== undefined ? String(info.default) : '')}"${step ? ` step="${step}"` : ''}>
                </div>`;
        });

        html += '</div>';

        complexParams.forEach(([key, info]) => {
            const val = values[key] !== undefined ? values[key] : (info.default !== undefined ? info.default : '');
            const jsonStr = typeof val === 'object' ? JSON.stringify(val) : String(val);
            html += `
                <div class="param-item param-item-wide">
                    <label class="param-label" title="${escapeHtml(key)} · 默认: ${escapeHtml(JSON.stringify(info.default))}">${escapeHtml(key)} <span class="param-type-tag">${escapeHtml(info.type)}</span></label>
                    <textarea class="form-input param-input" data-param-key="${escapeHtml(key)}" data-param-type="${escapeHtml(info.type)}"
                        rows="2" placeholder="${escapeHtml(JSON.stringify(info.default !== undefined ? info.default : ''))}">${escapeHtml(jsonStr)}</textarea>
                </div>`;
        });

        container.innerHTML = html;

        // 重置折叠状态（默认折叠）
        if (toggle) toggle.setAttribute('aria-expanded', 'false');
        if (toggle) toggle.querySelector('.toggle-icon').innerHTML = '&#9654;';
        if (body) body.style.display = 'none';
    }

    // 注册路由
    if (typeof Router !== 'undefined') {
        Router.register('/analyze', render);
    }
})();
