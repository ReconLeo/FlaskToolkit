const fs = require('fs');
const { JSDOM } = require('jsdom');

function stripJinja(html){
  return html.replace(/\{\{[^}]*\}\}/g,'SYSTEM').replace(/\{%[^%]*%\}/g,'');
}
function pass(msg,c){ console.log((c?'PASS ':'FAIL ')+msg); if(!c) process.exitCode=1; }

// 1. mobile/index.html：navbar-brand 图标 + 汉堡注入
{
  const html = stripJinja(fs.readFileSync('templates/mobile/index.html','utf8'));
  const mobileJs = fs.readFileSync('static/js/mobile.js','utf8');
  const indexJs = fs.readFileSync('static/js/index.js','utf8');
  const dom = new JSDOM(html, { runScripts:'dangerously', pretendToBeVisual:true, url:'http://localhost/' });
  const { document } = dom.window;
  dom.window.matchMedia = function(){ return { matches:true, media:'', addEventListener(){}, removeEventListener(){}, addListener(){}, removeListener(){} }; };
  dom.window.FT = { checkAuth(){return Promise.resolve({loggedIn:false});}, doLogout(){}, getCookie(){}, T(){return 'x';} };
  dom.window.eval(mobileJs);
  const brand = document.querySelector('.navbar-brand');
  pass('mobile/index navbar-brand 存在', !!brand);
  pass('mobile/index navbar-brand 含 icon.png', brand && brand.innerHTML.includes('/static/icon.png'));
  pass('mobile/index 汉堡 nav-toggle 注入', !!document.querySelector('.nav-toggle'));
  dom.window.eval(indexJs);
  pass('mobile/index 工具容器 .m-tools 存在', !!document.querySelector('.m-tools'));
}

// 2. admin base.html：change-pwd-modal 结构 + mobile.js 加 mobile-full
{
  const raw = fs.readFileSync('templates/admin/base.html','utf8');
  const mobileJs = fs.readFileSync('static/js/mobile.js','utf8');
  // 将 mobile.js 注入为内联 script（在 </body> 前），使 jsdom 在 DOMContentLoaded 前执行，正确触发初始化回调
  const html = stripJinja(raw).replace('</body>', '<script>'+mobileJs+'</script></body>');
  const dom = new JSDOM(html, { runScripts:'dangerously', pretendToBeVisual:true, url:'http://localhost/admin/dashboard' });
  const { document } = dom.window;
  dom.window.matchMedia = function(){ return { matches:true, media:'', addEventListener(){}, removeEventListener(){}, addListener(){}, removeListener(){} }; };
  const modal = document.querySelector('#change-pwd-modal');
  pass('change-pwd-modal 存在', !!modal);
  const mc = document.querySelector('#change-pwd-modal .modal-content');
  pass('change-pwd-modal content 存在', !!mc);
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
