/**
 * 插件页面通用公共逻辑（阶段二重构版）
 * 基于 HttpOnly Cookie + CSRF 双提交的新鉴权模型：
 * 1. 会话 token 由后端写入 HttpOnly Cookie，浏览器自动携带，前端无需读取
 * 2. CSRF token 由后端写入非 HttpOnly csrf_token Cookie，前端统一注入 X-CSRF-Token 头
 * 3. 全局请求拦截：XHR 与 fetch 统一注入 CSRF 头、统一处理 401/403
 * 4. 页面加载校验登录态（调用 /api/auth/user/info，Cookie 自动携带）
 */
(function() {
    'use strict';

    const CONFIG = {
        // 跳过登录态自动校验的页面路径
        skipAuthPaths: ['/login', '/403', '/404', '/'],
        // 登录态校验延迟（毫秒）
        authCheckDelay: 300
    };

    // ------------------------------ Cookie 工具 ------------------------------
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) {
            const v = parts.pop().split(';').shift();
            return v ? v : null;
        }
        return null;
    }

    function clearCookie(name) {
        document.cookie = `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
    }

    // ------------------------------ 公共 API ------------------------------
    window.PluginCommon = {
        // 获取 CSRF token（非 HttpOnly，前端可读）
        getCsrfToken: function() {
            return getCookie('csrf_token');
        },

        // 校验登录态：调用 user/info（Cookie 自动携带）
        isLoggedIn: function() {
            return new Promise((resolve) => {
                const xhr = new XMLHttpRequest();
                xhr.open('GET', '/api/auth/user/info', true);
                xhr.withCredentials = true;
                xhr.onreadystatechange = function() {
                    if (xhr.readyState === 4) {
                        resolve(xhr.status === 200);
                    }
                };
                xhr.onerror = function() { resolve(false); };
                xhr.send();
            });
        },

        // 跳转到登录页，携带当前页面为跳转来源
        redirectToLogin: function() {
            if (window.location.pathname === '/login') return;
            const redirect = encodeURIComponent(window.location.pathname + window.location.search);
            window.location.replace(`/login?redirect=${redirect}`);
        },

        // 跳转到403页面（后端已提供 /403 路由）
        redirectTo403: function(message) {
            if (window.location.pathname === '/403') return;
            const msg = encodeURIComponent(message || '权限不足');
            window.location.href = `/403?message=${msg}`;
        },

        // 通用请求封装（供插件业务代码调用）
        request: function(options) {
            return new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                xhr.open(options.method || 'GET', options.url, true);
                xhr.withCredentials = true;

                // 统一注入 CSRF 头（非安全方法）
                // 注：不再手动注入——本文件下方全局 XHR send 拦截已统一注入一次；
                // 若此处再注入，setRequestHeader 同名头会逗号拼接成 "token, token"，
                // 后端 CSRF 双提交校验失败返回 403（复核 2026-08-26 确认）。
                if (options.headers) {
                    Object.keys(options.headers).forEach(k => xhr.setRequestHeader(k, options.headers[k]));
                }

                xhr.onload = function() {
                    try {
                        const res = JSON.parse(xhr.responseText);
                        // 鉴权状态特殊处理（401 跳登录、403 跳 403 页）
                        if (xhr.status === 401) {
                            if (window.location.pathname !== '/login') {
                                clearCookie('csrf_token');
                                PluginCommon.redirectToLogin();
                            }
                            reject(new Error('未登录'));
                        } else if (xhr.status === 403) {
                            PluginCommon.redirectTo403(res.message || '权限不足');
                            reject(new Error('权限不足'));
                        } else {
                            // 业务结果以 body.code 判断（阶段三 Step5：error_response 现带 HTTP 4xx/5xx 状态码，
                            // 此处统一 resolve 由调用方按 res.code 处理，保持与旧行为一致）
                            resolve(res);
                        }
                    } catch (e) { reject(e); }
                };
                xhr.onerror = function() { reject(new Error('网络请求失败')); };

                let sendData = options.data;
                if (sendData && !(sendData instanceof FormData) && typeof sendData === 'object') {
                    sendData = JSON.stringify(sendData);
                    if (!options.headers || !options.headers['Content-Type']) {
                        xhr.setRequestHeader('Content-Type', 'application/json');
                    }
                }
                xhr.send(sendData);
            });
        }
    };

    // ------------------------------ 全局请求拦截（XHR + fetch 统一） ------------------------------
    const originalOpen = XMLHttpRequest.prototype.open;
    const originalSend = XMLHttpRequest.prototype.send;

    XMLHttpRequest.prototype.open = function(method, url, async, user, password) {
        this._fx_method = (method || 'GET').toUpperCase();
        this._fx_url = url;
        this._fx_onload = null;
        return originalOpen.apply(this, arguments);
    };

    XMLHttpRequest.prototype.send = function(body) {
        this.withCredentials = true;
        // 非安全方法注入 CSRF 头（OPENED 状态下 setRequestHeader 才有效）
        if (!['GET', 'HEAD', 'OPTIONS'].includes(this._fx_method)) {
            const csrf = PluginCommon.getCsrfToken();
            if (csrf) {
                try { this.setRequestHeader('X-CSRF-Token', csrf); } catch (e) {}
            }
        }
        // 统一 401/403 响应处理（避免重复绑定）
        if (!this._fx_onload) {
            this._fx_onload = true;
            this.addEventListener('load', function() {
                handleAuthStatus(this.status, this.responseText);
            });
        }
        return originalSend.apply(this, arguments);
    };

    // fetch 拦截
    const originalFetch = window.fetch;
    window.fetch = function(resource, init = {}) {
        init.credentials = init.credentials || 'include';
        init.headers = new Headers(init.headers || {});
        const method = (init.method || 'GET').toUpperCase();
        if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
            const csrf = PluginCommon.getCsrfToken();
            if (csrf && !init.headers.has('X-CSRF-Token')) {
                init.headers.set('X-CSRF-Token', csrf);
            }
        }
        return originalFetch.call(this, resource, init).then(response => {
            if (response.status === 401 || response.status === 403) {
                response.clone().json().then(res => {
                    handleAuthStatus(response.status, res && res.message);
                }).catch(() => handleAuthStatus(response.status, ''));
            }
            return response;
        });
    };

    // 统一状态处理：401 跳登录，403 跳 403 页
    function handleAuthStatus(status, text) {
        if (window.location.pathname === '/login') return;
        let message = '';
        if (text) {
            try {
                const res = JSON.parse(text);
                message = res.message || '';
            } catch (e) {}
        }
        if (status === 401) {
            clearCookie('csrf_token');
            PluginCommon.redirectToLogin();
        } else if (status === 403) {
            PluginCommon.redirectTo403(message || '权限不足');
        }
    }

    // ------------------------------ 页面加载时自动校验登录态 ------------------------------
    document.addEventListener('DOMContentLoaded', function() {
        const currentPath = window.location.pathname;
        if (CONFIG.skipAuthPaths.includes(currentPath)) return;
        // 无 csrf_token Cookie（从未登录过）不触发自动校验，避免 auth 未安装时误跳登录
        if (!PluginCommon.getCsrfToken()) return;

        setTimeout(() => {
            PluginCommon.isLoggedIn().then(ok => {
                if (!ok && window.location.pathname !== '/login') {
                    PluginCommon.redirectToLogin();
                }
            });
        }, CONFIG.authCheckDelay);
    });
})();
