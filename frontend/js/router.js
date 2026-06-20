/**
 * Hash 路由 —— 轻量 SPA 路由
 * 路由表： #/ → dashboard, #/analyze → analyze, #/backtest → backtest, etc.
 */

const Router = (() => {
    const routes = {};

    /**
     * 注册路由
     * @param {string} path - 如 '/analyze'
     * @param {Function} handler - 渲染函数
     */
    function register(path, handler) {
        routes[path] = handler;
    }

    /**
     * 导航到指定路由
     * @param {string} path - 如 '/analyze'
     */
    function navigate(path) {
        window.location.hash = '#' + path;
    }

    /**
     * 获取当前路径
     */
    function currentPath() {
        const hash = window.location.hash.slice(1) || '/';
        return hash.split('?')[0]; // 去掉查询参数
    }

    /**
     * 处理路由变化
     */
    function handleRoute() {
        const path = currentPath();
        const handler = routes[path];

        // 高亮导航项
        document.querySelectorAll('.nav-item').forEach(el => {
            const route = el.getAttribute('data-route');
            el.classList.toggle('active', route === path);
        });

        // 关闭移动端侧边栏
        document.getElementById('sidebar')?.classList.remove('open');

        const container = document.getElementById('view-container');
        if (!container) return;

        if (handler) {
            try {
                handler(container);
            } catch (err) {
                console.error('路由渲染错误:', err);
                container.innerHTML = `<div class="error-banner">页面渲染失败：${escapeHtml(err.message)}</div>`;
            }
        } else {
            const _ = window.Icon || {};
            const Search = _.search || (() => '');
            container.innerHTML = `
                <div class="empty-state">
                    <span class="empty-icon">${Search({ size: 48 })}</span>
                    <p>页面不存在：${escapeHtml(path)}</p>
                </div>`;
        }
    }

    /**
     * 初始化路由
     */
    function init() {
        window.addEventListener('hashchange', handleRoute);
        // 首次加载
        if (window.location.hash === '') {
            navigate('/');
        } else {
            handleRoute();
        }
    }

    return { register, navigate, currentPath, init };
})();
