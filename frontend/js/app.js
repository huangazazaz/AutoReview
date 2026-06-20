/**
 * AutoTrade 前端应用入口
 * 初始化路由、全局工具函数、UI 交互
 */
(function () {
    'use strict';

    // ---- 全局工具函数 ----

    /** HTML 转义 */
    window.escapeHtml = function (str) {
        if (str == null) return '';
        const div = document.createElement('div');
        div.textContent = String(str);
        return div.innerHTML;
    };

    /** 格式化数字 */
    window.formatNumber = function (num, decimals = 2) {
        if (num == null || isNaN(num)) return '—';
        return Number(num).toLocaleString('zh-CN', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        });
    };

    /** 格式化金额 */
    window.formatMoney = function (num) {
        if (num == null || isNaN(num)) return '—';
        return Number(num).toLocaleString('zh-CN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    };

    /** 格式化成交量（股） */
    window.formatVolume = function (num) {
        if (num == null || isNaN(num)) return '—';
        if (num >= 1e8) return (num / 1e8).toFixed(2) + ' 亿';
        if (num >= 1e4) return (num / 1e4).toFixed(2) + ' 万';
        return Number(num).toLocaleString('zh-CN');
    };

    /** 格式化金额（简略: 亿 / 万） */
    window.formatAmount = function (num) {
        if (num == null || isNaN(num)) return '—';
        const abs = Math.abs(num);
        if (abs >= 1e8) return '¥' + (num / 1e8).toFixed(2) + ' 亿';
        if (abs >= 1e4) return '¥' + (num / 1e4).toFixed(2) + ' 万';
        return '¥' + Number(num).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    };

    /** 百分比格式化 */
    window.formatPct = function (num) {
        if (num == null || isNaN(num)) return '—';
        return (num >= 0 ? '+' : '') + num.toFixed(2) + '%';
    };

    /** 显示加载遮罩 */
    window.showLoading = function (msg = '加载中...') {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.querySelector('p').textContent = msg;
            overlay.style.display = 'flex';
            overlay.setAttribute('aria-busy', 'true');
        }
    };

    /** 隐藏加载遮罩 */
    window.hideLoading = function () {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.display = 'none';
            overlay.setAttribute('aria-busy', 'false');
        }
    };

    /**
     * 渲染骨架屏
     * @param {string} type - 'card' | 'table' | 'text'
     * @param {number} count - 骨架块数量
     * @returns {string} HTML
     */
    window.renderSkeleton = function (type = 'text', count = 3) {
        if (type === 'card') {
            let html = '<div class="stats-grid">';
            for (let i = 0; i < count; i++) {
                html += '<div class="stat-card"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text"></div></div>';
            }
            html += '</div>';
            return html;
        }
        if (type === 'table') {
            let html = '';
            for (let i = 0; i < count; i++) {
                html += `<div class="skeleton skeleton-row" style="margin-bottom:8px;"></div>`;
            }
            return html;
        }
        // text
        let html = '';
        for (let i = 0; i < count; i++) {
            html += '<div class="skeleton skeleton-text"></div>';
        }
        return html;
    };

    /** Toast 消息 */
    window.showToast = function (msg, type = 'info', duration = 3000) {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.setAttribute('role', type === 'error' || type === 'warning' ? 'alert' : 'status');

        // 图标
        let iconSvg = '';
        if (typeof Icon !== 'undefined') {
            if (type === 'success') iconSvg = Icon.check({ size: 18, class: 'toast-icon' });
            else if (type === 'error') iconSvg = Icon.xCircle({ size: 18, class: 'toast-icon' });
            else if (type === 'warning') iconSvg = Icon.alert({ size: 18, class: 'toast-icon' });
            else iconSvg = Icon.info({ size: 18, class: 'toast-icon' });
        }

        toast.innerHTML = `${iconSvg}<span>${escapeHtml(msg)}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.2s';
            setTimeout(() => toast.remove(), 200);
        }, duration);
    };

    /** 确认对话框（简单版） */
    window.showConfirm = function (msg) {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            overlay.setAttribute('role', 'dialog');
            overlay.setAttribute('aria-modal', 'true');
            overlay.setAttribute('aria-labelledby', 'confirm-title');
            overlay.innerHTML = `
                <div class="modal" style="max-width:400px;">
                    <div class="modal-header">
                        <span class="modal-title" id="confirm-title">确认操作</span>
                        <button class="modal-close" aria-label="关闭">&times;</button>
                    </div>
                    <div class="modal-body">
                        <p style="color:var(--text-secondary);">${escapeHtml(msg)}</p>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary cancel-btn">取消</button>
                        <button class="btn btn-danger confirm-btn">确认</button>
                    </div>
                </div>`;
            document.body.appendChild(overlay);

            const close = () => overlay.remove();
            overlay.querySelector('.modal-close').onclick = () => { close(); resolve(false); };
            overlay.querySelector('.cancel-btn').onclick = () => { close(); resolve(false); };
            overlay.querySelector('.confirm-btn').onclick = () => { close(); resolve(true); };
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) { close(); resolve(false); }
            });
            // ESC key
            const escHandler = (e) => {
                if (e.key === 'Escape') { close(); resolve(false); document.removeEventListener('keydown', escHandler); }
            };
            document.addEventListener('keydown', escHandler);
        });
    };

    /** 显示模态框 */
    window.showModal = function (title, bodyHtml, footerHtml = '') {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            overlay.setAttribute('role', 'dialog');
            overlay.setAttribute('aria-modal', 'true');
            overlay.setAttribute('aria-labelledby', 'modal-title');
            overlay.innerHTML = `
                <div class="modal">
                    <div class="modal-header">
                        <span class="modal-title" id="modal-title">${escapeHtml(title)}</span>
                        <button class="modal-close" aria-label="关闭">&times;</button>
                    </div>
                    <div class="modal-body">${bodyHtml}</div>
                    ${footerHtml ? `<div class="modal-footer">${footerHtml}</div>` : ''}
                </div>`;
            document.body.appendChild(overlay);

            const close = () => overlay.remove();
            overlay.querySelector('.modal-close').onclick = close;
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) close();
            });
            // ESC key
            const escHandler = (e) => {
                if (e.key === 'Escape') { close(); document.removeEventListener('keydown', escHandler); }
            };
            document.addEventListener('keydown', escHandler);

            resolve(overlay);
        });
    };

    /** 安全执行 async 操作 */
    window.safeAsync = async function (fn, errorMsg = '操作失败') {
        try {
            return await fn();
        } catch (err) {
            console.error(err);
            showToast(errorMsg + '：' + err.message, 'error');
            return null;
        }
    };

    // ---- 侧边栏交互 ----
    const menuToggle = document.getElementById('menu-toggle');
    const sidebar = document.getElementById('sidebar');

    if (menuToggle && sidebar) {
        menuToggle.addEventListener('click', () => {
            const isOpen = sidebar.classList.toggle('open');
            menuToggle.setAttribute('aria-expanded', String(isOpen));
            menuToggle.setAttribute('aria-label', isOpen ? '关闭菜单' : '打开菜单');
        });

        // 点击主内容区关闭侧边栏
        const viewContainer = document.getElementById('view-container');
        if (viewContainer) {
            viewContainer.addEventListener('click', () => {
                if (sidebar.classList.contains('open')) {
                    sidebar.classList.remove('open');
                    menuToggle.setAttribute('aria-expanded', 'false');
                    menuToggle.setAttribute('aria-label', '打开菜单');
                }
            });
        }
    }

    // ---- 启动应用 ----
    console.log('AutoTrade Frontend v0.1.0 — Swiss Minimal Design');

    // 确保路由在所有视图注册后初始化
    if (typeof Router !== 'undefined') {
        Router.init();
    } else {
        window.addEventListener('load', () => {
            if (typeof Router !== 'undefined') Router.init();
        });
    }
})();
