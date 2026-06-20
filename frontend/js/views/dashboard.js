/**
 * 仪表盘视图 — 系统概览、快速入口
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

        container.innerHTML = `
            <div class="page-header">
                <h1 class="page-title">${D({ size: 24, class: '' })} 仪表盘</h1>
                <p class="page-subtitle">AutoTrade A股量化回测系统</p>
            </div>

            <!-- 状态卡片 -->
            <div class="stats-grid stagger" id="dash-stats" role="status" aria-label="系统状态概览">
                ${renderSkeleton('card', 4)}
            </div>

            <!-- 快捷操作 -->
            <h3 class="section-title">快捷操作</h3>
            <div class="quick-actions stagger">
                <a href="#/analyze" class="quick-action-card animate-in" aria-label="单股分析 — 对单只股票进行策略回测">
                    <span class="qa-icon">${S({ size: 24 })}</span>
                    <span class="qa-title">单股分析</span>
                    <span class="qa-desc">对单只股票进行策略回测，查看详细交易记录与指标</span>
                </a>
                <a href="#/backtest" class="quick-action-card animate-in" aria-label="批量回测 — 按分组批量运行策略">
                    <span class="qa-icon">${C({ size: 24 })}</span>
                    <span class="qa-title">批量回测</span>
                    <span class="qa-desc">按分组或多只股票批量运行策略，对比收益率</span>
                </a>
                <a href="#/bars" class="quick-action-card animate-in" aria-label="K线数据 — 查询日线 OHLC 数据">
                    <span class="qa-icon">${K({ size: 24 })}</span>
                    <span class="qa-title">K线数据</span>
                    <span class="qa-desc">查询股票日线数据，可视化 OHLC 蜡烛图</span>
                </a>
                <a href="#/groups" class="quick-action-card animate-in" aria-label="分组管理 — 创建和管理股票分组">
                    <span class="qa-icon">${F({ size: 24 })}</span>
                    <span class="qa-title">分组管理</span>
                    <span class="qa-desc">创建和管理股票分组，方便批量回测</span>
                </a>
            </div>

            <!-- 策略 & 数据源 -->
            <div class="row-stack">
                <div class="card grow animate-in">
                    <div class="card-header">
                        <span class="card-title">${BR({ size: 18 })} 可用策略</span>
                    </div>
                    <div class="card-body" id="dash-strategies">
                        <span style="color:var(--text-muted);">加载中...</span>
                    </div>
                </div>
                <div class="card grow animate-in">
                    <div class="card-header">
                        <span class="card-title">${DB({ size: 18 })} 数据源</span>
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
        const checkIcon = healthOk ? (_.check || (() => ''))({ size: 16, class: '' }) : (_.xCircle || (() => ''))({ size: 16, class: '' });

        document.getElementById('dash-stats').innerHTML = `
            <div class="stat-card" role="status" aria-label="API 状态：${healthOk ? '正常' : '异常'}">
                <div class="stat-label">API 状态</div>
                <div class="stat-value ${healthOk ? 'stat-positive' : 'stat-negative'}">
                    ${healthOk ? checkIcon + ' 正常' : checkIcon + ' 异常'}
                </div>
                <div class="stat-sub">${healthOk ? '服务运行中' : '无法连接'}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">可用策略</div>
                <div class="stat-value stat-neutral">
                    ${strategiesData.status === 'fulfilled' ? strategiesData.value.strategies.length : '—'}
                </div>
                <div class="stat-sub">已注册策略数</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">数据源</div>
                <div class="stat-value stat-neutral">
                    ${datasourcesData.status === 'fulfilled' ? datasourcesData.value.datasources.length : '—'}
                </div>
                <div class="stat-sub">可用数据源数</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">股票分组</div>
                <div class="stat-value stat-neutral">
                    ${groupsData.status === 'fulfilled' ? groupsData.value.groups.length : '—'}
                </div>
                <div class="stat-sub">已配置分组数</div>
            </div>
        `;

        // 策略标签
        const stratEl = document.getElementById('dash-strategies');
        if (strategiesData.status === 'fulfilled' && strategiesData.value.strategies.length) {
            stratEl.innerHTML = strategiesData.value.strategies.map(s => `<span class="tag">${escapeHtml(s)}</span>`).join(' ');
        } else {
            stratEl.innerHTML = '<span style="color:var(--text-muted);">暂无策略</span>';
        }

        // 数据源标签
        const dsEl = document.getElementById('dash-datasources');
        if (datasourcesData.status === 'fulfilled' && datasourcesData.value.datasources.length) {
            dsEl.innerHTML = datasourcesData.value.datasources.map(d => `<span class="tag">${escapeHtml(d)}</span>`).join(' ');
        } else {
            dsEl.innerHTML = '<span style="color:var(--text-muted);">暂无数据源</span>';
        }
    }

    // 注册路由
    if (typeof Router !== 'undefined') {
        Router.register('/', render);
    }
})();
