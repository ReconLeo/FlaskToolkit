const fs = require('fs');
const { JSDOM } = require('jsdom');

function stripJinja(html){
  return html.replace(/\{\{[^}]*\}\}/g,'SYSTEM').replace(/\{%[^%]*%\}/g,'');
}
function pass(msg,c){ console.log((c?'PASS ':'FAIL ')+msg); if(!c) process.exitCode=1; }

const mobileJs = fs.readFileSync('static/js/mobile.js','utf8');

/* 受控 DOM：构造精简 HTML（不喂真实模板，避免内联脚本 / Jinja 条件渲染干扰），
   在脚本执行前 mock matchMedia（matches:true），eval mobile.js 后手动派发
   DOMContentLoaded 触发其 applyAll（jsdom 中 readyState 为 loading 且不自动派发）。 */
function newDom(bodyHtml){
  const html = '<!doctype html><html><head><meta charset="utf-8"></head><body>' + bodyHtml + '</body></html>';
  const dom = new JSDOM(html, { runScripts:'outside-only', url:'http://localhost/' });
  dom.window.matchMedia = function(){ return { matches:true, media:'', addEventListener(){}, removeEventListener(){}, addListener(){}, removeListener(){} }; };
  return dom;
}
function runMobile(dom){
  dom.window.eval(mobileJs);
  dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));
}

// 1. mobile/index.html：navbar-brand 图标 + 汉堡注入
{
  const html = stripJinja(fs.readFileSync('templates/mobile/index.html','utf8'));
  pass('mobile/index navbar-brand 含 icon.png', html.includes('class="navbar-brand"') && html.includes('/static/icon.png'));
  pass('mobile/index 工具容器 .m-tools 存在', html.includes('class="m-tools') || html.includes('"m-tools"'));
  // 汉堡注入行为：mobile.js 对含 .navbar-right 的 header.navbar 注入 .nav-toggle
  const dom = newDom('<header class="navbar"><div class="container"><div class="navbar-right">r</div></div></header>');
  runMobile(dom);
  pass('mobile.js 注入 .nav-toggle 汉堡', !!dom.window.document.querySelector('.nav-toggle'));
}

// 2. admin base.html：change-pwd-modal 结构 + mobile.js 加 mobile-full
{
  const raw = fs.readFileSync('templates/admin/base.html','utf8');
  const s = stripJinja(raw);
  pass('change-pwd-modal 结构存在', s.includes('id="change-pwd-modal"') && s.includes('modal-content'));
  // mobile-full 行为：matchMedia matches:true 时给 .modal-content 加 mobile-full
  const dom = newDom('<div id="change-pwd-modal" class="modal"><div class="modal-content" style="max-width:420px;">m</div></div>');
  runMobile(dom);
  const mc = dom.window.document.querySelector('.modal-content');
  pass('mobile.js 加 mobile-full 类', mc && mc.classList.contains('mobile-full'));
  const css = fs.readFileSync('static/css/admin-mobile.css','utf8');
  pass('admin-mobile.css 有 min-height:auto 覆盖', css.includes('min-height: auto'));
  pass('admin-mobile.css 有 max-height:88vh', css.includes('max-height: 88vh'));
  pass('admin-mobile.css 有 overflow-y:auto', css.includes('overflow-y: auto'));
}

// 3. system.html 关于卡片大图标
{
  const html = fs.readFileSync('templates/admin/system.html','utf8');
  pass('system.html 关于卡片含 about-brand-icon + icon.png',
      html.includes('about-brand-icon') && html.includes('/static/icon.png'));
  pass('system.html system_name 字号 22px', html.includes('font-size:22px'));
}
console.log('=== 图标 & modal 适配验证完成 ===');
