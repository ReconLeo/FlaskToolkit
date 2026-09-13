/* 大插件示例静态资源：demo 公共脚本（经 /plugin-static/multitool_demo/ 访问） */
window.FtktDemo = {
    sayHello: function () {
        var el = document.getElementById('ftk-js-msg');
        if (el) el.textContent = '静态 JS 调用成功：' + new Date().toLocaleTimeString();
    }
};

// 用 Object.assign 合并保留模板注入的 apiUrl（勿整体覆盖 window.FtktText，否则 text/topwords 页注入的 apiUrl 会丢失 → fetch undefined）
window.FtktText = Object.assign({}, window.FtktText, {
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
    },
    // 词频 Top-N：复用同一 analyze API，把 top_words 渲染为有序列表
    analyzeTop: function () {
        var text = document.getElementById('ftk-topwords-text').value;
        var ol = document.getElementById('ftk-topwords-result');
        ol.innerHTML = '<li class="ftk-muted">请求中…</li>';
        fetch(window.FtktText.apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var top = (data.data && data.data.top_words) || [];
            ol.innerHTML = top.length
                ? top.map(function (it) { return '<li>' + it.word + ' × ' + it.count + '</li>'; }).join('')
                : '<li class="ftk-muted">暂无词频结果</li>';
        })
        .catch(function (e) { ol.innerHTML = '<li class="ftk-muted">请求失败: ' + e.message + '</li>'; });
    }
});
