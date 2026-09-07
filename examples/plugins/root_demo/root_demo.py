# -*- coding: utf-8 -*-
"""
示例插件：框架 Root 域演示（root_demo）
========================================
演示 v4.15.0 引入的 Root 权限域（framework 能力域 framework:core，≈ Linux root）。

框架能力展示点：
1. **framework:core capability**：在 plugin.json 声明 "framework:core"，等价获得对框架核心
   （app.py / global_var.py / core/ / routes/ / static/ / 框架模板 / data/user_config.json /
   plugins/status.json 等，见 core/framework_manifest.py 统一清单）的读写权限。
2. **Root 三档**：core 隐含 manage、read；加载时经 capabilities.check_framework('root_demo','core')
   确认授权并打印醒目横幅。
3. **Root 读**：读取框架版本、核心路径清单、框架核心配置 data/user_config.json（framework:core 读语义）。
4. **Root 写**：patch data/user_config.json（Root 写，经 capabilities.check_filesystem 校验 →
   framework:core 放行；审计钩子自动记录 root-access 事件）。
5. **对照拒绝**：普通 filesystem:write 命中核心路径会被拒绝（framework-core-not-declared），
   必须显式声明 framework:core 才能写框架核心。

安全提示：framework:core 是最高风险权限（可读写框架代码与全局状态）。示例仅用于教学，
生产环境中应避免给非信任插件授予 Root。

安装后访问：
- 页面   /plugin/root_demo                     （主入口 index 页）
- API    GET   /api/root_demo/overview         （admin：Root 概览——框架版本/授权级别/核心清单/用户配置）
- API    GET   /api/root_demo/config           （admin：读取框架核心配置 data/user_config.json）
- API    POST  /api/root_demo/config           （admin：写入框架核心配置，Root 写）
- API    GET   /api/root_demo/demo-reject      （admin：对照——普通 filesystem:write 写核心被拒）
"""
import json
import os
from typing import List, Dict

from flask import request

import global_var
from core import capabilities, framework_manifest
from plugins.base_plugin import BasePlugin, permission as permission_required

# 本插件写框架核心的目标文件（相对项目根，framework:core Root 域管辖）
_TARGET_CONFIG = 'data/user_config.json'


def _tr():
    """当前请求语言的翻译器（root_demo 后端消息 i18n，插件语言包合并演示）。"""
    from core import i18n
    return i18n.make_translator(i18n.get_lang())


class RootDemoPlugin(BasePlugin):
    name = "root_demo"
    title = "示例：框架 Root 域"
    description = "框架 Root 域（framework:core）演示：只读框架版本/核心路径清单、读写框架核心配置 data/user_config.json，并对照展示普通 filesystem:write 写核心路径被拒绝、须声明 framework:core（Root 权限）。"
    version = "1.0.0"
    author = "FlaskToolkit Examples"
    category = "示例"
    permission = "admin"               # Root 高风险，路由一律 admin
    require_framework_version = "4.15.0"  # framework:core 为 v4.15.0 能力

    # ---------------- 生命周期 ----------------
    def on_load(self):
        """加载时确认 Root 授权（framework:core），打印醒目横幅。"""
        ok, reason = capabilities.check_framework(self.name, 'core')
        if not ok:
            self.logger.warning(
                "root_demo 未获得 Root 授权（framework:core 未声明或未注册）：%s", reason)
        else:
            # 醒目横幅：与框架加载 framework:core 插件的横幅呼应
            self.logger.info(
                "[Root] root_demo 已获得 framework:core（Root 权限域）授权，可读写框架核心：%s", reason)

    # ---------------- 路由 ----------------
    @property
    def routes(self) -> List[Dict]:
        return [
            {
                "path": "/overview",
                "name": "Root 概览（admin）",
                "methods": ["GET"],
                "params": [],
                "view_func": self.api_overview,
            },
            {
                "path": "/config",
                "name": "读取框架核心配置（admin，Root 读）",
                "methods": ["GET"],
                "params": [],
                "view_func": self.api_get_config,
            },
            {
                "path": "/config",
                "name": "写入框架核心配置（admin，Root 写）",
                "methods": ["POST"],
                "params": [
                    {"name": "data", "type": "object", "required": True,
                     "description": "要合并写入 data/user_config.json 的键值对象（如 {\"PORT\": 5010}）"}
                ],
                "view_func": self.api_set_config,
            },
            {
                "path": "/demo-reject",
                "name": "对照：普通写核心被拒（admin）",
                "methods": ["GET"],
                "params": [],
                "view_func": self.api_demo_reject,
            },
        ]

    # ---------------- Root 读 ----------------
    @permission_required("admin")
    def api_overview(self):
        """Root 概览：框架版本 / 授权级别 / 核心文件清单 / 用户配置（framework:core 读）。"""
        ok, reason = capabilities.check_framework(self.name, 'core')
        core_files = list(framework_manifest.CORE_FILES)
        return self.success_response(data={
            "framework_version": getattr(global_var, 'FRAMEWORK_VERSION', ''),
            "root_level": {"level": "core", "allowed": ok, "reason": reason,
                           "implies": ["read", "manage", "core"]},
            "core_files_count": len(core_files),
            "core_files": core_files,
            "user_config": global_var.get_user_config(),
        }, message=_tr()("Root 概览（framework:core）"))

    @permission_required("admin")
    def api_get_config(self):
        """读取框架核心配置 data/user_config.json（framework:core 读语义）。"""
        ok, reason = capabilities.check_filesystem(self.name, _TARGET_CONFIG, 'r')
        if not ok:
            return self.error_response(_tr()("Root 读被拒：{reason}", reason=reason), code=403)
        cfg = self._read_config()
        return self.success_response(data={
            "file": _TARGET_CONFIG, "allowed": ok, "reason": reason, "config": cfg,
        }, message=_tr()("已读取框架核心配置"))

    # ---------------- Root 写 ----------------
    @permission_required("admin")
    def api_set_config(self):
        """写入框架核心配置 data/user_config.json（Root 写）。

        经 capabilities.check_filesystem 校验 → 命中核心路径写，仅 framework:core 放行；
        审计钩子会自动追加 root-access 审计事件。写入为原子替换，重启后生效。"""
        data = request.validated_data.get("data")
        if not isinstance(data, dict) or not data:
            return self.error_response(_tr()("data 须为非空键值对象"), code=400)
        # 显式走 Root 授权校验（与审计钩子同一判定，双重保险）
        ok, reason = capabilities.check_filesystem(self.name, _TARGET_CONFIG, 'w')
        if not ok:
            return self.error_response(_tr()("Root 写被拒：{reason}", reason=reason), code=403)
        cfg = self._read_config()
        cfg.update(data)
        if not self._write_config(cfg):
            return self.error_response(_tr()("写入框架核心配置失败"), code=500)
        return self.success_response(data={
            "file": _TARGET_CONFIG, "allowed": ok, "reason": reason, "config": cfg,
        }, message=_tr()("已写入框架核心配置（重启后生效）"))

    # ---------------- 对照：普通写核心被拒 ----------------
    @permission_required("admin")
    def api_demo_reject(self):
        """对照演示：仅声明 filesystem:write（无 framework:core）的插件，写核心路径被拒绝。"""
        demo = "demo_no_root"
        capabilities.register_capabilities(demo, ["filesystem:write:data/"])
        try:
            ok, reason = capabilities.check_filesystem(demo, "app.py", 'w')
            result = {
                "plugin": demo,
                "declared": ["filesystem:write:data/"],
                "target": "app.py",
                "allowed": ok,
                "reason": reason,
                "hint": "命中框架核心路径，普通 filesystem 声明不覆盖，须声明 framework:core",
            }
        finally:
            capabilities.unregister_capabilities(demo)
        return self.success_response(data=result, message=_tr()("普通写核心被拒对照"))

    # ---------------- 私有工具 ----------------
    def _read_config(self) -> dict:
        cfg_path = global_var.USER_CONFIG_FILE
        try:
            with open(cfg_path, encoding='utf-8') as f:
                cfg = json.load(f)
            if not isinstance(cfg, dict):
                return {}
            return cfg
        except (OSError, ValueError):
            return {}

    def _write_config(self, cfg: dict) -> bool:
        cfg_path = global_var.USER_CONFIG_FILE
        try:
            os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
            tmp = cfg_path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            os.replace(tmp, cfg_path)
            return True
        except OSError:
            return False
