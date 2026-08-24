/* ============================================================
   FlaskToolkit 首页：登录态渲染 + 工具搜索 / 排序（热度/字母）
   ============================================================ */
(function () {
    'use strict';

    // ---------- 登录态渲染 ----------
    function updateAuthUI(loggedIn, user) {
        const userInfoEl = document.getElementById('userInfo');
        const authButtonEl = document.getElementById('authButton');
        const adminBarEl = document.getElementById('adminBar');
        if (!userInfoEl || !authButtonEl || !adminBarEl) return;

        if (loggedIn && user) {
            const userName = user.nickname || user.username || '用户';
            const adminMark = user.role === 'admin'
                ? '<div class="admin-indicator" title="超级管理员">⚙️ 管理员</div>'
                : '';
            userInfoEl.innerHTML = adminMark + `
                <div class="user-avatar">${escapeHtml(userName.charAt(0).toUpperCase())}</div>
                <div class="user-text">
                    <div class="user-name">${escapeHtml(userName)}</div>
                    <div class="user-role">${escapeHtml(user.role || 'user')}</div>
                </div>`;
            authButtonEl.innerHTML = `<button id="logoutBtn" class="auth-btn logout-btn">退出登录</button>`;
            adminBarEl.classList.toggle('hidden', user.role !== 'admin');
        } else {
            userInfoEl.innerHTML = '';
            authButtonEl.innerHTML = `<a href="/login" class="auth-btn login-btn">登录</a>`;
            adminBarEl.classList.add('hidden');
        }
    }

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    // ---------- 搜索 / 排序 ----------
    function collect(card) {
        const d = card.dataset;
        return {
            el: card,
            grid: card.closest('.tools-grid'),
            title: (d.title || '').toLowerCase(),
            name: (d.name || '').toLowerCase(),
            author: (d.author || '').toLowerCase(),
            desc: (d.desc || '').toLowerCase(),
            cat: (d.category || '').toLowerCase(),
            heat: parseInt(d.heat || '0', 10) || 0
        };
    }

    function match(item, q) {
        if (!q) return true;
        return item.title.indexOf(q) >= 0 || item.name.indexOf(q) >= 0 ||
               item.author.indexOf(q) >= 0 || item.desc.indexOf(q) >= 0 ||
               item.cat.indexOf(q) >= 0;
    }

    function applyFilter(cards, q, sortMode) {
        let visibleTotal = 0;
        // 按 grid 分组处理（卡片不跨分类）
        const gridMap = new Map();
        cards.forEach(function (c) {
            if (!gridMap.has(c.grid)) gridMap.set(c.grid, []);
            gridMap.get(c.grid).push(c);
        });

        gridMap.forEach(function (group, grid) {
            const section = grid.closest('.category-section');
            let visible = group.filter(function (c) { return match(c, q); });
            if (sortMode === 'heat') {
                visible.sort(function (a, b) { return b.heat - a.heat; });
            } else if (sortMode === 'alpha') {
                visible.sort(function (a, b) {
                    return (a.title || '').localeCompare(b.title || '', 'zh');
                });
            }
            // 重建 grid：可见卡片按排序顺序在前，不可见卡片在后并隐藏
            grid.innerHTML = '';
            visible.forEach(function (c) { c.el.style.display = ''; grid.appendChild(c.el); });
            const hidden = group.filter(function (c) { return visible.indexOf(c) < 0; });
            hidden.forEach(function (c) { c.el.style.display = 'none'; grid.appendChild(c.el); });
            visibleTotal += visible.length;
            if (section) section.style.display = (visible.length === 0) ? 'none' : '';
        });

        // 空分类（无任何卡片）也隐藏
        document.querySelectorAll('.category-section').forEach(function (sec) {
            if (!sec.querySelector('.tool-card')) sec.style.display = 'none';
        });

        return visibleTotal;
    }

    function init() {
        // 登录态
        FT.checkAuth().then(function (r) { updateAuthUI(r.loggedIn, r.user); });

        // 登出（事件委托）
        document.addEventListener('click', function (e) {
            if (e.target && e.target.id === 'logoutBtn') {
                e.preventDefault();
                FT.doLogout({ redirect: '/login' });
            }
        });

        // 搜索 / 排序
        const cards = Array.prototype.slice.call(document.querySelectorAll('.tool-card')).map(collect);
        const searchEl = document.getElementById('toolSearch');
        const sortEl = document.getElementById('toolSort');
        const countEl = document.getElementById('toolCount');
        const emptyEl = document.getElementById('searchEmpty');
        if (!searchEl || !sortEl) return;

        function apply() {
            const q = (searchEl.value || '').trim().toLowerCase();
            const n = applyFilter(cards, q, sortEl.value);
            if (countEl) countEl.textContent = '共 ' + n + ' 个工具';
            if (emptyEl) emptyEl.style.display = (n === 0) ? 'block' : 'none';
        }

        searchEl.addEventListener('input', apply);
        sortEl.addEventListener('change', apply);
        apply();  // 初始填充计数
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
