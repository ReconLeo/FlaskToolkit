# -*- coding: utf-8 -*-
"""
企业内网工具箱的辅助模块（corp_utils.py）
==========================================
与主插件 `corp_tools.py` 分离的纯函数/轻量工具模块，供 API 与页面视图复用：

1. probe_http：内网服务 HTTP 探测（HEAD→GET 回退，超时/异常归一化）——
   使用 urllib 标准库（不引入 requests 依赖），socket 出站经 audit hook
   按 capabilities network:http 白名单授权（见开发规范 10.7/10.8）。
2. filter_links：按当前用户权限过滤内部工具导航链接。
3. notice 排序工具：公告按发布时间倒序。

注意：本模块不含 BasePlugin 子类，插件静态扫描器会安全跳过（不误判为插件）。
"""
import json
import time
import urllib.error
import urllib.request


def probe_http(url: str, timeout: float = 3.0) -> dict:
    """探测单个 HTTP(S) 服务，返回归一化状态 dict。

    - 优先 HEAD（多数内网服务支持且轻量）；HEAD 失败（405/403/501 等）回退 GET；
    - 读取一小段响应体后关闭连接，避免大页面拖慢探测；
    - 任何异常（连接拒绝/超时/DNS/HTTP 错误码）均归一为 status_code + error。
    """
    result = {
        "url": url,
        "up": False,
        "status_code": None,
        "latency_ms": None,
        "error": None,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    started = time.time()
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "FlaskToolkit-corp_tools/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result["status_code"] = resp.status
                # 读取一小段以触发真实连接（部分服务 HEAD 不响应体，读空即可）
                try:
                    resp.read(64)
                except Exception:
                    pass
        except urllib.error.HTTPError as e:
            # HTTPError 也是"服务在线"（如 401/403/404），code 属正常业务响应
            result["status_code"] = e.code
            try:
                e.read(64)
            except Exception:
                pass
        except urllib.error.URLError as e:
            result["error"] = str(e.reason)
        result["latency_ms"] = int((time.time() - started) * 1000)
        result["up"] = True  # 能拿到 HTTP 响应（含错误码）即视为在线
    except Exception as e:
        # 超时 / 连接拒绝等网络层异常
        result["error"] = type(e).__name__ + ": " + str(e)[:80]
        result["latency_ms"] = int((time.time() - started) * 1000)
    return result


def filter_links(links: list, role: str = "public") -> list:
    """按用户角色过滤导航链接。

    角色层级 public < user < admin；链接声明 permission 为可见最低要求：
    - permission=public → 所有人可见
    - permission=user   → 登录用户（含 admin）可见
    - permission=admin  → 仅 admin 可见
    """
    role_level = {"public": 0, "user": 1, "admin": 2}
    user_level = role_level.get(role, 0)
    out = []
    for link in links or []:
        need = role_level.get(link.get("permission", "public"), 0)
        if user_level >= need:
            out.append(link)
    return out


def sort_notices(notices: list) -> list:
    """公告按 created_at 倒序（新在前），无时间戳的排最前兜底。"""
    return sorted(
        notices or [],
        key=lambda n: (n.get("created_at") or ""),
        reverse=True,
    )


def load_json(path: str, default):
    """安全读取 JSON 文件，损坏/缺失返回 default（不抛异常）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: str, data) -> bool:
    """写 JSON 文件（utf-8, indent=2），成功返回 True。"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
