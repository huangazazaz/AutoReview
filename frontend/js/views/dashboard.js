/**
 * 仪表盘视图 — 系统概览、快速入口
 * 设计: AutoTrade v3 — 增强卡片 / 渐变强调 / 玻璃拟态
 */
(function () {
    'use strict';

    async function render(container) {
        // 图标引用
        const _ = window.Icon || {};
        const D = _.dashboard || (() => '');
        const S = _.search || (() => '');
        const C = _.chart || (() => '');
        const K = _.candlestick || (() => '');
        const F = _.folder || (() => '');
        const BR = _.brain || (() => '');
        const DB = _.database || (() => '');
        const Z = _.zap || (() => '');
        const AC = _.activity || (() => '');
        const LZ = _.layers || (() => '');
        const US = _.users || (() => '');

        container.innerHTML = `
            <!-- 英雄区渐变背景 -->
            <div class="page-hero">
                <div class="page-header" style="margin-bottom:0;">
                    <h1 class="page-title" style="display:flex;align-items:center;gap:var(--space-3);">
                        <span style="display:flex;align-items:center;justify-content:center;width:40px;height:40px;border-radius:var(--radius);background:var(--gradient-brand);color:#fff;">${D({ size: 22, class: '' })}</span>
                        仪表盘
                    </h1>
                    <p class="page-subtitle" style="margin-top:4px;">AutoTrade A股量化回测系统 · 实时状态概览</p>
                </div>
            </div>

            <!-- 状态卡片 — 增强样式 -->
            <div class="stats-grid stagger" id="dash-stats" role="status" aria-label="系统状态概览">
                ${renderSkeleton('card', 4)}
            </div>

            <!-- 快捷操作 -->
            <div style="display:flex;align-items:center;gap:var(--space-3);margin:var(--space-6) 0 var(--space-3);">
                <div style="width:3px;height:18px;border-radius:2px;background:var(--gradient-brand);flex-shrink:0;"></div>
                <h3 class="section-title" style="margin:0;">快捷操作</h3>
            </div>
            <div class="quick-actions stagger">
                <a href="#/analyze" class="quick-action-card animate-in" aria-label="单股分析 — 对单只股票进行策略回测">
                    <span class="qa-icon" style="background:var(--accent-bg);border-color:rgba(139,92,246,0.25);color:var(--accent);">${S({ size: 24 })}</span>
                    <span class="qa-title">单股分析</span>
                    <span class="qa-desc">对单只股票进行策略回测，查看详细交易记录与指标</span>
                </a>
                <a href="#/backtest" class="quick-action-card animate-in" aria-label="批量回测 — 按分组批量运行策略">
                    <span class="qa-icon">${C({ size: 24 })}</span>
                    <span class="qa-title">批量回测</span>
                    <span class="qa-desc">按分组或多只股票批量运行策略，对比收益率</span>
                </a>
                <a href="#/bars" class="quick-action-card animate-in" aria-label="K线数据 — 查询日线 OHLC 数据">
                    <span class="qa-icon" style="background:var(--info-bg);border-color:rgba(59,130,246,0.25);color:var(--info);">${K({ size: 24 })}</span>
                    <span class="qa-title">K线数据</span>
                    <span class="qa-desc">查询股票日线数据，可视化 OHLC 蜡烛图</span>
                </a>
                <a href="#/groups" class="quick-action-card animate-in" aria-label="分组管理 — 创建和管理股票分组">
                    <span class="qa-icon" style="background:var(--sell-bg);border-color:rgba(34,197,94,0.25);color:var(--success);">${F({ size: 24 })}</span>
                    <span class="qa-title">分组管理</span>
                    <span class="qa-desc">创建和管理股票分组，方便批量回测</span>
                </a>
            </div>

            <!-- 策略 & 数据源 -->
            <div style="display:flex;align-items:center;gap:var(--space-3);margin:var(--space-6) 0 var(--space-3);">
                <div style="width:3px;height:18px;border-radius:2px;background:var(--gradient-brand);flex-shrink:0;"></div>
                <h3 class="section-title" style="margin:0;">系统资源</h3>
            </div>
            <div class="row-stack">
                <div class="card grow animate-in card-accent" style="border-top:2px solid rgba(139,92,246,0.3);">
                    <div class="card-header">
                        <span class="card-title" style="display:flex;align-items:center;gap:var(--space-2);">
                            <span style="color:var(--accent);display:flex;">${BR({ size: 18 })}</span> 可用策略
                        </span>
                        <span class="badge-outline" id="dash-strategy-count">—</span>
                    </div>
                    <div class="card-body" id="dash-strategies">
                        <span style="color:var(--text-muted);">加载中...</span>
                    </div>
                </div>
                <div class="card grow animate-in card-accent" style="border-top:2px solid rgba(59,130,246,0.3);">
                    <div class="card-header">
                        <span class="card-title" style="display:flex;align-items:center;gap:var(--space-2);">
                            <span style="color:var(--info);display:flex;">${DB({ size: 18 })}</span> 数据源
                        </span>
                        <span class="badge-outline" id="dash-ds-count">—</span>
                    </div>
                    <div class="card-body" id="dash-datasources">
                        <span style="color:var(--text-muted);">加载中...</span>
                    </div>
                </div>
            </div>
        `;

        // 并行加载数据
        const [healthData, strategiesData, datasourcesData, groupsData] = await Promise.allSettled([
            API.health(),
            API.getStrategies(),
            API.getDatasources(),
            API.getGroups(),
        ]);

        // 健康状态
        const healthOk = healthData.status === 'fulfilled' && healthData.value?.status === 'ok';
        const healthIcon = healthOk
            ? `<span class="pulse-dot online" style="margin-right:8px;"></span>`
            : `<span class="pulse-dot offline" style="margin-right:8px;"></span>`;

        document.getElementById('dash-stats').innerHTML = `
            <div class="stat-card" role="status" aria-label="API 状态：${healthOk ? '正常' : '异常'}" style="border-top:2px solid ${healthOk ? 'var(--success)' : 'var(--error)'};">
                <div class="stat-label">${healthIcon} API 状态</div>
                <div class="stat-value ${healthOk ? 'stat-positive' : 'stat-negative'}" style="font-size:20px;">
                    ${healthOk ? '运行正常' : '连接异常'}
                </div>
                <div class="stat-sub">${healthOk ? '所有服务在线' : '无法连接到后端'}</div>
            </div>
            <div class="stat-card" style="border-top:2px solid var(--accent);">
                <div class="stat-label">📊 可用策略</div>
                <div class="stat-value stat-neutral">
                    ${strategiesData.status === 'fulfilled' ? strategiesData.value.strategies.length : '—'}
                </div>
                <div class="stat-sub">已注册策略数</div>
            </div>
            <div class="stat-card" style="border-top:2px solid var(--info);">
                <div class="stat-label">📡 数据源</div>
                <div class="stat-value stat-neutral">
                    ${datasourcesData.status === 'fulfilled' ? datasourcesData.value.datasources.length : '—'}
                </div>
                <div class="stat-sub">可用数据源数</div>
            </div>
            <div class="stat-card" style="border-top:2px solid var(--primary);">
                <div class="stat-label">📁 股票分组</div>
                <div class="stat-value stat-neutral">
                    ${groupsData.status === 'fulfilled' ? groupsData.value.groups.length : '—'}
                </div>
                <div class="stat-sub">已配置分组数</div>
            </div>
        `;

        // 策略标签
        const stratEl = document.getElementById('dash-strategies');
        const stratCountEl = document.getElementById('dash-strategy-count');
        if (strategiesData.status === 'fulfilled' && strategiesData.value.strategies.length) {
            const names = strategiesData.value.strategies.map(s => typeof s === 'string' ? s : s.name);
            stratEl.innerHTML = names.map(s => `<span class="tag">${escapeHtml(s)}</span>`).join(' ');
            stratCountEl.textContent = names.length + ' 个';
        } else {
            stratEl.innerHTML = `
                <div class="empty-state" style="padding:var(--space-5) 0;">
                    <p style="color:var(--text-muted);">暂无策略</p>
                </div>`;
            stratCountEl.textContent = '0';
        }

        // 数据源标签
        const dsEl = document.getElementById('dash-datasources');
        const dsCountEl = document.getElementById('dash-ds-count');
        if (datasourcesData.status === 'fulfilled' && datasourcesData.value.datasources.length) {
            dsEl.innerHTML = datasourcesData.value.datasources.map(d => `<span class="tag">${escapeHtml(d)}</span>`).join(' ');
            dsCountEl.textContent = datasourcesData.value.datasources.length + ' 个';
        } else {
            dsEl.innerHTML = `
                <div class="empty-state" style="padding:var(--space-5) 0;">
                    <p style="color:var(--text-muted);">暂无数据源</p>
                </div>`;
            dsCountEl.textContent = '0';
        }
    }

    // 注册路由
    if (typeof Router !== 'undefined') {
        Router.register('/', render);
    }
})();
