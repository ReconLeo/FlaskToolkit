/* v4.19.2 theme.js 前端行为验证（jsdom）
   覆盖：KNOWN 动态读取 data-themes、自定义主题 data-theme 设置、
         /theme-static CSS 按需挂载、CSS 404 回退 auto。
   运行：node temp/test_theme_js.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const themeJs = fs.readFileSync('static/js/theme.js', 'utf8');
const THEMES_JSON = '{"auto":"auto","light":"light","dark":"dark","sepia":"Sepia"}';

let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log('[PASS]', name); }
  else { fail++; console.log('[FAIL]', name, detail || ''); }
}

function makeDom(themeInit) {
  const html = `<html data-theme-init="${themeInit}" data-themes='${THEMES_JSON}'><head></head><body></body></html>`;
  const dom = new JSDOM(html, { runScripts: 'outside-only', url: 'http://localhost/' });
  dom.window.matchMedia = function (q) {
    return { matches: false, media: q, addEventListener: function () {}, removeEventListener: function () {} };
  };
  dom.window.eval(themeJs);
  dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));
  return dom;
}

// T1 auto + matchMedia dark=false → light；declared=auto
let dom = makeDom('auto');
check('T1 auto → data-theme=light', dom.window.document.documentElement.getAttribute('data-theme') === 'light');
check('T1b declared=auto', dom.window.document.documentElement.getAttribute('data-theme-declared') === 'auto');

// T2 sepia init → data-theme=sepia + 挂载自定义 CSS link
dom = makeDom('sepia');
const de = dom.window.document.documentElement;
check('T2 data-theme=sepia', de.getAttribute('data-theme') === 'sepia');
const links = Array.from(dom.window.document.head.querySelectorAll('link[rel="stylesheet"]'));
check('T2b 挂载 /theme-static/sepia/theme.css', links.some(l => l.getAttribute('href') === '/theme-static/sepia/theme.css'));

// T3 sepia init 但 CSS onerror → 回退 auto（data-theme=light, declared=auto）
dom = makeDom('sepia');
const domDoc = dom.window.document;
const linkEl = Array.from(domDoc.head.querySelectorAll('link[rel="stylesheet"]'))
  .find(l => l.getAttribute('href') === '/theme-static/sepia/theme.css');
linkEl.onerror();
check('T3 CSS 404 → 回退 auto(data-theme=light)', domDoc.documentElement.getAttribute('data-theme') === 'light');
check('T3b declared=auto', domDoc.documentElement.getAttribute('data-theme-declared') === 'auto');
check('T3c 自定义 link 已移除', !domDoc.head.querySelector('link[href="/theme-static/sepia/theme.css"]'));

// T4 KNOWN 动态：data-themes 含 sepia → Theme.apply('sepia') 不被强制回 auto
dom = makeDom('auto');
dom.window.Theme.apply('sepia');
const de4 = dom.window.document.documentElement;
check('T4 Theme.apply(sepia) → data-theme=sepia', de4.getAttribute('data-theme') === 'sepia');

// T5 从 sepia 切回 auto → 移除自定义 link
dom.window.Theme.apply('auto');
const de5 = dom.window.document.documentElement;
check('T5 切回 auto → data-theme=light', de5.getAttribute('data-theme') === 'light');
check('T5b 自定义 link 已移除', !dom.window.document.head.querySelector('link[href="/theme-static/sepia/theme.css"]'));

// T6 内建 light/dark 不挂自定义 CSS
dom = makeDom('light');
check('T6 light 无自定义 link', dom.window.document.head.querySelector('link[href^="/theme-static/"]') === null);

console.log(`\n==== theme.js 前端验证：共 ${pass + fail} 项，通过 ${pass}，失败 ${fail} ====`);
process.exit(fail ? 1 : 0);
