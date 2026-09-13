const fs = require('fs');
const { JSDOM } = require('jsdom');
const html = fs.readFileSync('tests/frontend_jsdom/fixtures/render_setup.html', 'utf8');
const dom = new JSDOM(html, { runScripts: 'dangerously', url: 'http://localhost/setup' });
const { window } = dom;
const { document } = window;
window.matchMedia = window.matchMedia || function () {
    return { matches: false, addEventListener: function(){}, removeEventListener: function(){}, addListener: function(){}, removeListener: function(){} };
};
let ok = true;
function assert(n, c) { console.log((c ? 'PASS' : 'FAIL') + '  ' + n); if (!c) ok = false; }
setTimeout(function () {
    const body = document.body;
    const sel = document.getElementById('lang');
    assert('初始 data-lang-active=en（默认英语）', body.getAttribute('data-lang-active') === 'en');
    assert('下拉初始选中 en', sel.value === 'en');
    sel.value = 'zh-CN';
    sel.dispatchEvent(new window.Event('change'));
    assert('切换 zh-CN → data-lang-active=zh-CN', body.getAttribute('data-lang-active') === 'zh-CN');
    assert('html lang=zh-CN', document.documentElement.getAttribute('lang') === 'zh-CN');
    sel.value = 'en';
    sel.dispatchEvent(new window.Event('change'));
    assert('切回 en → data-lang-active=en', body.getAttribute('data-lang-active') === 'en');
    console.log(ok ? '\n=== setup 交互全部通过 ===' : '\n=== 有失败 ===');
    process.exit(ok ? 0 : 1);
}, 100);
