/* ============================================================
   FlaskToolkit 裸插件调试页（plugin_default）：API 调用测试工具
   逻辑与框架版本保持一致（重要测试工具，改动需谨慎）
   ============================================================ */
(function () {
    'use strict';

    /**
     * 尝试将字符串解析为 JSON 值（对象/数组），失败则返回原字符串
     */
    function tryParseJSON(value) {
        if (typeof value !== 'string' || value.trim() === '') {
            return value;
        }
        const trimmed = value.trim();
        // 只有以 { 或 [ 开头的才尝试 JSON 解析，避免误伤普通字符串
        if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
            try {
                return JSON.parse(trimmed);
            } catch (e) {
                return value;  // 解析失败，保持原字符串
            }
        }
        return value;
    }

    /**
     * 调用插件 API
     * @param {string} path     API 路径（含占位符替换后的路径）
     * @param {string} method   HTTP 方法
     * @param {HTMLElement} button 触发按钮（用于定位卡片）
     */
    window.callApi = function (path, method, button) {
        const card = button.closest('.api-card');
        const paramElements = card.querySelectorAll('.param');
        const resultEl = card.querySelector('.result');
        const statusEl = card.querySelector('.call-status');

        const params = {};
        let hasFiles = false;
        const formData = new FormData();

        paramElements.forEach(function (el) {
            const name = el.dataset.name;
            const type = el.dataset.type;

            // 文件类型特殊处理
            if (type === 'file') {
                const files = el.files;
                if (files && files.length > 0) {
                    hasFiles = true;
                    formData.append(name, files[0]);
                }
                return;
            }

            const rawValue = el.value;
            // 空值跳过
            if (rawValue === '' || rawValue === null || rawValue === undefined) {
                return;
            }

            // 根据类型进行 JSON 化处理
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

        const options = { method: method, headers: {} };

        if (hasFiles) {
            // 文件上传：使用 FormData，不设置 Content-Type（让浏览器自动设置）
            for (const [key, value] of Object.entries(params)) {
                formData.append(key, typeof value === 'object' ? JSON.stringify(value) : String(value));
            }
            options.body = formData;
        } else if (method.toUpperCase() === 'POST') {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(params);
        } else {
            // GET 请求：将参数拼接到 URL 查询字符串
            const urlParams = new URLSearchParams();
            for (const [key, value] of Object.entries(params)) {
                urlParams.append(key, typeof value === 'object' ? JSON.stringify(value) : String(value));
            }
            const queryString = urlParams.toString();
            if (queryString) {
                path += '?' + queryString;
            }
        }

        resultEl.style.display = 'block';
        resultEl.textContent = '请求中...';
        if (statusEl) statusEl.textContent = '';
        if (button) button.disabled = true;

        fetch(path, options)
            .then(function (res) { return res.json(); })
            .then(function (data) {
                resultEl.style.display = 'block';
                resultEl.textContent = JSON.stringify(data, null, 2);
                if (statusEl) statusEl.textContent = 'HTTP ' + (data && data.code ? data.code : '');
            })
            .catch(function (err) {
                resultEl.style.display = 'block';
                resultEl.textContent = '错误: ' + err.message;
                if (statusEl) statusEl.textContent = '请求失败';
            })
            .finally(function () {
                if (button) button.disabled = false;
            });
    };
})();
