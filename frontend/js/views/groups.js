/**
 * 分组管理视图 — 股票分组的 CRUD 操作
 */
(function () {
    'use strict';

    let currentGroupId = null;

    async function render(container) {
        const _ = window.Icon || {};
        const Folder = _.folder || (() => '');
        const Plus = _.plus || (() => '');
        const ArrowLeft = _.arrowLeft || (() => '');
        const File = _.folder || (() => '');

        container.innerHTML = `
            <div class="page-header" style="display:flex; align-items:center; justify-content:space-between;">
                <div>
                    <h1 class="page-title">${Folder({ size: 24 })} 分组管理</h1>
                    <p class="page-subtitle">创建和管理股票分组，用于批量回测</p>
                </div>
                <button class="btn btn-primary" id="groups-create-btn">
                    ${Plus({ size: 18 })} 新建分组
                </button>
            </div>

            <div class="split-layout">
                <!-- 左侧：分组列表 -->
                <div class="split-left">
                    <div class="card">
                        <div class="card-header">
                            <span class="card-title">分组列表</span>
                        </div>
                        <div class="card-body" id="groups-list">
                            <span style="color:var(--text-muted);">加载中...</span>
                        </div>
                    </div>
                </div>

                <!-- 右侧：分组详情 -->
                <div class="split-right">
                    <div class="card" id="groups-detail-card">
                        <div class="card-body">
                            <div class="empty-state">
                                <span class="empty-icon">${ArrowLeft({ size: 48 })}</span>
                                <p>请从左侧选择一个分组</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 加载分组列表
        await loadGroupList();

        // 新建分组按钮
        document.getElementById('groups-create-btn').addEventListener('click', () => {
            showGroupModal(null);
        });
    }

    async function loadGroupList() {
        const _ = window.Icon || {};
        const File = _.folder || (() => '');

        const data = await safeAsync(() => API.getGroups(), '加载分组列表失败');
        const listEl = document.getElementById('groups-list');
        if (!listEl) return;

        if (!data || !data.groups || data.groups.length === 0) {
            listEl.innerHTML = `<div class="empty-state"><span class="empty-icon">${File({ size: 48 })}</span><p>暂无分组</p></div>`;
            return;
        }

        listEl.innerHTML = data.groups.map(g => `
            <div class="group-list-item ${currentGroupId === g.id ? 'active' : ''}" data-group-id="${escapeHtml(g.id)}" role="button" tabindex="0">
                <span class="group-name">${escapeHtml(g.name || g.id)}</span>
                <span class="group-count">${g.symbols.length} 只</span>
            </div>
        `).join('');

        // 点击和键盘事件
        listEl.querySelectorAll('.group-list-item').forEach(item => {
            const handler = () => {
                const id = item.dataset.groupId;
                currentGroupId = id;
                listEl.querySelectorAll('.group-list-item').forEach(el => el.classList.remove('active'));
                item.classList.add('active');
                loadGroupDetail(id);
            };
            item.addEventListener('click', handler);
            item.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handler(); } });
        });
    }

    async function loadGroupDetail(groupId) {
        const _ = window.Icon || {};
        const Edit = _.edit || (() => '');
        const Trash = _.trash || (() => '');
        const File = _.folder || (() => '');

        const card = document.getElementById('groups-detail-card');
        if (!card) return;

        card.innerHTML = '<div class="card-body"><span style="color:var(--text-muted);">加载中...</span></div>';

        const data = await safeAsync(() => API.getGroup(groupId), '加载分组详情失败');
        if (!data || data.error) {
            card.innerHTML = `<div class="card-body"><div class="error-banner" role="alert">${escapeHtml(data?.error || '加载失败')}</div></div>`;
            return;
        }

        const symbols = data.symbols || [];
        card.innerHTML = `
            <div class="card-header">
                <span class="card-title">${escapeHtml(data.name || data.id)}</span>
                <div style="display:flex; gap:var(--space-2);">
                    <button class="btn btn-secondary btn-sm" id="groups-edit-btn" aria-label="编辑分组 ${escapeHtml(data.name || data.id)}">
                        ${Edit({ size: 14 })} 编辑
                    </button>
                    <button class="btn btn-danger btn-sm" id="groups-delete-btn" aria-label="删除分组 ${escapeHtml(data.name || data.id)}">
                        ${Trash({ size: 14 })} 删除
                    </button>
                </div>
            </div>
            <div class="card-body">
                <p style="color:var(--text-muted); margin-bottom:var(--space-3);">标识：<code>${escapeHtml(data.id)}</code> | 共 ${symbols.length} 只股票</p>
                ${symbols.length === 0 ? `<div class="empty-state"><span class="empty-icon">${File({ size: 48 })}</span><p>该分组暂无股票</p></div>` : `
                <div class="table-container">
                    <table aria-label="分组股票列表">
                        <thead>
                            <tr>
                                <th>代码</th>
                                <th>名称</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${symbols.map(s => `
                                <tr>
                                    <td><strong>${escapeHtml(s.code)}</strong></td>
                                    <td>${escapeHtml(s.name || '—')}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>`}
            </div>
        `;

        // 编辑按钮
        document.getElementById('groups-edit-btn').addEventListener('click', () => {
            showGroupModal(data);
        });

        // 删除按钮
        document.getElementById('groups-delete-btn').addEventListener('click', async () => {
            const confirmed = await showConfirm(`确定要删除分组「${data.name || data.id}」吗？此操作不可撤销。`);
            if (!confirmed) return;

            const result = await safeAsync(() => API.deleteGroup(data.id), '删除分组失败');
            if (result) {
                showToast(`分组「${data.id}」已删除`, 'success');
                currentGroupId = null;
                const ArrowLeft = (window.Icon || {}).arrowLeft || (() => '');
                document.getElementById('groups-detail-card').innerHTML = `
                    <div class="card-body">
                        <div class="empty-state">
                            <span class="empty-icon">${ArrowLeft({ size: 48 })}</span>
                            <p>请从左侧选择一个分组</p>
                        </div>
                    </div>`;
                await loadGroupList();
            }
        });
    }

    async function showGroupModal(groupData) {
        const _ = window.Icon || {};
        const Plus = _.plus || (() => '');
        const Close = _.close || (() => '');

        const isEdit = groupData !== null;
        const symbols = groupData?.symbols || [{ code: '', name: '' }];

        function symbolRowsHtml(syms) {
            return syms.map((s, i) => `
                <div class="symbol-row" data-index="${i}">
                    <input type="text" class="form-input code-input" placeholder="代码" value="${escapeHtml(s.code || '')}" maxlength="6" autocomplete="off">
                    <input type="text" class="form-input" placeholder="名称（可选）" value="${escapeHtml(s.name || '')}" autocomplete="off">
                    <button class="btn-icon danger remove-symbol-btn" aria-label="移除股票" title="删除">${Close({ size: 16 })}</button>
                </div>
            `).join('');
        }

        const bodyHtml = `
            <div class="form-group">
                <label class="form-label" for="modal-group-id">分组标识 <span class="required" aria-hidden="true">*</span><span class="sr-only">必填</span></label>
                <input type="text" class="form-input" id="modal-group-id" value="${escapeHtml(groupData?.id || '')}"
                    placeholder="英文/中文标识（用作文件名）" ${isEdit ? 'disabled' : ''} autocomplete="off">
            </div>
            <div class="form-group">
                <label class="form-label" for="modal-group-name">显示名称</label>
                <input type="text" class="form-input" id="modal-group-name" value="${escapeHtml(groupData?.name || '')}"
                    placeholder="可选，默认同标识" autocomplete="off">
            </div>
            <div class="form-group">
                <label class="form-label">股票列表</label>
                <div id="modal-symbols">${symbolRowsHtml(symbols)}</div>
                <button class="btn btn-secondary btn-sm" id="modal-add-symbol" style="margin-top:var(--space-2);">
                    ${Plus({ size: 14 })} 添加股票
                </button>
            </div>
        `;

        const footerHtml = `
            <button class="btn btn-secondary cancel-modal-btn">取消</button>
            <button class="btn btn-primary save-modal-btn">${isEdit ? '保存修改' : '创建分组'}</button>
        `;

        const overlay = await showModal(
            isEdit ? `编辑分组：${groupData.name || groupData.id}` : '新建分组',
            bodyHtml,
            footerHtml
        );

        if (!overlay) return;

        const idInput = overlay.querySelector('#modal-group-id');
        const nameInput = overlay.querySelector('#modal-group-name');
        const symbolsContainer = overlay.querySelector('#modal-symbols');

        // 添加股票行
        overlay.querySelector('#modal-add-symbol').addEventListener('click', () => {
            const idx = symbolsContainer.querySelectorAll('.symbol-row').length;
            const row = document.createElement('div');
            row.className = 'symbol-row';
            row.dataset.index = idx;
            row.innerHTML = `
                <input type="text" class="form-input code-input" placeholder="代码" maxlength="6" autocomplete="off">
                <input type="text" class="form-input" placeholder="名称（可选）" autocomplete="off">
                <button class="btn-icon danger remove-symbol-btn" aria-label="移除股票" title="删除">${Close({ size: 16 })}</button>
            `;
            symbolsContainer.appendChild(row);
            bindRemoveButtons(overlay);
        });

        bindRemoveButtons(overlay);

        overlay.querySelector('.cancel-modal-btn').addEventListener('click', () => overlay.remove());

        overlay.querySelector('.save-modal-btn').addEventListener('click', async () => {
            const id = idInput.value.trim();
            if (!id) {
                showToast('请输入分组标识', 'warning');
                return;
            }

            const name = nameInput.value.trim() || id;
            const symbolRows = symbolsContainer.querySelectorAll('.symbol-row');
            const symbolList = [];
            symbolRows.forEach(row => {
                const inputs = row.querySelectorAll('input');
                const code = inputs[0].value.trim();
                if (code) {
                    symbolList.push({
                        code: code,
                        name: inputs[1].value.trim(),
                    });
                }
            });

            const payload = { id, name, symbols: symbolList };

            let result;
            if (isEdit) {
                result = await safeAsync(() => API.updateGroup(groupData.id, {
                    name: payload.name,
                    symbols: payload.symbols,
                }), '更新分组失败');
            } else {
                result = await safeAsync(() => API.createGroup(payload), '创建分组失败');
            }

            if (result && !result.error) {
                showToast(isEdit ? '分组已更新' : '分组已创建', 'success');
                overlay.remove();
                currentGroupId = result.id || id;
                await loadGroupList();
                await loadGroupDetail(currentGroupId);
            } else if (result && result.error) {
                showToast(result.error, 'error');
            }
        });

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.remove();
        });
    }

    function bindRemoveButtons(container) {
        container.querySelectorAll('.remove-symbol-btn').forEach(btn => {
            btn.onclick = function () {
                const row = this.closest('.symbol-row');
                const total = container.querySelectorAll('.symbol-row').length;
                if (total <= 1) {
                    row.querySelectorAll('input').forEach(i => i.value = '');
                } else {
                    row.remove();
                }
            };
        });
    }

    // 注册路由
    if (typeof Router !== 'undefined') {
        Router.register('/groups', render);
    }
})();
