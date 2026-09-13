# 前端 JS 行为验证（jsdom）

本目录存放用 [jsdom](https://github.com/jsdom/jsdom) 在 Node 中驱动的**前端 JavaScript 行为验证**脚本（原存于 temp/ 的一次性验证，固化到此）。

覆盖：`theme.js` / `user_center.js` / `mobile.js` + `index.js` 注入、桌面与移动端 index 布局、登录页、用户中心导航、图标渲染等前端行为。

## 运行前提

- 已安装 Node.js + `jsdom`（`npm install jsdom`）。
- **从项目根目录运行**（脚本内资源引用基于 cwd=项目根）。

## 运行

```bash
node tests/frontend_jsdom/test_theme_js.js
node tests/frontend_jsdom/test_user_center_js.js
node tests/frontend_jsdom/test_layout_verify.js
node tests/frontend_jsdom/test_navbar_verify.js
node tests/frontend_jsdom/test_icon_verify.js
node tests/frontend_jsdom/test_mobile_index.js
node tests/frontend_jsdom/test_setup.js
```

失败时脚本置 `process.exitCode=1`，可被 CI / 全量回归脚本捕获。

## 说明

- `fixtures/`：`render_mobile_index.html`、`render_setup.html` 为渲染后的完整页面快照（含数据），供 `test_mobile_index` / `test_setup` 直接驱动；若页面结构大改需重新生成快照。
- 脚本内部对模板做了 Jinja 占位符剥离（`stripJinja`）或直接引用 `static/js/` 真实源码，验证的是**当前源码行为**。
