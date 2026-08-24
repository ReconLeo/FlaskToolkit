/* ============================================================
   FlaskToolkit 裸插件调试页（plugin_default）：API 调用测试工具
   在保持原参数收集/调用语义基础上增强：
   - CSRF：非安全方法自动携带 X-CSRF-Token（读 csrf_token Cookie）
   - 路径参数：<name> / <int:name> 占位符替换为输入值
   - PUT/DELETE/PATCH 与 POST 一致发送 JSON body
   - 响应展示：HTTP 状态码 / 耗时 / 业务 code / 实际请求 URL
   - 结果：一键复制、折叠 / 展开
   - 请求历史：会话内最近调用记录（可清空）
   ============================================================ */
(function () {
    'use strict';

    // ---------- 会话内请求历史 ----------
    const history = [];

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function renderHistory() {
        const body = document.getElementById('historyBody');
        const count = document.getElementById('historyCount');
        if (!body) return;
        body.innerHTML = history.slice(0, 50).map(function (h) {
            return '<tr>' +
                '<td>' + h.time + '</td>' +
                '<td><span class="method-badge ' + h.method + '">' + h.method + '</span></td>' +
                '<td class="history-path" title="' + escapeHtml(h.path) + '">' + escapeHtml(h.path) + '</td>' +
                '<td>' + h.status + '</td>' +
                '<td>' + h.elapsed + ' ms</td>' +
                '</tr>';
        }).join('');
        if (count) count.textContent = '（' + history.length + ' 次）';
    }

    function pushHistory(method, path, status, elapsed) {
        history.unshift({
            time: new Date().toLocaleTimeString(),
            method: method,
            path: path,
            status: status,
            elapsed: elapsed
        });
        renderHistory();
    }

    // ---------- 工具函数 ----------
    function getCookie(name) {
        if (window.FT && window.FT.getCookie) return window.FT.getCookie(name);
        const value = '; ' + document.cookie;
        const parts = value.split('; ' + name + '=');
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    /**
     * 尝试将字符串解析为 JSON 值（对象/数组），失败则返回原字符串
     */
    function tryParseJSON(value) {
        if (typeof value !== 'string' || value.trim() === '') {
            return value;
        }
        const trimmed = value.trim();
        if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
            try {
                return JSON.parse(trimmed);
            } catch (e) {
                return value;
            }
        }
        return value;
    }

    // ---------- 结果工具条：复制 / 折叠 ----------
    window.copyResult = function (btn) {
        const card = btn.closest('.api-card');
        const resultEl = card.querySelector('.result');
        if (!resultEl || !resultEl.dataset.raw) return;
        const text = resultEl.dataset.raw;
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(function () {
                btn.textContent = '✓ 已复制';
                setTimeout(function () { btn.textContent = '📋 复制结果'; }, 1500);
            }).catch(function () {
                fallbackCopy(text, btn);
            });
        } else {
            fallbackCopy(text, btn);
        }
    };

    function fallbackCopy(text, btn) {
        try {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            btn.textContent = '✓ 已复制';
            setTimeout(function () { btn.textContent = '📋 复制结果'; }, 1500);
        } catch (e) {
            btn.textContent = '复制失败';
        }
    }

    window.toggleFoldResult = function (btn) {
        const card = btn.closest('.api-card');
        const resultEl = card.querySelector('.result');
        if (!resultEl) return;
        const folded = resultEl.classList.toggle('collapsed');
        btn.textContent = folded ? '展开' : '折叠';
    };

    // ---------- 主调用 ----------
    window.callApi = function (routePath, method, button) {
        const card = button.closest('.api-card');
        const paramElements = card.querySelectorAll('.param');
        const resultEl = card.querySelector('.result');
        const toolbarEl = card.querySelector('.result-toolbar');
        const statusEl = card.querySelector('.call-status');
        const urlEl = card.querySelector('.request-url');

        // ===== 1. 路径参数替换（<name> 或 <int:name>） =====
        let path = routePath;
        let missingPath = false;
        const pathInputs = card.querySelectorAll('.path-param-input');
        pathInputs.forEach(function (el) {
            const name = el.dataset.pathParam;
            const val = (el.value || '').trim();
            if (!val) {
                missingPath = true;
                return;
            }
            // 匹配 <name> 或 <int:name> 等带转换器的占位符
            const re = new RegExp('<(?:[^:>]+:)?' + name + '>');
            path = path.replace(re, encodeURIComponent(val));
        });
        if (missingPath) {
            resultEl.style.display = 'block';
            resultEl.textContent = '请填写所有必填的路径参数';
            if (toolbarEl) toolbarEl.style.display = 'none';
            return;
        }

        // ===== 2. 收集普通参数（保持原有语义） =====
        const params = {};
        let hasFiles = false;
        const formData = new FormData();

        paramElements.forEach(function (el) {
            // 跳过路径参数输入框（已单独处理）
            if (el.classList.contains('path-param-input')) return;
            const name = el.dataset.name;
            const type = el.dataset.type;

            if (type === 'file') {
                const files = el.files;
                if (files && files.length > 0) {
                    hasFiles = true;
                    formData.append(name, files[0]);
                }
                return;
            }

            const rawValue = el.value;
            if (rawValue === '' || rawValue === null || rawValue === undefined) {
                return;
            }

            if (type === 'array' || type === 'object') {
                params[name] = tryParseJSON(rawValue);
            } else if (type === 'boolean') {
                params[name] = rawValue;
            } else if (type === 'number' || type === 'int') {
                const num = Number(rawValue);
                params[name] = isNaN(num) ? rawValue : num;
            } else {
                params[name] = rawValue;
            }
        });

        // ===== 3. 构造请求（方法语义：POST/PUT/DELETE/PATCH 走 JSON body） =====
        const methodUpper = (method || 'GET').toUpperCase();
        const options = { method: methodUpper, headers: {} };

        if (hasFiles) {
            for (const [key, value] of Object.entries(params)) {
                formData.append(key, typeof value === 'object' ? JSON.stringify(value) : String(value));
            }
            options.body = formData;
        } else if (['POST', 'PUT', 'DELETE', 'PATCH'].indexOf(methodUpper) >= 0) {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(params);
        } else {
            const urlParams = new URLSearchParams();
            for (const [key, value] of Object.entries(params)) {
                urlParams.append(key, typeof value === 'object' ? JSON.stringify(value) : String(value));
            }
            const queryString = urlParams.toString();
            if (queryString) {
                path += '?' + queryString;
            }
        }

        // ===== 4. CSRF：非安全方法自动携带 X-CSRF-Token =====
        if (['POST', 'PUT', 'DELETE', 'PATCH'].indexOf(methodUpper) >= 0) {
            const csrf = getCookie('csrf_token');
            if (csrf) options.headers['X-CSRF-Token'] = csrf;
        }

        // ===== 5. 发起请求并展示 =====
        resultEl.style.display = 'block';
        resultEl.textContent = '请求中...';
        if (toolbarEl) toolbarEl.style.display = 'none';
        if (urlEl) urlEl.style.display = 'none';
        if (statusEl) statusEl.textContent = '';
        if (button) button.disabled = true;
        const start = performance.now();

        fetch(path, options)
            .then(function (res) {
                return res.text().then(function (text) {
                    return { status: res.status, text: text };
                });
            })
            .then(function (res) {
                const elapsed = Math.round(performance.now() - start);
                let data;
                try { data = JSON.parse(res.text); } catch (e) { data = { raw: res.text }; }
                const bizCode = (data && typeof data === 'object') ? data.code : null;
                const meta = 'HTTP ' + res.status + ' · ' + elapsed + ' ms' + (bizCode ? ' · code ' + bizCode : '');

                resultEl.style.display = 'block';
                resultEl.dataset.raw = res.text;
                resultEl.textContent = res.text;
                if (toolbarEl) toolbarEl.style.display = 'block';
                if (urlEl) { urlEl.style.display = 'block'; urlEl.textContent = '请求: ' + path; }
                if (statusEl) statusEl.textContent = meta;
                pushHistory(methodUpper, path, res.status, elapsed);
            })
            .catch(function (err) {
                const elapsed = Math.round(performance.now() - start);
                resultEl.style.display = 'block';
                resultEl.dataset.raw = '错误: ' + err.message;
                resultEl.textContent = '错误: ' + err.message;
                if (toolbarEl) toolbarEl.style.display = 'none';
                if (urlEl) { urlEl.style.display = 'block'; urlEl.textContent = '请求: ' + path; }
                if (statusEl) statusEl.textContent = '请求失败';
                pushHistory(methodUpper, path, 'ERR', elapsed);
            })
            .finally(function () {
                if (button) button.disabled = false;
            });
    };

    // ---------- 初始化：清空历史 ----------
    function init() {
        const clearBtn = document.getElementById('historyClear');
        if (clearBtn) {
            clearBtn.addEventListener('click', function () {
                history.length = 0;
                renderHistory();
            });
        }
        renderHistory();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
