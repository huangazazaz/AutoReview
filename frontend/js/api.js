/**
 * AutoTrade API 客户端
 * 统一封装所有后端 API 请求，处理错误和加载状态
 */

const API = (() => {
    const BASE = '';

    /**
     * 通用 fetch 封装
     */
    async function request(method, path, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (body !== null) {
            opts.body = JSON.stringify(body);
        }

        let res;
        try {
            res = await fetch(BASE + path, opts);
        } catch (err) {
            throw new Error(`网络错误：无法连接到服务器 (${err.message})`);
        }

        const data = await res.json();

        if (!res.ok) {
            // FastAPI 422 校验错误
            if (res.status === 422 && data.detail) {
                const msgs = data.detail.map(d => `${d.loc.join('.')}: ${d.msg}`).join('; ');
                throw new Error(`参数校验失败：${msgs}`);
            }
            throw new Error(data.error || data.detail || `请求失败 (HTTP ${res.status})`);
        }

        if (data.error) {
            throw new Error(data.error);
        }

        return data;
    }

    /** GET 请求 */
    function get(path) { return request('GET', path); }

    /** POST 请求 */
    function post(path, body) { return request('POST', path, body); }

    /** PUT 请求 */
    function put(path, body) { return request('PUT', path, body); }

    /** DELETE 请求 */
    function del(path) { return request('DELETE', path); }

    // ---- 公开 API ----

    /** 健康检查 */
    function health() { return get('/health'); }

    /**
     * 单股分析回测
     * @param {Object} params - { symbol, strategy?, start?, end?, period?, datasource? }
     */
    function analyze(params) { return post('/analyze', params); }

    /**
     * 批量回测
     * @param {Object} params - { strategy?, symbols?, group?, start?, end?, period?, datasource? }
     */
    function backtest(params) { return post('/backtest', params); }

    /**
     * 日线数据查询
     * @param {Object} params - { symbol, start?, end?, period? }
     */
    function getBars(params) { return post('/bars', params); }

    /** 获取策略列表 */
    function getStrategies() { return get('/strategies'); }

    /** 获取数据源列表 */
    function getDatasources() { return get('/datasources'); }

    /** 获取所有分组 */
    function getGroups() { return get('/groups'); }

    /** 获取单个分组 */
    function getGroup(id) { return get(`/groups/${encodeURIComponent(id)}`); }

    /** 创建分组 */
    function createGroup(data) { return post('/groups', data); }

    /** 更新分组 */
    function updateGroup(id, data) { return put(`/groups/${encodeURIComponent(id)}`, data); }

    /** 删除分组 */
    function deleteGroup(id) { return del(`/groups/${encodeURIComponent(id)}`); }

    /** 获取本地缓存的股票列表 */
    function getCachedStocks() { return get('/cache/stocks'); }

    return {
        health,
        analyze,
        backtest,
        getBars,
        getStrategies,
        getDatasources,
        getGroups,
        getGroup,
        createGroup,
        updateGroup,
        deleteGroup,
        getCachedStocks,
    };
})();
