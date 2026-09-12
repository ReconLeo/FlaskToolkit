/* ============================================================
   FlaskToolkit v4.13.0 — Mobile & Tablet JS 增强层
   四件套：①表格自动包裹滚动容器 ②汉堡菜单（首页 navbar）
           ③模态框窄屏全屏化 ④toast 窄屏顶部通栏
   与原有 JS（main.js / plugin_common.js）分离，不修改原逻辑。
   引入：各模板 </body> 前 <script src="/static/js/mobile.js"></script>
   ============================================================ */
(function () {
    'use strict';

    var MOBILE_480 = window.matchMedia('(max-width: 480px)');
    var MOBILE_640 = window.matchMedia('(max-width: 640px)');
    var MOBILE_768 = window.matchMedia('(max-width: 768px)');

    /* ---------- ① 表格自动包裹 .table-scroll ---------- */
    function wrapTables(root) {
        var tables = (root || document).querySelectorAll('table');
        for (var i = 0; i < tables.length; i++) {
            var t = tables[i];
            var parent = t.parentNode;
            if (!parent || parent.nodeType !== 1) continue;
            if (parent.classList && parent.classList.contains('table-scroll')) continue;
            if (parent.tagName === 'TABLE') continue;          // 嵌套表格跳过
            if (parent.closest('.table-scroll')) continue;      // 已在滚动容器内
            var wrap = document.createElement('div');
            wrap.className = 'table-scroll';
            parent.insertBefore(wrap, t);
            wrap.appendChild(t);
        }
    }

    /* ---------- ② 汉堡菜单（首页 navbar：有 .navbar-right 的导航） ---------- */
    function setupBurger() {
        document.querySelectorAll('header.navbar, nav.navbar').forEach(function (nav) {
            if (nav.querySelector('.nav-toggle')) return;
            var right = nav.querySelector('.navbar-right');
            if (!right) return;
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'nav-toggle';
            btn.setAttribute('aria-label', '导航菜单');
            btn.innerHTML = '&#9776;'; /* ☰ */
            btn.addEventListener('click', function () {
                nav.classList.toggle('nav-open');
            });
            /* 插入到导航条尾部（container 内） */
            var container = nav.querySelector('.container') || nav;
            container.appendChild(btn);
            /* 点击容器外关闭 */
            document.addEventListener('click', function (e) {
                if (!nav.contains(e.target) && nav.classList.contains('nav-open')) {
                    nav.classList.remove('nav-open');
                }
            });
        });
    }

    /* ---------- ③ 模态框窄屏全屏化 ---------- */
    function setupModalFull() {
        document.querySelectorAll('.modal-content').forEach(function (m) {
            if (MOBILE_480.matches) {
                m.classList.add('mobile-full');
            } else {
                m.classList.remove('mobile-full');
            }
        });
    }

    /* ---------- ④ toast 窄屏顶部通栏 ---------- */
    function setupToast() {
        document.body.classList.toggle('mobile-narrow', MOBILE_768.matches);
    }

    /* ---------- ⑤ theme/lang 点击 toggle（点按出现，再按收起；点外部关闭） ---------- */
    var _dropdownBound = false;
    function closeDropdowns() {
        document.querySelectorAll('.theme-menu, .lang-menu').forEach(function (m) { m.style.display = ''; });
    }
    function setupDropdown() {
        if (_dropdownBound) return;
        _dropdownBound = true;
        document.addEventListener('click', function (e) {
            var t = e.target;
            var btn = t && t.closest ? t.closest('.theme-btn, .lang-btn') : null;
            var sw = btn ? btn.closest('.theme-switch, .lang-switch') : null;
            if (sw) {
                e.preventDefault();
                var menu = sw.querySelector('.theme-menu, .lang-menu');
                var wasOpen = menu && menu.style.display === 'block';
                if (wasOpen) {
                    /* 二次点击收起：inline none 优先于 hover block，避免移不出菜单 */
                    menu.style.display = 'none';
                    return;
                }
                closeDropdowns();
                if (menu) menu.style.display = 'block';
                return;
            }
            if (t && t.closest && (t.closest('.theme-menu') || t.closest('.lang-menu'))) return;
            closeDropdowns();
        });
    }

    function applyAll() {
        wrapTables(document);
        setupBurger();
        setupModalFull();
        setupToast();
        setupDropdown();
    }

    /* 初始应用 + 媒体查询变化响应 + 动态内容（后台 JS 渲染表格/弹窗）监听 */
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applyAll);
    } else {
        applyAll();
    }
    [MOBILE_480, MOBILE_640, MOBILE_768].forEach(function (mq) {
        if (mq.addEventListener) {
            mq.addEventListener('change', applyAll);
        } else if (mq.addListener) {
            mq.addListener(applyAll); /* 旧内核兼容 */
        }
    });
    /* 后台表格多为 JS 渲染：轻量 MutationObserver 兜底包裹 */
    var mo = new MutationObserver(function () {
        wrapTables(document);
        setupModalFull();
    });
    if (window.MutationObserver && document.body) {
        mo.observe(document.body, { childList: true, subtree: true });
    }
})();
