const fs = require('fs');
const { JSDOM } = require('jsdom');
function stripJinja(html){ return html.replace(/\{\{[^}]*\}\}/g,'SYSTEM').replace(/\{%[^%]*%\}/g,''); }
function pass(msg,c){ console.log((c?'PASS ':'FAIL ')+msg); if(!c) process.exitCode=1; }

// 1. 桌面 index.html：主标题跟随 system_name
{
  const html = fs.readFileSync('templates/index.html','utf8');
  pass('桌面主标题用 system_name', html.includes('{{ system_name }}</h1>') && !html.includes("t('FlaskToolkit 全栈工具集')"));
  pass('桌面 navbar-brand 含 system_name', html.includes('{{ system_name }} {{ system_version }}'));
}

// 2. mobile/index.html：m-container 上方 system_name 标题 + 结构
{
  const html = fs.readFileSync('templates/mobile/index.html','utf8');
  pass('mobile 有 m-page-title 主标题', html.includes('class="m-page-title"'));
  pass('mobile m-page-title 主标题含 system_name', html.includes('class="m-page-title">{{ system_name }}'));
  pass('mobile m-toolbar-row 含 toolSort+toolCount', html.includes('id="toolSort"') && html.includes('id="toolCount"'));
  pass('mobile adminBar 存在', html.includes('id="adminBar"'));
}

// 3. CSS 规则存在性
{
  const mc = fs.readFileSync('static/css/mobile.css','utf8');
  const ma = fs.readFileSync('static/css/mobile-app.css','utf8');
  pass('mobile.css navbar flex 垂直居中', mc.includes('header.navbar { display: flex; align-items: center; }'));
  pass('mobile.css adminBar 按钮全宽', mc.includes('#adminBar .btn { width: 100%'));
  pass('mobile-app.css m-page-title 居中', ma.includes('body.mobile .m-page-title'));
  pass('mobile-app.css m-toolbar-row column', ma.includes('flex-direction: column'));
  pass('mobile-app.css m-count 靠左', ma.includes('align-self: flex-start'));
}

// 4. jsdom 渲染 mobile/index：m-toolbar-row 结构与 adminBar 按钮 class
{
  const html = stripJinja(fs.readFileSync('templates/mobile/index.html','utf8'));
  const dom = new JSDOM(html, { runScripts:'outside-only', url:'http://localhost/' });
  const { document } = dom.window;
  const row = document.querySelector('.m-toolbar-row');
  pass('m-toolbar-row 存在', !!row);
  pass('m-toolbar-row 含 select(toolSort)', !!row.querySelector('#toolSort'));
  pass('m-toolbar-row 含 span(toolCount)', !!row.querySelector('#toolCount'));
  pass('m-page-title 存在', !!document.querySelector('.m-page-title'));
  pass('adminBar 内是 btn', !!document.querySelector('#adminBar .btn'));
}
console.log('=== 布局调整验证完成 ===');
