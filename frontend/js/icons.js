/**
 * AutoTrade SVG 图标库
 * 零依赖、轻量内联 SVG 图标，替代所有 emoji 使用
 * 
 * 每个函数返回一个内联 SVG 字符串，接受参数：
 * @param {Object} opts - { size: 20, class: '', stroke: 2, fill: 'none' }
 * @returns {string} SVG HTML 字符串
 * 
 * 使用 Lucide 风格设计语言 — 统一 2px 描边、rounded 端点
 */

const Icon = (() => {
    'use strict';

    /** 生成 SVG 属性字符串 */
    function attrs(size, cls, extra = '') {
        const s = size || 20;
        const c = cls ? `icon ${cls}` : 'icon';
        return `class="${c}" width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" role="img" ${extra}`;
    }

    // ==================== 导航图标 ====================

    /** 仪表盘 (Layout Dashboard) */
    function dashboard(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="仪表盘"')}>
            <rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/>
            <rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>
        </svg>`;
    }

    /** 搜索/分析 (Search) */
    function search(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="搜索分析"')}>
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>`;
    }

    /** 回测/图表 (Bar Chart) */
    function chart(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="回测图表"')}>
            <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/>
            <line x1="6" y1="20" x2="6" y2="14"/>
        </svg>`;
    }

    /** K线/Candlestick */
    function candlestick(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="K线数据"')}>
            <rect x="6" y="4" width="4" height="7" rx="0.5"/><line x1="8" y1="3" x2="8" y2="4"/>
            <line x1="8" y1="11" x2="8" y2="13"/>
            <rect x="14" y="9" width="4" height="6" rx="0.5"/><line x1="16" y1="7" x2="16" y2="9"/>
            <line x1="16" y1="15" x2="16" y2="18"/>
        </svg>`;
    }

    /** 分组/文件夹 (Folder) */
    function folder(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="分组管理"')}>
            <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.89l-.82-1.22A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/>
        </svg>`;
    }

    // ==================== 操作图标 ====================

    /** 添加 (Plus) */
    function plus(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="添加"')}>
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>`;
    }

    /** 编辑 (Edit/Pencil) */
    function edit(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="编辑"')}>
            <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>
            <path d="m15 5 4 4"/>
        </svg>`;
    }

    /** 删除/垃圾桶 (Trash) */
    function trash(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="删除"')}>
            <path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>
            <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
        </svg>`;
    }

    /** 关闭 (X) */
    function close(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="关闭"')}>
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>`;
    }

    /** 返回箭头 (Arrow Left) */
    function arrowLeft(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="返回"')}>
            <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
        </svg>`;
    }

    // ==================== 状态图标 ====================

    /** 成功/对勾 (Check) */
    function check(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="成功"')}>
            <polyline points="20 6 9 17 4 12"/>
        </svg>`;
    }

    /** 警告/三角 (Alert Triangle) */
    function alert(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="警告"')}>
            <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
            <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>`;
    }

    /** 信息 (Info) */
    function info(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="信息"')}>
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/>
            <line x1="12" y1="8" x2="12.01" y2="8"/>
        </svg>`;
    }

    /** 错误/X圆 (X Circle) */
    function xCircle(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="错误"')}>
            <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/>
            <line x1="9" y1="9" x2="15" y2="15"/>
        </svg>`;
    }

    /** 数据库 (Database) */
    function database(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="数据源"')}>
            <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
        </svg>`;
    }

    /** 策略/大脑 (Brain Circuit) */
    function brain(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="策略"')}>
            <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-2.04Z"/>
            <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-2.04Z"/>
        </svg>`;
    }

    /** 设置 (Settings/Gear) */
    function settings(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="设置"')}>
            <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
            <circle cx="12" cy="12" r="3"/>
        </svg>`;
    }

    /** 行情/趋势向上 (Trending Up) */
    function trendingUp(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="上涨趋势"')}>
            <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/>
            <polyline points="16 7 22 7 22 13"/>
        </svg>`;
    }

    /** 行情/趋势向下 (Trending Down) */
    function trendingDown(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="下跌趋势"')}>
            <polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/>
            <polyline points="16 17 22 17 22 11"/>
        </svg>`;
    }

    // ==================== 奖牌/排行图标 ====================

    function gold(opts = {}) { return medal('gold', '#F59E0B', opts); }
    function silver(opts = {}) { return medal('silver', '#94A3B8', opts); }
    function bronze(opts = {}) { return medal('bronze', '#D97706', opts); }

    function medal(type, color, opts = {}) {
        const labels = { gold: '第一名', silver: '第二名', bronze: '第三名' };
        return `<svg ${attrs(opts.size || 18, opts.class, `aria-label="${labels[type]}"`)}>
            <circle cx="12" cy="12" r="10" stroke="${color}" fill="${color}" fill-opacity="0.15"/>
            <text x="12" y="12" text-anchor="middle" dominant-baseline="central"
                font-size="12" font-weight="700" fill="${color}" stroke="none">${type === 'gold' ? '1' : type === 'silver' ? '2' : '3'}</text>
        </svg>`;
    }

    // ==================== 品牌 Logo ====================

    function logo(opts = {}) {
        const s = opts.size || 32;
        return `<svg ${attrs(s, opts.class || 'brand-logo', 'aria-label="AutoTrade"')}>
            <rect x="2" y="4" width="20" height="16" rx="3" fill="currentColor" fill-opacity="0.12"/>
            <polyline points="7 17 10 10 13 14 16 7 18 11" fill="none"/>
            <circle cx="7" cy="17" r="1" fill="currentColor" fill-opacity="0.6"/><circle cx="18" cy="11" r="1" fill="currentColor" fill-opacity="0.6"/>
        </svg>`;
    }

    // ==================== 实用图标 ====================

    /** 外部链接 (External Link) */
    function externalLink(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="外部链接"')}>
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
            <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
        </svg>`;
    }

    /** 复制 (Copy) */
    function copy(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="复制"')}>
            <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>`;
    }

    /** 刷新 (Refresh) */
    function refresh(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="刷新"')}>
            <path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/>
            <path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/>
        </svg>`;
    }

    /** 加载旋转器 (Loader Spinner) */
    function loader(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="加载中"')} class="icon-spin ${opts.class || ''}">
            <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
        </svg>`;
    }

    /** 菜单/汉堡 (Menu) */
    function menu(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="菜单"')}>
            <line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/>
            <line x1="4" y1="18" x2="20" y2="18"/>
        </svg>`;
    }

    /** 火箭/发射 (Rocket) — 用于 CTA 按钮 */
    function rocket(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="启动"')}>
            <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/>
            <path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/>
            <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/>
            <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>
        </svg>`;
    }

    /** 日历 (Calendar) */
    function calendar(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="日历"')}>
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
            <line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>
            <line x1="3" y1="10" x2="21" y2="10"/>
        </svg>`;
    }

    /** 井号 (Hash) — 用于股票代码 */
    function hash(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="代码"')}>
            <line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/>
            <line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/>
        </svg>`;
    }

    /** 右箭头 (Chevron Right) — 用于日期范围连接 */
    function chevronRight(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="至"')}>
            <polyline points="9 18 15 12 9 6"/>
        </svg>`;
    }

    /** 时钟 (Clock) — 用于周期选择 */
    function clock(opts = {}) {
        return `<svg ${attrs(opts.size, opts.class, 'aria-label="周期"')}>
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
        </svg>`;
    }

    return {
        // 导航
        dashboard, search, chart, candlestick, folder,
        // 操作
        plus, edit, trash, close, arrowLeft,
        // 状态
        check, alert, info, xCircle,
        // 数据
        database, brain,
        // 排行
        gold, silver, bronze,
        // 趋势
        trendingUp, trendingDown,
        // 品牌
        logo,
        // 工具
        externalLink, copy, refresh, loader, menu,
        settings, rocket,
        // 表单
        calendar, hash, chevronRight, clock,
    };
})();

// 导出到全局
window.Icon = Icon;
