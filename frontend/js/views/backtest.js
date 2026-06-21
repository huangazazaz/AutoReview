/**
 * 批量回测视图 — 按分组或多只股票批量运行策略
 */
(function () {
    'use strict';

    let chartInstance = null;
    let sortKey = 'return_pct';
    let sortAsc = false;

    async function render(container) {
        const _ = window.Icon || {};
        const Chart = _.chart || (() => '');
        const Rocket = _.rocket || (() => '');
        const Loader = _.loader || (() => '');

        // 清理旧图表
        if (chartInstance) { chartInstance.dispose(); chartInstance = null; }

        container.innerHTML = `
            <div class="page-header">
                <h1 class="page-title">${Chart({ size: 24 })} 批量回测</h1>
                <p class="page-subtitle">按分组或自定义股票列表批量运行策略，多维度对比收益率</p>
            </div>

            <!-- 表单 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">回测参数</span>
                </div>
                <div class="card-body">
                    <!-- 输入模式切换 -->
                    <div class="tabs" id="bt-input-mode" role="tablist" aria-label="输入模式">
                        <button class="tab active" data-mode="symbols" role="tab" aria-selected="true">按代码</button>
                        <button class="tab" data-mode="group" role="tab" aria-selected="false">按分组</button>
                    </div>

                    <div id="bt-symbols-panel">
                        <div class="form-group">
                            <label class="form-label" for="bt-symbols">股票代码</label>
                            <div class="input-with-clear">
                                <input type="text" class="form-input" id="bt-symbols"
                                    placeholder="逗号分隔，如 600522,000001,600036" autocomplete="off">
                                <button type="button" class="input-clear-btn" id="bt-symbols-clear"
                                    title="清空" aria-label="清空股票代码" tabindex="-1">&times;</button>
                            </div>
                        </div>
                        <!-- 缓存股票快速选择 -->
                        <div class="form-group" id="bt-cached-panel">
                            <label class="form-label" for="bt-cached-stocks">
                                缓存股票快速选择
                                <span style="font-weight:400;font-size:11px;color:var(--text-muted);margin-left:4px;">（点击添加）</span>
                            </label>
                            <div style="display:flex; gap:8px;">
                                <select class="form-select" id="bt-cached-stocks" style="flex:1;">
                                    <option value="">— 选择已缓存的股票 —</option>
                                </select>
                                <button class="btn btn-secondary btn-sm" id="bt-add-all-cached" title="添加全部缓存股票" style="white-space:nowrap;">
                                    + 全部
                                </button>
                            </div>
                        </div>
                    </div>
                    <div id="bt-group-panel" style="display:none;">
                        <div class="form-group">
                            <label class="form-label" for="bt-group">选择分组</label>
                            <select class="form-select" id="bt-group"></select>
                        </div>
                    </div>

                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label" for="bt-strategy">策略</label>
                            <select class="form-select" id="bt-strategy"></select>
                        </div>
                        <div class="form-group">
                            <label class="form-label" for="bt-period">周期</label>
                            <select class="form-select" id="bt-period">
                                <option value="1y">最近 1 年</option>
                                <option value="6m">最近 6 个月</option>
                                <option value="3m">最近 3 个月</option>
                                <option value="20d">最近 20 天</option>
                                <option value="60t">最近 60 交易日</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label class="form-label" for="bt-datasource">数据源</label>
                            <select class="form-select" id="bt-datasource">
                                <option value="">自动（主备降级）</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label class="form-label" for="bt-start">开始日期</label>
                            <input type="text" class="form-input date-input" id="bt-start"
                                placeholder="开始日期" autocomplete="off"
                                onfocus="this.type='date';this.showPicker?.()" onblur="if(!this.value)this.type='text'">
                        </div>
                        <div class="form-group">
                            <label class="form-label" for="bt-end">结束日期</label>
                            <input type="text" class="form-input date-input" id="bt-end"
                                placeholder="结束日期" autocomplete="off"
                                onfocus="this.type='date';this.showPicker?.()" onblur="if(!this.value)this.type='text'">
                        </div>
                        <div class="form-group" style="display:flex; align-items:flex-end;">
                            <button class="btn btn-primary" id="bt-submit" style="width:100%;">
                                ${Rocket({ size: 18 })} 开始批量回测
                            </button>
                        </div>
                    </div>

                    <!-- 策略参数 - 独立可折叠区域 -->
                    <div class="params-section" id="bt-params-panel" style="display:none;">
                        <button type="button" class="params-toggle" id="bt-params-toggle" aria-expanded="false">
                            <span class="toggle-icon">&#9654;</span> 策略参数
                            <span class="params-summary" id="bt-params-summary"></span>
                        </button>
                        <div class="params-body" id="bt-params-body" style="display:none;">
                            <div id="bt-params" class="strategy-params"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 结果区 -->
            <div id="bt-results"></div>
        `;

        // 加载下拉数据（并行：策略 + 数据源 + 分组 + 缓存股票）
        const [strategiesData, datasourcesData, groupsData, cachedData] = await Promise.allSettled([
            API.getStrategies(),
            API.getDatasources(),
            API.getGroups(),
            API.getCachedStocks(),
        ]);

        const strategySelect = document.getElementById('bt-strategy');
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
        const paramPanel = document.getElementById('bt-params-panel');
        const paramContainer = document.getElementById('bt-params');
        const paramToggle = document.getElementById('bt-params-toggle');
        const paramBody = document.getElementById('bt-params-body');

        if (strategiesList.length > 0 && paramContainer) {
            renderBtParams(strategiesList, strategySelect.value, paramContainer, paramPanel, paramBody, paramToggle);
        }
        strategySelect.addEventListener('change', () => {
            if (strategiesList.length > 0 && paramContainer) {
                renderBtParams(strategiesList, strategySelect.value, paramContainer, paramPanel, paramBody, paramToggle);
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

        const dsSelect = document.getElementById('bt-datasource');
        if (datasourcesData.status === 'fulfilled') {
            dsSelect.innerHTML += datasourcesData.value.datasources
                .map(d => `<option value="${escapeHtml(d)}">${escapeHtml(d)}</option>`).join('');
        }

        const groupSelect = document.getElementById('bt-group');
        if (groupsData.status === 'fulfilled' && groupsData.value.groups.length) {
            groupSelect.innerHTML = groupsData.value.groups
                .map(g => `<option value="${escapeHtml(g.id)}">${escapeHtml(g.name)} (${g.symbols.length} 只)</option>`).join('');
        } else {
            groupSelect.innerHTML = '<option value="">暂无分组</option>';
        }

        // 缓存股票下拉框
        const cachedSelect = document.getElementById('bt-cached-stocks');
        let cachedSymbols = [];
        if (cachedData.status === 'fulfilled' && cachedData.value.symbols && cachedData.value.symbols.length) {
            cachedSymbols = cachedData.value.symbols;
            cachedSelect.innerHTML = '<option value="">— 选择已缓存的股票 (' + cachedSymbols.length + ' 只) —</option>'
                + cachedSymbols.map(s => {
                    const namePart = s.name ? ` ${s.name}` : '';
                    const info = s.last_close != null
                        ? `收盘 ¥${formatNumber(s.last_close, 2)} · ${s.bars}条 [${s.start || '?'}~${s.end || '?'}]`
                        : `${s.bars || 0}条数据`;
                    return `<option value="${escapeHtml(s.symbol)}">${escapeHtml(s.symbol)}${escapeHtml(namePart)} — ${escapeHtml(info)}</option>`;
                }).join('');
        } else {
            cachedSelect.innerHTML = '<option value="">— 无缓存数据，请先查询K线 —</option>';
        }

        // 股票代码输入框快捷清空
        const btSymbolsInput = document.getElementById('bt-symbols');
        const btSymbolsClear = document.getElementById('bt-symbols-clear');
        if (btSymbolsInput && btSymbolsClear) {
            const toggleClearBtn = () => {
                btSymbolsClear.classList.toggle('visible', !!btSymbolsInput.value);
            };
            btSymbolsInput.addEventListener('input', toggleClearBtn);
            btSymbolsClear.addEventListener('click', () => {
                btSymbolsInput.value = '';
                btSymbolsClear.classList.remove('visible');
                btSymbolsInput.focus();
            });
            toggleClearBtn();
        }

        // 缓存股票选择 → 追加到代码输入框
        cachedSelect.addEventListener('change', function () {
            const code = this.value;
            if (!code) return;
            const input = document.getElementById('bt-symbols');
            const existing = input.value.split(/[,，\s]+/).filter(Boolean);
            if (!existing.includes(code)) {
                existing.push(code);
                input.value = existing.join(',');
            }
            this.value = ''; // 重置选择
            showToast(`已添加 ${code}`, 'info', 1500);
        });

        // "全部添加"按钮
        document.getElementById('bt-add-all-cached').addEventListener('click', function () {
            const input = document.getElementById('bt-symbols');
            const existing = input.value.split(/[,，\s]+/).filter(Boolean);
            const newCodes = cachedSymbols.map(s => s.symbol).filter(c => !existing.includes(c));
            if (newCodes.length === 0) {
                showToast('所有缓存股票已在列表中', 'info');
                return;
            }
            input.value = [...existing, ...newCodes].join(',');
            showToast(`已添加 ${newCodes.length} 只缓存股票`, 'success');
        });

        // 输入模式切换
        let inputMode = 'symbols';
        document.getElementById('bt-input-mode').addEventListener('click', (e) => {
            if (!e.target.classList.contains('tab')) return;
            const mode = e.target.dataset.mode;
            if (mode === inputMode) return;
            inputMode = mode;
            document.querySelectorAll('#bt-input-mode .tab').forEach(t => {
                t.classList.toggle('active', t.dataset.mode === mode);
                t.setAttribute('aria-selected', String(t.dataset.mode === mode));
            });
            document.getElementById('bt-symbols-panel').style.display = mode === 'symbols' ? '' : 'none';
            document.getElementById('bt-group-panel').style.display = mode === 'group' ? '' : 'none';
        });

        // 提交
        document.getElementById('bt-submit').addEventListener('click', async () => {
            const params = {
                strategy: document.getElementById('bt-strategy').value,
                period: document.getElementById('bt-period').value,
            };

            if (inputMode === 'symbols') {
                const syms = document.getElementById('bt-symbols').value.trim();
                if (!syms) { showToast('请输入股票代码或选择分组', 'warning'); return; }
                params.symbols = syms;
            } else {
                const group = document.getElementById('bt-group').value;
                if (!group) { showToast('请选择分组', 'warning'); return; }
                params.group = group;
            }

            const ds = document.getElementById('bt-datasource').value;
            if (ds) params.datasource = ds;

            const start = document.getElementById('bt-start').value;
            const end = document.getElementById('bt-end').value;
            if (start) params.start = start;
            if (end) params.end = end;
            if (start || end) delete params.period;

            // 收集策略参数覆盖值
            const paramInputs = document.querySelectorAll('#bt-params .param-input');
            if (paramInputs.length > 0) {
                const strategyParams = {};
                paramInputs.forEach(input => {
                    const key = input.dataset.paramKey;
                    const type = input.dataset.paramType;
                    let val = input.value.trim();
                    if (val === '') return;
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

            const btn = document.getElementById('bt-submit');
            btn.disabled = true;
            btn.innerHTML = `${Loader({ size: 18 })} 批量回测中...`;
            showLoading('正在批量回测，请稍候...');

            const data = await safeAsync(() => API.backtest(params), '批量回测失败');

            hideLoading();
            btn.disabled = false;
            btn.innerHTML = `${Rocket({ size: 18 })} 开始批量回测`;

            if (data && !data.error) {
                renderResults(data);
            } else if (data && data.error) {
                showToast(data.error, 'error');
            }
        });
    }

    function renderResults(data) {
        const _ = window.Icon || {};
        const Gold = _.gold || (() => '');
        const Silver = _.silver || (() => '');
        const Bronze = _.bronze || (() => '');
        const Chart = _.chart || (() => '');
        const File = _.folder || (() => '');

        const results = data.results || [];
        const avgReturn = data.avg_return_pct || 0;
        const total = data.total || 0;
        const positivePct = total > 0 ? ((data.positive_count || 0) / total * 100) : 0;

        // 按收益率降序排列（排行榜）
        const ranked = [...results].sort((a, b) => (b.return_pct || 0) - (a.return_pct || 0));

        // 图表用数据
        const chartData = ranked.map(r => ({
            symbol: r.symbol,
            name: r.stock_name || r.symbol,
            return_pct: r.return_pct || 0,
            sharpe: r.sharpe || 0,
            trades: r.trades || 0,
            max_drawdown: r.max_drawdown_pct || 0,
            win_rate: r.win_rate || 0,
        }));

        // 最佳 / 最差
        const best = data.best_symbol ? `${data.best_symbol}${data.best_return ? ' ' + formatPct(data.best_return) : ''}` : '—';
        const worst = data.worst_symbol ? `${data.worst_symbol}${data.worst_return ? ' ' + formatPct(data.worst_return) : ''}` : '—';

        document.getElementById('bt-results').innerHTML = `
            <!-- 汇总卡片 -->
            <div class="stats-grid" style="margin-top:var(--space-4);" role="status" aria-label="批量回测汇总">
                <div class="stat-card">
                    <div class="stat-label">股票总数 / 胜率</div>
                    <div class="stat-value stat-neutral">
                        ${total}
                        <span style="font-size:14px;color:var(--text-muted);">只</span>
                    </div>
                    <div class="stat-sub">正收益占比 ${formatNumber(positivePct, 1)}%</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">成功 / 失败</div>
                    <div class="stat-value stat-neutral">
                        ${data.success || 0}
                        <span style="font-size:16px;color:var(--text-muted);">/</span>
                        <span style="color:${(data.failed || 0) > 0 ? 'var(--error)' : 'inherit'}">${data.failed || 0}</span>
                    </div>
                    <div class="stat-sub">正 <span style="color:var(--buy);">${data.positive_count || 0}</span> · 负 <span style="color:var(--sell);">${data.negative_count || 0}</span></div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">平均收益率</div>
                    <div class="stat-value ${avgReturn >= 0 ? 'stat-positive' : 'stat-negative'}">
                        ${formatPct(avgReturn)}
                    </div>
                    <div class="stat-sub">全部股票均值</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">最佳 / 最差</div>
                    <div class="stat-value stat-neutral" style="font-size:16px;">
                        <span style="color:var(--buy);">${escapeHtml(best)}</span>
                    </div>
                    <div class="stat-sub" style="color:var(--sell);">${escapeHtml(worst)}</div>
                </div>
            </div>

            <!-- 对比图表 + 表格 -->
            <div style="display:flex; gap:var(--space-5); flex-wrap:wrap;">
                <div class="chart-container" id="bt-chart" role="img" aria-label="收益率对比柱状图"
                    style="flex:1; min-width:380px; height:${Math.max(300, chartData.length * 36 + 80)}px;"></div>

                <div class="card" style="flex:2; min-width:500px;">
                    <div class="card-header">
                        <span class="card-title">收益率排行</span>
                        <span style="font-size:12px;color:var(--text-muted);">点击表头排序 · 点击行查看详情</span>
                    </div>
                    <div class="card-body" style="padding:0;">
                        ${chartData.length === 0 ? `<div class="empty-state"><span class="empty-icon">${File({ size: 48 })}</span><p>无结果</p></div>` : `
                        <div class="table-container" style="border:none;">
                            <table id="bt-results-table" aria-label="收益率排行榜">
                                <thead>
                                    <tr>
                                        <th style="width:40px;" aria-label="排名">#</th>
                                        <th data-sort="symbol">股票</th>
                                        <th data-sort="return_pct" style="text-align:right;" class="sorted" aria-sort="descending">收益率 ▾</th>
                                        <th data-sort="max_drawdown" style="text-align:right;">最大回撤</th>
                                        <th data-sort="sharpe" style="text-align:right;">夏普</th>
                                        <th data-sort="win_rate" style="text-align:right;">胜率</th>
                                        <th data-sort="trades" style="text-align:right;">交易</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${chartData.map((r, i) => {
                                        const rank = i + 1;
                                        const medalHtml = rank === 1 ? Gold({ size: 18 }) : rank === 2 ? Silver({ size: 18 }) : rank === 3 ? Bronze({ size: 18 }) : `<span style="color:var(--text-muted);">${rank}</span>`;
                                        const ret = r.return_pct;
                                        const isPos = ret >= 0;
                                        const rowBg = isPos ? 'rgba(239,68,68,0.03)' : 'rgba(34,197,94,0.03)';
                                        return `
                                        <tr class="clickable" data-symbol="${escapeHtml(r.symbol)}"
                                            title="点击查看 ${escapeHtml(r.name)} 详情"
                                            style="background:${rowBg};">
                                            <td style="font-weight:700; text-align:center;">${medalHtml}</td>
                                            <td>
                                                <strong>${escapeHtml(r.symbol)}</strong>
                                                ${r.name ? `<span style="color:var(--text-muted); font-size:12px; margin-left:4px;">${escapeHtml(r.name)}</span>` : ''}
                                            </td>
                                            <td style="text-align:right; font-weight:700; color:${isPos ? 'var(--buy)' : 'var(--sell)'};">
                                                ${formatPct(ret)}
                                            </td>
                                            <td style="text-align:right; color:var(--sell);">${formatPct(r.max_drawdown)}</td>
                                            <td style="text-align:right;">${formatNumber(r.sharpe, 3)}</td>
                                            <td style="text-align:right;">${formatPct(r.win_rate)}</td>
                                            <td style="text-align:right;">${r.trades}</td>
                                        </tr>`;
                                    }).join('')}
                                </tbody>
                            </table>
                        </div>`}
                    </div>
                </div>
            </div>
        `;

        // 渲染 ECharts 对比柱状图
        if (chartData.length > 0) {
            renderChart(chartData);
        }

        // 点击行跳转到单股分析
        bindRowClicks();

        // 点击表头排序
        document.querySelectorAll('#bt-results-table thead th[data-sort]').forEach(th => {
            th.addEventListener('click', () => {
                const key = th.dataset.sort;
                if (sortKey === key) {
                    sortAsc = !sortAsc;
                } else {
                    sortKey = key;
                    sortAsc = false;
                }
                sortAndRerender(data);
            });
        });
    }

    function bindRowClicks() {
        document.querySelectorAll('#bt-results-table tbody tr.clickable').forEach(row => {
            row.addEventListener('click', () => {
                const symbol = row.dataset.symbol;
                if (symbol && typeof Router !== 'undefined') {
                    Router.navigate('/analyze');
                    setTimeout(() => {
                        const input = document.getElementById('analyze-symbol');
                        if (input) { input.value = symbol; input.focus(); }
                    }, 100);
                }
            });
        });
    }

    function sortAndRerender(data) {
        const _ = window.Icon || {};
        const Gold = _.gold || (() => '');
        const Silver = _.silver || (() => '');
        const Bronze = _.bronze || (() => '');

        const results = data.results || [];
        const sorted = [...results].sort((a, b) => {
            const va = a[sortKey] ?? 0;
            const vb = b[sortKey] ?? 0;
            if (typeof va === 'string') {
                return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
            }
            return sortAsc ? va - vb : vb - va;
        });

        // 更新排序箭头和 aria-sort
        document.querySelectorAll('#bt-results-table thead th[data-sort]').forEach(th => {
            const isSorted = th.dataset.sort === sortKey;
            th.classList.toggle('sorted', isSorted);
            if (isSorted) {
                th.setAttribute('aria-sort', sortAsc ? 'ascending' : 'descending');
            } else {
                th.removeAttribute('aria-sort');
            }
        });

        const tbody = document.querySelector('#bt-results-table tbody');
        if (!tbody) return;

        tbody.innerHTML = sorted.map((r, i) => {
            const rank = i + 1;
            const medalHtml = rank === 1 ? Gold({ size: 18 }) : rank === 2 ? Silver({ size: 18 }) : rank === 3 ? Bronze({ size: 18 }) : `<span style="color:var(--text-muted);">${rank}</span>`;
            const ret = r.return_pct || 0;
            const isPos = ret >= 0;
            const rowBg = isPos ? 'rgba(239,68,68,0.03)' : 'rgba(34,197,94,0.03)';
            return `
            <tr class="clickable" data-symbol="${escapeHtml(r.symbol)}"
                title="点击查看 ${escapeHtml(r.stock_name || r.symbol)} 详情"
                style="background:${rowBg};">
                <td style="font-weight:700; text-align:center;">${medalHtml}</td>
                <td>
                    <strong>${escapeHtml(r.symbol)}</strong>
                    ${r.stock_name ? `<span style="color:var(--text-muted); font-size:12px; margin-left:4px;">${escapeHtml(r.stock_name)}</span>` : ''}
                </td>
                <td style="text-align:right; font-weight:700; color:${isPos ? 'var(--buy)' : 'var(--sell)'};">
                    ${formatPct(ret)}
                </td>
                <td style="text-align:right; color:var(--sell);">${formatPct(r.max_drawdown_pct)}</td>
                <td style="text-align:right;">${formatNumber(r.sharpe, 3)}</td>
                <td style="text-align:right;">${formatPct(r.win_rate)}</td>
                <td style="text-align:right;">${r.trades}</td>
            </tr>`;
        }).join('');

        bindRowClicks();
    }

    function renderChart(data) {
        const dom = document.getElementById('bt-chart');
        if (!dom || typeof echarts === 'undefined') return;

        if (chartInstance) chartInstance.dispose();

        chartInstance = echarts.init(dom, 'dark');

        const reversed = [...data].reverse();
        const names = reversed.map(r => r.name);
        const values = reversed.map(r => r.return_pct);

        // 色盲友好配色
        const POS_COLOR = '#EF4444';
        const NEG_COLOR = '#22C55E';

        const option = {
            title: {
                text: '收益率对比',
                subtext: '柱上直接标注数值 · 实心=正收益 · 斜线=负收益（色盲友好）',
                left: 'center',
                textStyle: { color: '#E2E8F0', fontSize: 13 },
                subtextStyle: { color: '#64748B', fontSize: 10 },
            },
            backgroundColor: '#1E293B',
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                backgroundColor: '#1A2332',
                borderColor: '#334155',
                textStyle: { color: '#E2E8F0', fontSize: 12 },
                formatter: function (params) {
                    const p = params[0];
                    const d = reversed[p.dataIndex];
                    return `<strong>${escapeHtml(d.symbol)} ${escapeHtml(d.name)}</strong><br/>
                        收益率: ${formatPct(d.return_pct)}<br/>
                        夏普: ${formatNumber(d.sharpe, 3)}<br/>
                        最大回撤: ${formatPct(d.max_drawdown)}<br/>
                        交易笔数: ${d.trades}`;
                },
            },
            // 右侧留出空间给数值标签
            grid: { left: '3%', right: '14%', top: '15%', bottom: '3%', containLabel: true },
            xAxis: {
                type: 'value',
                axisLine: { lineStyle: { color: '#334155' } },
                axisLabel: {
                    color: '#94A3B8',
                    fontSize: 11,
                    formatter: '{value}%',
                },
                splitLine: { lineStyle: { color: '#1E293B' } },
            },
            yAxis: {
                type: 'category',
                data: names,
                axisLine: { lineStyle: { color: '#334155' } },
                axisLabel: {
                    color: '#94A3B8',
                    fontSize: 12,
                    width: 100,
                    overflow: 'truncate',
                },
                inverse: true,
            },
            series: [{
                type: 'bar',
                data: values.map(v => ({
                    value: v,
                    itemStyle: {
                        color: v >= 0 ? POS_COLOR : NEG_COLOR,
                        borderRadius: [0, 4, 4, 0],
                        // 负收益叠加斜线图案（色盲友好）
                        decal: v < 0 ? {
                            symbol: 'rect',
                            symbolSize: 0.6,
                            color: 'rgba(255,255,255,0.15)',
                            dashArrayX: [3, 3],
                            dashArrayY: [8, 4],
                            rotation: -45,
                        } : undefined,
                    },
                })),
                barMaxWidth: 24,
                // ★ 关键优化: 柱子上直接显示数值标签
                label: {
                    show: true,
                    position: 'right',
                    color: '#E2E8F0',
                    fontSize: 11,
                    fontFamily: 'Inter, sans-serif',
                    fontWeight: 500,
                    formatter: function (p) {
                        return (p.value >= 0 ? '+' : '') + p.value.toFixed(2) + '%';
                    },
                },
                emphasis: {
                    itemStyle: {
                        color: (p) => p.value >= 0 ? '#F87171' : '#4ADE80',
                    },
                    label: {
                        fontSize: 12,
                        fontWeight: 600,
                    },
                },
            }],
        };

        chartInstance.setOption(option);

        // 屏幕阅读器摘要
        const srSummaryId = 'bt-chart-summary';
        const posCount = values.filter(v => v >= 0).length;
        const negCount = values.filter(v => v < 0).length;
        const maxRet = Math.max(...values);
        const minRet = Math.min(...values);
        const bestName = reversed[values.indexOf(maxRet)]?.name || '';
        const srSummary = `收益率对比图：共${values.length}只股票，${posCount}只正收益，${negCount}只负收益。最佳${bestName}收益率${formatPct(maxRet)}，最差收益率${formatPct(minRet)}。`;

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
     * 渲染批量回测策略参数编辑表单（独立可折叠面板）
     */
    function renderBtParams(strategiesList, strategyName, container, panel, body, toggle) {
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

        if (panel) panel.style.display = '';

        // 更新摘要
        const summaryEl = document.getElementById('bt-params-summary');
        if (summaryEl) {
            const summaryParts = entries.slice(0, 5).map(([k]) => {
                const v = values[k] !== undefined ? values[k] : (schema[k].default !== undefined ? schema[k].default : '—');
                const displayVal = typeof v === 'object' ? JSON.stringify(v) : String(v);
                return `${k}=${displayVal}`;
            });
            const more = entries.length > 5 ? ` +${entries.length - 5}` : '';
            summaryEl.textContent = summaryParts.join(', ') + more;
        }

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

        // 重置折叠状态
        if (toggle) toggle.setAttribute('aria-expanded', 'false');
        if (toggle) toggle.querySelector('.toggle-icon').innerHTML = '&#9654;';
        if (body) body.style.display = 'none';
    }

    // 注册路由
    if (typeof Router !== 'undefined') {
        Router.register('/backtest', render);
    }
})();
