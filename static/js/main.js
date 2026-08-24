/* ============================================================
   FlaskToolkit 公共脚本（登录态检测 / 登出 / 工具函数）
   适用页面：index / plugin_default / login / logout
   ============================================================ */
(function (window) {
    'use strict';

    /** 读取 Cookie */
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    /** 清除 Cookie（按名称与 path） */
    function clearCookie(name, path) {
        document.cookie = `${name}=; path=${path || '/'}; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
    }

    /**
     * 检测当前登录态（HttpOnly Cookie 自动携带）
     * @returns {Promise<{loggedIn:boolean, user:object|null}>}
     */
    function checkAuth() {
        return new Promise(function (resolve) {
            const xhr = new XMLHttpRequest();
            xhr.open('GET', '/api/auth/user/info', true);
            xhr.withCredentials = true;
            xhr.onreadystatechange = function () {
                if (xhr.readyState !== 4) return;
                if (xhr.status === 200) {
                    try {
                        const res = JSON.parse(xhr.responseText);
                        if (res.code === 200 && res.data) {
                            resolve({ loggedIn: true, user: res.data });
                            return;
                        }
                    } catch (e) { /* fallthrough */ }
                }
                resolve({ loggedIn: false, user: null });
            };
            xhr.send();
        });
    }

    /**
     * 调用登出接口（清理会话 Cookie 与本地残留）
     * @param {Object} [opts] {redirect: string}
     */
    function doLogout(opts) {
        const options = opts || {};
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/auth/logout', true);
        xhr.withCredentials = true;
        const token = getCookie('token');
        if (token) xhr.setRequestHeader('X-Token', token);
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4) return;
            try { localStorage.removeItem('token'); } catch (e) { /* ignore */ }
            if (options.redirect) {
                window.location.href = options.redirect;
            } else {
                window.location.href = '/login';
            }
        };
        xhr.send();
    }

    window.FT = {
        getCookie: getCookie,
        clearCookie: clearCookie,
        checkAuth: checkAuth,
        doLogout: doLogout
    };
})(window);
