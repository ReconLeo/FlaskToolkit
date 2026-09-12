/* v4.20 用户中心前端脚本
   依赖：/static/js/plugin_common.js（PluginCommon.request 自动带 CSRF、处理 401/403）
   能力：加载当前用户 → 修改昵称（/api/auth/user/update-nickname）、修改密码（/api/auth/change-password）、退出登录。
*/
(function () {
    'use strict';

    var T = window.T || function (k) { return k; };

    function $(id) { return document.getElementById(id); }
    function showToast(message, type) {
        var toast = $('toast');
        toast.textContent = message;
        toast.className = 'toast ' + (type || 'success');
        toast.style.display = 'block';
        clearTimeout(toast._t);
        toast._t = setTimeout(function () { toast.style.display = 'none'; }, 3000);
    }
    function setErr(id, msg) {
        var el = $(id);
        if (el) { el.textContent = msg; }
    }

    function loadUser() {
        PluginCommon.request({ url: '/api/auth/user/info' }).then(function (res) {
            if (res.code === 200 && res.data) {
                var u = res.data;
                $('uc-username').value = u.username || '';
                $('uc-nickname').value = u.nickname || u.username || '';
                $('uc-name').textContent = (u.nickname || u.username) + ' · ' +
                    (u.role === 'admin' ? T('管理员') : T('用户'));
                $('uc-avatar').textContent = (u.nickname || u.username || 'A').charAt(0).toUpperCase();
            }
        }).catch(function () {});
    }

    function submitNickname() {
        setErr('uc-nickname-err', '');
        setErr('uc-nickname-ok', '');
        var nickname = $('uc-nickname').value.trim();
        if (!nickname) { setErr('uc-nickname-err', T('昵称不能为空')); return; }
        if (nickname.length > 20) { setErr('uc-nickname-err', T('昵称长度不能超过 20 个字符')); return; }
        PluginCommon.request({
            url: '/api/auth/user/update-nickname',
            method: 'POST',
            data: { nickname: nickname }
        }).then(function (res) {
            if (res.code === 200) {
                setErr('uc-nickname-ok', res.message || T('昵称修改成功'));
                showToast(res.message || T('昵称修改成功'), 'success');
                loadUser(); // 刷新头部显示
            } else {
                setErr('uc-nickname-err', res.message || T('修改失败'));
            }
        }).catch(function () {});
    }

    function submitPassword() {
        setErr('uc-pwd-err', '');
        var oldPwd = $('uc-old-pwd').value;
        var newPwd = $('uc-new-pwd').value;
        var confirmPwd = $('uc-confirm-pwd').value;
        if (!oldPwd || !newPwd) { setErr('uc-pwd-err', T('请填写原密码和新密码')); return; }
        if (newPwd.length < 6) { setErr('uc-pwd-err', T('新密码长度至少 6 位')); return; }
        if (newPwd !== confirmPwd) { setErr('uc-pwd-err', T('两次输入的新密码不一致')); return; }
        PluginCommon.request({
            url: '/api/auth/change-password',
            method: 'POST',
            data: { old_password: oldPwd, new_password: newPwd }
        }).then(function (res) {
            if (res.code === 200) {
                $('uc-old-pwd').value = '';
                $('uc-new-pwd').value = '';
                $('uc-confirm-pwd').value = '';
                showToast(res.message || T('密码修改成功'), 'success');
                // 清强制改密标记（若用户从强制改密弹窗跳转而来）
                try {
                    sessionStorage.removeItem('ftk_must_pwd');
                    sessionStorage.removeItem('ftk_must_pwd_shown');
                } catch (e) { /* ignore */ }
            } else {
                setErr('uc-pwd-err', res.message || T('修改失败'));
            }
        }).catch(function () {});
    }

    function doLogout() {
        PluginCommon.request({ url: '/api/auth/logout', method: 'POST' })
            .catch(function () {})
            .finally(function () { window.location.replace('/login'); });
    }

    // 暴露给模板内联 onclick 调用
    window.submitNickname = submitNickname;
    window.submitPassword = submitPassword;
    window.doLogout = doLogout;

    document.addEventListener('DOMContentLoaded', loadUser);
})();
