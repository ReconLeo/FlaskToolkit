const fs = require('fs');
const { JSDOM } = require('jsdom');
function stripJinja(html){ return html.replace(/\{\{[^}]*\}\}/g,'SYSTEM').replace(/\{%[^%]*%\}/g,''); }
function pass(msg,c){ console.log((c?'PASS ':'FAIL ')+msg); if(!c) process.exitCode=1; }

// user-center：uc-top 统一 navbar 样式
{
  const html = stripJinja(fs.readFileSync('templates/user_center.html','utf8'));
  const dom = new JSDOM(html, { runScripts:'outside-only', url:'http://localhost/user-center' });
  const doc = dom.window.document;
  const top = doc.querySelector('.uc-top');
  pass('uc-top 存在', !!top);
  const left = top.children[0], right = top.children[1];
  pass('uc-top 左侧含图标', !!left.querySelector('img.brand-icon'));
  pass('uc-top 左侧含系统名', left.textContent.includes('SYSTEM'));
  pass('uc-top 返回首页是按钮', !!left.querySelector('a.btn.btn-primary'));
  pass('uc-top 右侧退出登录是按钮', !!right.querySelector('a.btn.btn-ghost'));
  pass('uc-top 右侧保留头像', !!right.querySelector('#uc-avatar'));
}

// plugin_default：navbar-brand 加图标
{
  const html = stripJinja(fs.readFileSync('templates/plugin_default.html','utf8'));
  const dom = new JSDOM(html, { runScripts:'outside-only', url:'http://localhost/' });
  const doc = dom.window.document;
  const brand = doc.querySelector('.navbar-brand');
  pass('plugin_default navbar-brand 存在', !!brand);
  pass('plugin_default navbar-brand 含图标', brand && !!brand.querySelector('img.brand-icon'));
  pass('plugin_default navbar-brand 含系统名', brand && brand.textContent.includes('SYSTEM'));
}
console.log('=== navbar 统一验证完成 ===');
