/* 大插件示例静态资源：demo 公共脚本（经 /plugin-static/multitool_demo/ 访问） */
window.FtktDemo = {
    sayHello: function () {
        var el = document.getElementById('ftk-js-msg');
        if (el) el.textContent = '静态 JS 调用成功：' + new Date().toLocaleTimeString();
    }
};

window.FtktText = {
    analyze: function () {
        var text = document.getElementById('ftk-text').value;
        var el = document.getElementById('ftk-result');
        el.textContent = '请求中…';
        // fetch 已被 plugin_common.js 包装：自动注入 X-CSRF-Token、401 跳登录
        fetch(window.FtktText.apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        })
        .then(function (r) { return r.json(); })
        .then(function (data) { el.textContent = JSON.stringify(data, null, 2); })
        .catch(function (e) { el.textContent = '请求失败: ' + e.message; });
    }
};
