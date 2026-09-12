/* ============================================================
   FlaskToolkit v4.19.2 — 界面主题（深色 + 可扩展主题）前端脚本
   - 依据 <html data-theme-init>（后端注入的当前主题）设置 <html data-theme>
   - auto（跟随系统）：用 matchMedia(prefers-color-scheme) 解析为 dark/light，
     并监听系统变化实时切换；light/dark 直接生效
   - 自定义主题（v4.19.2）：从 <html data-themes>（available_themes 的 tojson）
     动态读取可选主题表；自定义主题直接设 data-theme=<name>，并按需动态挂载
     <link href="/theme-static/<name>/theme.css">；CSS 加载失败（404，如主题被删）
     回退 auto 作为视觉兜底
   - 手动切换：window.Theme.switch(code) → 立即设置 + 跳转 /theme/<code> 持久化
   依赖：各模板 <head> 引入，且 <html data-theme-init> 与 data-themes 由后端注入
   ============================================================ */
(function (window, document) {
    'use strict';

    var html = document.documentElement;
    var mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
    var current = null; // 已解析的实际 data-theme（dark/light 或自定义主题名）

    // 内建主题（无独立 CSS，走框架 static/css/theme.css）
    var BUILTIN = { auto: true, light: true, dark: true };

    // 从 <html data-themes="..."> 读取可选主题表（内建 + 自定义），键为主题名
    function readKnown() {
        var known = {};
        var s = html.getAttribute('data-themes');
        if (s) {
            try {
                var obj = JSON.parse(s);
                Object.keys(obj).forEach(function (k) { known[k] = true; });
            } catch (e) { /* 解析失败按空表处理 */ }
        }
        // 兜底：即使 data-themes 缺失/损坏，也保留内建三色
        Object.keys(BUILTIN).forEach(function (k) { known[k] = true; });
        return known;
    }
    var KNOWN = readKnown();

    function isCustom(name) {
        return KNOWN[name] && !BUILTIN[name];
    }

    function isDarkSystem() {
        return mq ? mq.matches : false;
    }

    // 把主题声明解析为实际 data-theme 值：
    //   light/dark → 自身；auto → dark/light（跟随系统）；自定义主题 → 主题名；
    //   KNOWN 外（防御，理论后端已兜底）→ 透传声明值
    function resolve(declared) {
        if (declared === 'dark') return 'dark';
        if (declared === 'light') return 'light';
        if (declared === 'auto') return isDarkSystem() ? 'dark' : 'light';
        return declared; // 自定义主题（或防御性透传未知值）
    }

    // 自定义主题 CSS 按需挂载（仅一个 link，切换时替换）
    var cssLink = null;
    function ensureThemeCss(declared) {
        if (cssLink) {
            if (cssLink.parentNode) cssLink.parentNode.removeChild(cssLink);
            cssLink = null;
        }
        if (declared && isCustom(declared)) {
            cssLink = document.createElement('link');
            cssLink.rel = 'stylesheet';
            cssLink.href = '/theme-static/' + encodeURIComponent(declared) + '/theme.css';
            cssLink.onerror = function () { fallbackToAuto(); };
            document.head.appendChild(cssLink);
        }
    }

    // CSS 加载失败兜底：回退 auto（跟随系统），保留内建变量，视觉不崩坏
    function fallbackToAuto() {
        if (cssLink) {
            if (cssLink.parentNode) cssLink.parentNode.removeChild(cssLink);
            cssLink = null;
        }
        apply('auto');
    }

    function apply(declared) {
        var resolved = resolve(declared);
        current = resolved;
        html.setAttribute('data-theme', resolved);
        // 暴露当前声明（供入口高亮）
        html.setAttribute('data-theme-declared', declared || 'auto');
        ensureThemeCss(declared || 'auto');
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
