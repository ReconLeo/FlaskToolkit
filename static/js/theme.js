/* ============================================================
   FlaskToolkit v4.19.0 — 界面主题（深色模式）前端脚本
   - 依据 <html data-theme-init>（后端注入的当前主题）设置 <html data-theme>
   - auto（跟随系统）：用 matchMedia(prefers-color-scheme) 解析为 dark/light，
     并监听系统变化实时切换；light/dark 直接生效
   - 手动切换：window.Theme.switch(code) → 立即设置 + 跳转 /theme/<code> 持久化
   - 可扩展：CSS 通过 [data-theme="<name>"] 变量集生效，无需改本脚本
   依赖：各模板 <head> 引入，且 <html data-theme-init="..."> 已由后端注入
   ============================================================ */
(function (window, document) {
    'use strict';

    var html = document.documentElement;
    var mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
    var current = null; // 已解析的实际主题（dark/light）

    // 可选主题集合（需与后端 core.theme.available_themes 保持一致）
    var KNOWN = { auto: true, light: true, dark: true };

    function isDarkSystem() {
        return mq ? mq.matches : false;
    }

    // 把主题声明（auto/light/dark）解析为实际 data-theme 值（dark/light）
    function resolve(declared) {
        if (declared === 'dark') return 'dark';
        if (declared === 'light') return 'light';
        return isDarkSystem() ? 'dark' : 'light'; // auto
    }

    function apply(declared) {
        var resolved = resolve(declared);
        current = resolved;
        html.setAttribute('data-theme', resolved);
        // 暴露当前声明（供入口高亮）
        html.setAttribute('data-theme-declared', declared || 'auto');
        return resolved;
    }

    function init() {
        var declared = html.getAttribute('data-theme-init');
        if (!declared || !KNOWN[declared]) declared = 'auto';
        apply(declared);
        // 跟随系统变化
        if (mq && typeof mq.addEventListener === 'function') {
            mq.addEventListener('change', function () {
                var d = html.getAttribute('data-theme-declared') || 'auto';
                if (d === 'auto') apply('auto');
            });
        }
    }

    // 手动切换：设置 data-theme 后跳转持久化（GET /theme/<code>?next=<path>）
    function switchTheme(code) {
        if (!KNOWN[code]) code = 'auto';
        apply(code);
        var next = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.href = '/theme/' + encodeURIComponent(code) + '?next=' + next;
    }

    window.Theme = {
        current: function () { return current; },
        declared: function () { return html.getAttribute('data-theme-declared') || 'auto'; },
        apply: apply,
        switch: switchTheme,
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(window, document);
