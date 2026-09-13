/* v4.20 user_center.js 前端行为验证（jsdom）
   覆盖：加载用户、改昵称拦截/请求体、改密码校验/请求体。
   运行：node temp/test_user_center_js.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const js = fs.readFileSync('static/js/user_center.js', 'utf8');
let calls = [];
let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log('[PASS]', name); }
  else { fail++; console.log('[FAIL]', name, detail || ''); }
}

function makeDom() {
  calls = [];
  const dom = new JSDOM(`<html><body>
    <input type="text" id="uc-nickname"><div id="uc-nickname-err"></div>
    <input type="password" id="uc-old-pwd">
    <input type="password" id="uc-new-pwd">
    <input type="password" id="uc-confirm-pwd">
    <div id="uc-pwd-err"></div><div id="uc-username"></div>
    <div id="uc-name"></div><div id="uc-avatar"></div><div id="toast"></div>
  </body></html>`, { runScripts: 'outside-only', url: 'http://localhost/' });
  dom.window.T = (k) => k;
  dom.window.PluginCommon = {
    request: (opt) => {
      calls.push(opt);
      return new dom.window.Promise((res) => res({ code: 200, data: { username: 'admin', nickname: '管理员', role: 'admin' }, message: 'ok' }));
    }
  };
  dom.window.eval(js);
  dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));
  return dom;
}

const tick = () => new Promise((r) => setTimeout(r, 0));
async function main() {
// T1 加载时请求 user/info 填充
let dom = makeDom();
await tick(); // 等 loadUser 的 Promise .then 微任务执行
check('T1 加载调用 user/info', calls.length >= 1 && calls[0].url === '/api/auth/user/info',
  calls[0] && calls[0].url);
check('T1b 填充 username 只读', dom.window.document.getElementById('uc-username').value === 'admin',
  'value=' + dom.window.document.getElementById('uc-username').value);

// T2 空昵称 → 拦截（不发请求）
let callCount = calls.length;
dom.window.document.getElementById('uc-nickname').value = '   ';
dom.window.submitNickname();
check('T2 空昵称拦截不发请求', calls.length === callCount, '');
check('T2b 提示昵称不能为空', dom.window.document.getElementById('uc-nickname-err').textContent.indexOf('昵称不能为空') >= 0,
  dom.window.document.getElementById('uc-nickname-err').textContent);

// T3 超长昵称 → 拦截
callCount = calls.length;
dom.window.document.getElementById('uc-nickname').value = 'x'.repeat(21);
dom.window.submitNickname();
check('T3 超长昵称拦截', calls.length === callCount, '');

// T4 有效改昵称 → 请求体正确
callCount = calls.length;
dom.window.document.getElementById('uc-nickname').value = '小王';
dom.window.submitNickname();
const nreq = calls[calls.length - 1];
check('T4 改昵称请求 URL 正确', nreq.url === '/api/auth/user/update-nickname' && nreq.method === 'POST', nreq.url);
check('T4b 改昵称请求体 nickname', nreq.data && nreq.data.nickname === '小王', JSON.stringify(nreq.data));

// T5 改密：短密码 → 拦截
dom = makeDom();
const elOld = dom.window.document.getElementById('uc-old-pwd');
const elNew = dom.window.document.getElementById('uc-new-pwd');
const elConf = dom.window.document.getElementById('uc-confirm-pwd');
elOld.value = 'admin123'; elNew.value = '123'; elConf.value = '123';
callCount = calls.length;
dom.window.submitPassword();
check('T5 短密码拦截', calls.length === callCount, '');
check('T5b 提示至少6位', dom.window.document.getElementById('uc-pwd-err').textContent.indexOf('至少 6 位') >= 0, '');

// T6 改密：两次不一致 → 拦截
elOld.value = 'admin123'; elNew.value = 'newpass1'; elConf.value = 'newpass2';
callCount = calls.length;
dom.window.submitPassword();
check('T6 两次不一致拦截', calls.length === callCount, '');

// T7 有效改密 → 请求体正确
elOld.value = 'admin123'; elNew.value = 'newpass1'; elConf.value = 'newpass1';
dom.window.submitPassword();
const preq = calls[calls.length - 1];
check('T7 改密请求 URL 正确', preq.url === '/api/auth/change-password' && preq.method === 'POST', preq.url);
check('T7b 改密请求体', preq.data && preq.data.old_password === 'admin123' && preq.data.new_password === 'newpass1',
  JSON.stringify(preq.data));

  console.log(`\n==== user_center.js 前端验证：共 ${pass + fail} 项，通过 ${pass}，失败 ${fail} ====`);
  process.exit(fail ? 1 : 0);
}
main();
