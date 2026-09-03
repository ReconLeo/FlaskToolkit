/* corp_tools 企业内网工具箱前端逻辑
 * 经 /plugin-static/corp_tools/js/corp.js 提供。
 * 注意：CSRF 由 plugin_common.js 全局拦截 XHR 自动注入，无需手动带 token。
 */
(function () {
    "use strict";

    // 工具：GET/POST/DELETE 封装（plugin_common.js 已注入 CSRF）
    function api(method, url, body) {
        return new Promise(function (resolve, reject) {
            var xhr = new XMLHttpRequest();
            xhr.open(method, url, true);
            xhr.setRequestHeader("Content-Type", "application/json");
            xhr.onreadystatechange = function () {
                if (xhr.readyState !== 4) return;
                var data = null;
                try { data = JSON.parse(xhr.responseText); } catch (e) { /* ignore */ }
                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve(data || {});
                } else {
                    reject(data || { status: xhr.status });
                }
            };
            xhr.send(body ? JSON.stringify(body) : null);
        });
    }

    // ---------- 健康状态页 ----------
    function loadHealth() {
        var box = document.getElementById("corp-health");
        if (!box) return;
        api("GET", "/api/corp_tools/health").then(function (res) {
            var items = (res.data && res.data.items) || [];
            if (!items.length) {
                box.innerHTML = "<p class='corp-muted'>暂无探测数据（首次探测后 60s 内出现）。</p>";
                return;
            }
            var html = items.map(function (h) {
                var cls = h.up ? "up" : "down";
                var status = h.up
                    ? ("在线 " + (h.status_code || ""))
                    : (h.error || "离线");
                var meta = "探测于 " + h.checked_at + " · " + (h.latency_ms != null ? h.latency_ms + " ms" : "-");
                return "<div class='health-card " + cls + "'>"
                    + "<h4>" + escapeHtml(h.name) + " <span class='tag " + cls + "'>" + status + "</span></h4>"
                    + "<div class='meta'>" + escapeHtml(h.group) + " · " + escapeHtml(meta) + "</div>"
                    + "</div>";
            }).join("");
            box.innerHTML = html;
        }).catch(function () {
            box.innerHTML = "<p class='corp-muted'>健康状态加载失败（未登录或服务异常）。</p>";
        });
    }

    // ---------- 工具导航页 ----------
    function loadLinks() {
        var box = document.getElementById("corp-links");
        if (!box) return;
        api("GET", "/api/corp_tools/links").then(function (res) {
            var items = (res.data && res.data.items) || [];
            if (!items.length) {
                box.innerHTML = "<p class='corp-muted'>当前角色无可见链接。</p>";
                return;
            }
            var groups = {};
            items.forEach(function (l) {
                var g = l.group || "默认";
                (groups[g] = groups[g] || []).push(l);
            });
            var html = Object.keys(groups).map(function (g) {
                return "<div class='corp-links-group'><h4>" + escapeHtml(g) + "</h4>"
                    + groups[g].map(function (l) {
                        return "<a href='" + escapeHtml(l.url) + "' target='_blank' rel='noopener'>" + escapeHtml(l.name) + "</a>";
                    }).join("")
                    + "</div>";
            }).join("");
            box.innerHTML = html;
        }).catch(function () {
            box.innerHTML = "<p class='corp-muted'>导航加载失败。</p>";
        });
    }

    // ---------- 公告板页 ----------
    function loadNotices() {
        var box = document.getElementById("corp-notices");
        if (!box) return;
        api("GET", "/api/corp_tools/notices").then(function (res) {
            var items = (res.data && res.data.items) || [];
            if (!items.length) {
                box.innerHTML = "<p class='corp-muted'>暂无公告。</p>";
                return;
            }
            box.innerHTML = items.map(function (n) {
                return "<div class='corp-notice level-" + escapeHtml(n.level || "info") + "'>"
                    + "<button class='notice-del' data-id='" + escapeHtml(n.id) + "'>删除</button>"
                    + "<span class='notice-title'>" + escapeHtml(n.title) + "</span>"
                    + "<span class='notice-meta'>" + escapeHtml(n.level || "info") + " · " + escapeHtml(n.author || "") + " · " + escapeHtml(n.created_at || "") + "</span>"
                    + "<p class='notice-content'>" + escapeHtml(n.content) + "</p>"
                    + "</div>";
            }).join("");
            // 删除按钮事件（admin 才可见；无权限时后端返回 403，前端提示）
            box.querySelectorAll(".notice-del").forEach(function (btn) {
                btn.addEventListener("click", function () {
                    if (!confirm("确定删除该公告？")) return;
                    api("DELETE", "/api/corp_tools/notices/" + encodeURIComponent(btn.dataset.id)).then(function () {
                        loadNotices();
                    }).catch(function (e) {
                        alert((e && e.message) || "删除失败（无权限或公告不存在）");
                    });
                });
            });
        }).catch(function () {
            box.innerHTML = "<p class='corp-muted'>公告加载失败（需登录）。</p>";
        });
    }

    function bindNoticeForm() {
        var form = document.getElementById("corp-notice-form");
        if (!form) return;
        form.addEventListener("submit", function (ev) {
            ev.preventDefault();
            var fd = new FormData(form);
            api("POST", "/api/corp_tools/notices", {
                title: fd.get("title"),
                content: fd.get("content"),
                level: fd.get("level") || "info",
            }).then(function () {
                form.reset();
                loadNotices();
            }).catch(function (e) {
                alert((e && e.message) || "发布失败（需要管理员权限）");
            });
        });
    }

    function escapeHtml(s) {
        return String(s == null ? "" : s)
            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    // 按当前页面初始化
    document.addEventListener("DOMContentLoaded", function () {
        if (document.getElementById("corp-health")) {
            loadHealth();
            setInterval(loadHealth, 15000); // 15s 轮询，覆盖 60s 探测周期
        }
        if (document.getElementById("corp-links")) loadLinks();
        if (document.getElementById("corp-notices")) {
            loadNotices();
            bindNoticeForm();
        }
    });
})();
