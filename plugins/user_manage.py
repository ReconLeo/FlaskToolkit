from plugins.base_plugin import BasePlugin
from flask import request, render_template
from global_var import plugins
from typing import List, Dict

class UserManagePlugin(BasePlugin):
    name = "user_manage"
    title = "用户账号管理"
    description = "用户账号管理插件，支持用户增删改查、密码重置、权限配置"
    version = "1.0.1"
    author = "System"
    category = "系统管理"
    permission = "admin"
    dependencies = ["auth"]  # 依赖auth插件的用户存储和鉴权能力
    require_framework_version = "4.0.0"  # 非强制；声明后低于此框架版本将拒绝安装/加载

    @property
    def routes(self) -> List[Dict]:
        return [
            {
                'path': '/list',
                'name': '获取用户列表',
                'methods': ['GET'],
                'params': [
                    {'name': 'page', 'type': 'number', 'required': False, 'default': 1, 'description': '页码'},
                    {'name': 'page_size', 'type': 'number', 'required': False, 'default': 10, 'description': '每页数量'},
                    {'name': 'keyword', 'type': 'string', 'required': False, 'description': '搜索关键词（用户名/昵称）'}
                ],
                'view_func': self.get_user_list
            },
            {
                'path': '/create',
                'name': '创建用户',
                'methods': ['POST'],
                'params': [
                    {'name': 'username', 'type': 'string', 'required': True, 'description': '用户名'},
                    {'name': 'password', 'type': 'string', 'required': True, 'description': '密码'},
                    {'name': 'nickname', 'type': 'string', 'required': False, 'description': '用户昵称'},
                    {'name': 'role', 'type': 'string', 'required': False, 'default': 'user', 'description': '角色：admin/user'}
                ],
                'view_func': self.create_user
            },
            {
                'path': '/update',
                'name': '更新用户信息',
                'methods': ['POST'],
                'params': [
                    {'name': 'user_id', 'type': 'number', 'required': True, 'description': '用户ID'},
                    {'name': 'nickname', 'type': 'string', 'required': False, 'description': '用户昵称'},
                    {'name': 'role', 'type': 'string', 'required': False, 'description': '角色：admin/user'}
                ],
                'view_func': self.update_user
            },
            {
                'path': '/reset_password',
                'name': '重置用户密码',
                'methods': ['POST'],
                'params': [
                    {'name': 'user_id', 'type': 'number', 'required': True, 'description': '用户ID'},
                    {'name': 'new_password', 'type': 'string', 'required': True, 'description': '新密码'}
                ],
                'view_func': self.reset_password
            },
            {
                'path': '/delete',
                'name': '删除用户',
                'methods': ['POST'],
                'params': [
                    {'name': 'user_id', 'type': 'number', 'required': True, 'description': '用户ID'}
                ],
                'view_func': self.delete_user
            }
        ]

    def on_load(self):
        # 确保auth插件存在
        if "auth" not in plugins:
            self.logger.error("依赖auth插件未加载，用户管理插件启动失败")
            self.enabled = False
            return
        self.auth_plugin = plugins["auth"]
        self.logger.info("用户管理插件加载完成，已关联鉴权插件")

    # 重写页面渲染方法，加载用户管理专属前端页面
    def render_plugin_page(self):
        return render_template(
            'plugins/user_manage.html',
            plugin_name=self.name,
            plugin_version=self.version,
            plugin_description=self.description
        )

    @BasePlugin.require_role(["admin"])  # 仅管理员可访问
    def get_user_list(self):
        """获取用户列表（支持分页和搜索）"""
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 10))
        keyword = request.args.get("keyword", "").strip()

        # 调用auth插件的用户查询接口
        all_users = self.auth_plugin.get_all_users()
        
        # 搜索过滤
        if keyword:
            all_users = [
                user for user in all_users 
                if keyword in user["username"] or keyword in user.get("nickname", "")
            ]
        
        # 分页处理
        total = len(all_users)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_users = all_users[start:end]

        return self.success_response({
            "list": paginated_users,
            "total": total,
            "page": page,
            "page_size": page_size
        })

    @BasePlugin.require_role(["admin"])
    def create_user(self):
        """创建新用户"""
        data = request.validated_data
        username = data["username"]
        
        # 检查用户名是否已存在
        if self.auth_plugin.get_user_by_username(username):
            return self.error_response("用户名已存在", 400)
        
        # 创建用户（调用auth插件能力）
        user = self.auth_plugin.create_user(
            username=username,
            password=data["password"],
            nickname=data.get("nickname", username),
            role=data.get("role", "user")
        )
        return self.success_response(user, "用户创建成功")

    @BasePlugin.require_role(["admin"])
    def update_user(self):
        """更新用户信息"""
        data = request.validated_data
        user_id = data["user_id"]
        
        # 检查用户是否存在
        user = self.auth_plugin.get_user_by_id(user_id)
        if not user:
            return self.error_response("用户不存在", 404)
        
        # 禁止修改默认admin账户的角色
        if user["username"] == "admin" and data.get("role") != "admin":
            return self.error_response("不能修改超级管理员角色", 403)
        
        # 更新用户信息
        updated_user = self.auth_plugin.update_user(
            user_id=user_id,
            nickname=data.get("nickname"),
            role=data.get("role")
        )
        return self.success_response(updated_user, "用户信息更新成功")

    @BasePlugin.require_role(["admin"])
    def reset_password(self):
        """重置用户密码"""
        data = request.validated_data
        user_id = data["user_id"]
        
        user = self.auth_plugin.get_user_by_id(user_id)
        if not user:
            return self.error_response("用户不存在", 404)
        
        self.auth_plugin.reset_password(user_id, data["new_password"])
        return self.success_response(None, "密码重置成功")

    @BasePlugin.require_role(["admin"])
    def delete_user(self):
        """删除用户"""
        data = request.validated_data
        user_id = data["user_id"]
        
        user = self.auth_plugin.get_user_by_id(user_id)
        if not user:
            return self.error_response("用户不存在", 404)
        
        # 禁止删除默认admin账户
        if user["username"] == "admin":
            return self.error_response("不能删除超级管理员账户", 403)
        
        self.auth_plugin.delete_user(user_id)
        return self.success_response(None, "用户删除成功")