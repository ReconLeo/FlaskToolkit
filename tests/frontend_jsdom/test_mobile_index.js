const fs = require('fs');
const { JSDOM } = require('jsdom');
const html = fs.readFileSync('tests/frontend_jsdom/fixtures/render_mobile_index.html', 'utf8');
const mobileJs = fs.readFileSync('static/js/mobile.js', 'utf8');
const indexJs = fs.readFileSync('static/js/index.js', 'utf8');

const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost/' });
const { window } = dom;
const { document } = window;

// polyfill matchMedia（模拟移动端窄屏）
window.matchMedia = window.matchMedia || function (q) {
    return { matches: true, media: q, addEventListener: function(){}, removeEventListener: function(){}, addListener: function(){}, removeListener: function(){} };
};
// mock FT（main.js 提供）
window.FT = {
    checkAuth: function () { return Promise.resolve({ loggedIn: false, user: null }); },
    doLogout: function(){}, getCookie: function(){}
};

let ok = true;
function assert(name, cond) {
    console.log((cond ? 'PASS' : 'FAIL') + '  ' + name);
    if (!cond) ok = false;
}

// 执行 mobile.js 与 index.js
window.eval(mobileJs);
window.eval(indexJs);

setTimeout(function () {
    const nav = document.querySelector('header.navbar');
    const toggle = document.querySelector('header.navbar .nav-toggle');
    assert('navbar 存在', !!nav);
    assert('mobile.js 注入 nav-toggle（汉堡）', !!toggle);
    if (toggle) {
        toggle.click();
        assert('点击汉堡 → navbar.nav-open', nav.classList.contains('nav-open'));
        toggle.click();
        assert('再次点击 → nav-open 收起', !nav.classList.contains('nav-open'));
    }
    const search = document.getElementById('toolSearch');
    const cards = document.querySelectorAll('.m-tool-card');
    assert('工具卡片 2 个', cards.length === 2);
    if (search) {
        search.value = 'alpha';
        search.dispatchEvent(new window.Event('input'));
        setTimeout(function () {
            const visible = Array.prototype.slice.call(document.querySelectorAll('.m-tool-card')).filter(function (c) { return c.style.display !== 'none'; });
            assert('搜索 alpha 后 1 个可见（Alpha）', visible.length === 1 && visible[0].dataset.title === 'Alpha');
            console.log(ok ? '\n=== 全部通过 ===' : '\n=== 存在失败 ===');
            process.exit(ok ? 0 : 1);
        }, 50);
    } else {
        assert('搜索框存在', false);
        process.exit(1);
    }
}, 100);
