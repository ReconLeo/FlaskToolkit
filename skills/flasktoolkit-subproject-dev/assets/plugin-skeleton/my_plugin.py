# -*- coding: utf-8 -*-
"""
FlaskToolkit 子项目插件骨架（my_plugin）
========================================
最小可运行后端插件，作为新子项目插件的起始模板：

- 类属性与 plugin.json 两处一致（name/version/title/author/permission/category/description）
- 主入口 /plugin/<name> 渲染 templates/<name>/index.html（render_index 提供上下文）
- 一个 API 路由（三层权限示例：public）
- 生命周期钩子占位

复制到子项目源（如 plugins/<name>/）后，按需改名并扩充。
"""
from typing import List, Dict

# ⚠️ base_plugin.py 位于 [上级包] plugins/，不在本插件子包内。
# 写成 `from .base_plugin import ...` 会被解析成 plugins.<name>.base_plugin（不存在），
# 导致 ModuleNotFoundError → 插件在启动加载时被跳过、后台完全看不到。
# 必须用绝对导入（与官方示例 examples/plugins/multitool_demo 一致）。
try:
    from plugins.base_plugin import BasePlugin
    from plugins.base_plugin import permission as permission_required
except ImportError:  # 兼容「插件目录内自带 base_plugin.py」的另类布局
    from .base_plugin import BasePlugin
    from .base_plugin import permission as permission_required


class MyPlugin(BasePlugin):
    # 元信息：必须与 plugin.json 一致（冲突 → 上传 400）
    name = "my_plugin"
    title = "My Plugin"
    author = "Your Name"
    version = "1.0.0"
    category = "工具"
    description = "FlaskToolkit 子项目插件骨架，按需修改。"
    permission = "user"
    dependencies: List[str] = []

    @property
    def routes(self) -> List[Dict]:
        return [
            {
                "path": "/hello",
                "name": "示例接口（public 权限）",
                "methods": ["GET"],
                "params": [],
                "view_func": self.api_hello,
            },
        ]

    # ---------------- 生命周期钩子 ----------------
    def on_load(self):
        self.load_config()
        self.logger.info(f"{self.name} 已加载，版本 {self.version}")

    # ---------------- 视图函数 ----------------
    @permission_required("public")
    def api_hello(self):
        return self.success_response(data={"message": "Hello FlaskToolkit!"},
                                     message="示例接口调用成功")

    # ---------------- 主入口 ----------------
    def render_index(self):
        """返回主入口模板上下文（templates/plugins/<name>/index.html）"""
        return {"plugin_name": self.name, "version": self.version}
