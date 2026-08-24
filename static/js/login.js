/* ============================================================
   FlaskToolkit 登录页：redirect 处理 / 记住用户名 / 显示密码 / 登录
   ============================================================ */
(function () {
    'use strict';

    // 跳转来源解析（禁止站外与登录页本身）
    const params = new URLSearchParams(window.location.search);
    let redirectUrl = params.get('redirect') || '/';
    redirectUrl = decodeURIComponent(redirectUrl).replace(/[?&]$/, '');
    if (redirectUrl.startsWith('/login') || !redirectUrl.startsWith('/')) {
        redirectUrl = '/';
    }
    window.goRedirect = function () { window.location.replace(redirectUrl); };

    // 记住用户名
    const REMEMBER_KEY = 'ftk_remember_username';

    function restoreRemember() {
        try {
            const saved = localStorage.getItem(REMEMBER_KEY);
            if (saved) {
                document.getElementById('username').value = saved;
                document.getElementById('remember').checked = true;
                document.getElementById('password').focus();
            } else {
                document.getElementById('username').focus();
            }
        } catch (e) { /* ignore */ }
    }

    function showSuccess() {
        document.getElementById('loginForm').style.display = 'none';
        document.getElementById('successArea').style.display = 'block';
        document.getElementById('successTip').textContent =
            redirectUrl === '/' ? '3秒后自动跳转到首页...' : '3秒后自动跳转到原页面...';
        setTimeout(goRedirect, 3000);
    }

    function handleLogin() {
        const usernameEl = document.getElementById('username');
        const passwordEl = document.getElementById('password');
        const errorTip = document.getElementById('errorTip');
        const loginBtn = document.getElementById('loginBtn');
        const username = (usernameEl.value || '').trim();
        const password = (passwordEl.value || '').trim();

        if (!username || !password) {
            errorTip.textContent = '请输入用户名和密码';
            errorTip.style.display = 'block';
            return;
        }

        // 记住用户名
        try {
            if (document.getElementById('remember').checked) {
                localStorage.setItem(REMEMBER_KEY, username);
            } else {
                localStorage.removeItem(REMEMBER_KEY);
            }
        } catch (e) { /* ignore */ }

        loginBtn.disabled = true;
        loginBtn.textContent = '登录中...';
        errorTip.style.display = 'none';

        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/auth/login', true);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.withCredentials = true;
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4) return;
            loginBtn.disabled = false;
            loginBtn.textContent = '登录';
            try {
                const res = JSON.parse(xhr.responseText);
                if (xhr.status === 200 && res.code === 200 && res.data && res.data.token) {
                    // 会话 token 已由后端写入 HttpOnly Cookie，前端仅清理残留
                    try { localStorage.removeItem('token'); } catch (e) { /* ignore */ }
                    showSuccess();
                } else {
                    errorTip.textContent = res.message || res.msg || '用户名或密码错误';
                    errorTip.style.display = 'block';
                }
            } catch (e) {
                errorTip.textContent = '登录响应异常，请重试';
                errorTip.style.display = 'block';
            }
        };
        xhr.send(JSON.stringify({ username: username, password: password }));
    }

    function togglePwd() {
        const pwd = document.getElementById('password');
        const btn = document.getElementById('pwdToggle');
        const show = pwd.type === 'password';
        pwd.type = show ? 'text' : 'password';
        btn.textContent = show ? '隐藏' : '显示';
        pwd.focus();
    }

    function init() {
        // 已登录则直接显示成功页并跳转（校验会话有效性）
        FT.checkAuth().then(function (r) {
            if (r.loggedIn) {
                showSuccess();
            } else {
                FT.clearCookie('csrf_token', '/');
            }
        });

        restoreRemember();

        const loginBtn = document.getElementById('loginBtn');
        document.getElementById('password').addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !loginBtn.disabled) handleLogin();
        });
        document.getElementById('username').addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !loginBtn.disabled) handleLogin();
        });
        document.getElementById('pwdToggle').addEventListener('click', togglePwd);
        loginBtn.addEventListener('click', handleLogin);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
