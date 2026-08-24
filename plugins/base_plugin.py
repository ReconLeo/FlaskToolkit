from abc import ABC, abstractmethod
from functools import wraps
from flask import request, jsonify, render_template, send_file, redirect, Response
import urllib.parse
import os
from io import BytesIO
import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Callable, Any, Optional
import sys
from urllib.parse import quote
import re
import zipfile
import global_var  # 全局常量与共享状态

# ------------------------------
# 统一权限装饰器（新版插件推荐使用）
# ------------------------------
def permission(level: str = "user"):
    """
    新版统一权限装饰器，标记接口的访问层级。
    level 可选值：
      - "public": 游客可访问（无需登录，如登录接口）
      - "user":   仅登录用户可访问（默认）
      - "admin":  仅管理员可访问
    旧版插件可继续使用 require_role，两者标记会被框架统一识别。
    未标记任何权限的接口默认按 "user"（仅登录）处理。
    注意：若插件类内声明了 permission 属性（如 permission = "admin"），
    类体内的 @permission 会被该类属性遮蔽，请改用别名导入：
    from .base_plugin import permission as permission_required
    """
    if level not in ("public", "user", "admin"):
        raise ValueError(f"无效权限层级: {level}，可选 public/user/admin")
    def decorator(func):
        func._permission = level
        return func
    return decorator


class BasePlugin(ABC):
    # 插件基础属性
    @property
    @abstractmethod
    def name(self): 
        """插件唯一标识符（英文，无特殊字符）"""
        pass

    @property
    def title(self): 
        """插件友好显示名称（中文，可选），默认等于name"""
        return self.name

    @property
    @abstractmethod
    def description(self): 
        """插件描述"""
        pass

    @property
    @abstractmethod
    def version(self): 
        """版本号"""
        pass

    @property
    @abstractmethod
    def category(self): 
        """分类"""
        return "common"

    @property
    def author(self): 
        """插件作者（可选）"""
        return "佚名"
    
    @property
    def permission(self):
        """插件所需权限，默认普通用户可访问，可重写为admin"""
        return "user"

    @property
    def dependencies(self): 
        """依赖列表"""
        return []

    @property
    @abstractmethod
    def routes(self): 
        """路由配置"""
        pass

    # 默认属性
    enabled = True  # 默认启用状态
    loaded = True   # 标记插件是否正常加载
    
    # 定时任务配置：格式 [{"func": self.cron_task, "trigger": "cron", "second": "*/30"}]
    @property
    def scheduled_tasks(self) -> List[Dict]: return []
    
    # 允许的上传文件类型和大小限制
    @property
    def allowed_upload_types(self) -> List[str]: return []
    @property
    def max_upload_size(self) -> int: 10 * 1024 * 1024  # 10MB

    def __init__(self):
        self.config = {}
        self.load_config()
        self._temp_files = {}  # 临时文件存储
        self._async_tasks = {}  # 异步任务状态存储
        # 修改默认目录标记：区分主动设置和旧版默认场景
        self._plugin_temp_dir = "__NEW_PLUGIN_DEFAULT__"
        # 自动创建旧版兼容目录（保证旧插件直接可用）
        os.makedirs(os.path.join(os.path.dirname(__file__), 'temp'), exist_ok=True)
        # 内置logger属性，默认使用系统logger，加载时会被替换为专属适配器
        self.logger = logging.getLogger('flask.app')
        
        # 静态资源目录属性（提前初始化，支持插件自定义）
        self.static_dir = None
    
    # ===== 拆分出独立的静态资源注册函数 =====
    # base_plugin.py 修正 register_static_routes 方法
    def register_static_routes(self, app):
        """
        确定插件静态资源目录（支持插件自定义static_dir）。
        默认路径：主脚本目录/templates/plugins/static/<插件名>

        注：静态资源路由不再由每个插件单独注册（@app.route 在应用处理过首个请求后
        无法新增路由，会破坏运行时热加载插件）。改为启动时在 routes/plugin.py 注册
        一次全局通配路由 /plugin-static/<插件名>/<文件>，运行时按插件名分发到
        本目录，热加载新插件无需重新注册任何路由。

        Args:
            app: Flask 应用实例（保留参数以兼容旧签名，已不使用）
        """
        # 如果插件未自定义static_dir，使用默认路径
        if self.static_dir is None:
            global_static_root = os.path.join(
                os.path.dirname(os.path.abspath(sys.argv[0])),  # 主脚本所在目录
                'templates', 'plugins', 'static'
            )
            self.static_dir = os.path.join(global_static_root, self.name)

        if not os.path.exists(self.static_dir) or not os.path.isdir(self.static_dir):
            self.logger.debug(f"未检测到静态资源目录 {self.static_dir}")
            return

        self.logger.info(f"插件 {self.name} 静态资源目录: {self.static_dir}")
    
    def call_plugin_method(self, plugin_name: str, method_name: str,
                       *args, inject_data: dict = None, **kwargs) -> Any:
        """
        调用其他插件的公开方法
        
        :param plugin_name: 目标插件名
        :param method_name: 目标方法名
        :param args: 位置参数（直接透传）
        :param inject_data: 注入到目标插件 request.validated_data 的数据
        :param kwargs: 关键字参数（直接透传）
        :return: 目标方法返回值
        :raises ValueError: 插件不存在/方法不存在
        :raises RuntimeError: 目标方法执行异常
        """
        # 1. 校验插件是否存在
        if plugin_name not in global_var.plugins:
            error_msg = f"跨插件调用失败：插件 {plugin_name} 未加载"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
    
        target_plugin = global_var.plugins[plugin_name]
    
        # 2. 校验方法是否存在且是公开方法
        if not hasattr(target_plugin, method_name) or method_name.startswith('_'):
            error_msg = f"跨插件调用失败：插件 {plugin_name} 不存在公开方法 {method_name}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
    
        target_method = getattr(target_plugin, method_name)
        if not callable(target_method):
            error_msg = f"跨插件调用失败：{plugin_name}.{method_name} 不是可调用方法"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
    
        # 3. 自动参数注入：如果提供了 inject_data，注入到目标插件的 request 上下文
        if inject_data is not None:
            original_data = getattr(target_plugin, '_original_validated_data', None)
            try:
                # 保存原始数据并注入
                target_plugin._original_validated_data = getattr(
                    request, 'validated_data', None
                )
                request.validated_data = inject_data
                # 继续执行
            except AttributeError:
                pass
    
        # 4. 执行调用
        self.logger.debug(
            f"跨插件调用：{self.name} -> {plugin_name}.{method_name}"
            f"(args={args}, kwargs={kwargs}, inject_data={inject_data})"
        )
        try:
            result = target_method(*args, **kwargs)
            self.logger.debug(
                f"跨插件调用成功：{plugin_name}.{method_name} 返回结果={result}"
            )
            return result
        except Exception as e:
            error_msg = (
                f"跨插件调用异常：{plugin_name}.{method_name} "
                f"执行失败: {str(e)}"
            )
            self.logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
        finally:
            # 恢复原始 validated_data
            if inject_data is not None:
                try:
                    request.validated_data = target_plugin._original_validated_data
                    target_plugin._original_validated_data = None
                except AttributeError:
                    pass
    
    # ------------------------------
    # 鉴权装饰器（自动适配可选鉴权）
    # ------------------------------
    # 改为属性装饰器，确保self绑定到当前插件实例
    @staticmethod
    def require_role(allowed_roles: list[str] = None):
        allowed_roles = allowed_roles or ["admin", "user"]
        # 兼容旧版：转换为统一权限标记，供框架层 wrap_view_func 识别
        permission_level = "admin" if list(allowed_roles) == ["admin"] else "user"
        def decorator(func):
            func._permission = permission_level
            @wraps(func)
            def wrapper(*args, **kwargs):
    
                path = request.path
                is_api_request = path.startswith('/api/')
    
                # 1. 鉴权插件不存在直接放行
                if "auth" not in global_var.plugins:
                    return func(*args, **kwargs)
    
                # 2. 统一获取token
                token = request.headers.get("X-Token") or request.cookies.get("token") or request.args.get("token")
                user_info = global_var.plugins["auth"].verify_token(token)
    
                # 3. 未登录处理
                if not user_info:
                    if is_api_request:
                        # API请求返回JSON错误
                        return {"code": 401, "message": "未登录或登录已过期"}, 401
                    else:
                        # 页面请求跳转到登录页，携带来源地址
                        redirect_url = urllib.parse.quote_plus(request.full_path)
                        return redirect(f'/login?redirect={redirect_url}')
    
                # 4. 权限不足处理
                if user_info["role"] not in allowed_roles:
                    if is_api_request:
                        return {"code": 403, "message": f"权限不足，需要角色：{allowed_roles}"}, 403
                    else:
                        # 页面请求返回403页面
                        return render_template('403.html', message=f"需要{','.join(allowed_roles)}权限才可访问"), 403
    
                # 5. 权限校验通过，将用户信息注入request
                request.user = user_info
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), 'configs', f'{self.name}.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except Exception as e:
                self.logger.warning(f"加载插件 {self.name} 配置失败: {str(e)}")

    def save_config(self):
        config_dir = os.path.join(os.path.dirname(__file__), 'configs')
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, f'{self.name}.json')
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self.logger.error(f"保存插件 {self.name} 配置失败: {str(e)}")
            return False

    # 新增：设置插件专属临时目录
    def set_temp_dir(self, temp_dir: str):
        """
        设置插件专属临时目录
        :param temp_dir: 临时目录绝对路径
        """
        self._plugin_temp_dir = temp_dir
        os.makedirs(self._plugin_temp_dir, exist_ok=True)

    # 新增：获取插件专属临时目录
    def get_temp_dir(self) -> str:
        """
        获取插件专属临时目录
        :return: 临时目录绝对路径
        """
        return self._plugin_temp_dir

    # 文件处理工具方法
    def save_uploaded_file(self, file_key: str = 'file') -> tuple[str, str]:
        """保存上传的文件，返回(临时文件路径, 原始文件名)"""
        if file_key not in request.files:
            raise ValueError("缺少上传文件")
        file = request.files[file_key]
        if file.filename == '':
            raise ValueError("未选择文件")
        
        ext = os.path.splitext(file.filename)[1].lower()
        if self.allowed_upload_types and ext not in self.allowed_upload_types:
            raise ValueError(f"不支持的文件类型，允许: {', '.join(self.allowed_upload_types)}")
        
        # 生成临时文件名（使用插件专属临时目录）
        temp_name = f"{uuid.uuid4().hex}{ext}"
        temp_path = os.path.join(self._plugin_temp_dir, temp_name)
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        file.save(temp_path)
        
        # 记录临时文件，自动过期
        self._temp_files[temp_name] = {
            'path': temp_path,
            'create_time': datetime.now(),
            'original_name': file.filename
        }
        return temp_path, file.filename
    
    def send_file_response(self, file_path: str, download_name: str = None,
                        mimetype: str = None, etag: str = None,
                        as_attachment: bool = True, headers: dict = None):
        """扩展的 send_file_response，支持更多参数"""
        from flask import send_file
    
        resp = send_file(
            file_path,
            as_attachment=as_attachment,
            download_name=download_name,
            mimetype=mimetype,
            etag=etag,
            max_age=0,                    # 禁止浏览器缓存
            conditional=True,             # 支持 If-Modified-Since / If-None-Match
        )
    
        if headers:
            for k, v in headers.items():
                resp.headers[k] = v
    
        return resp

    # 异步任务工具方法
    def run_async_task(self, task_func: Callable, *args, **kwargs) -> str:
        """启动异步任务，返回任务ID"""
        task_id = uuid.uuid4().hex
        self._async_tasks[task_id] = {
            'status': 'running',
            'result': None,
            'error': None,
            'start_time': datetime.now()
        }

        def task_wrapper():
            try:
                result = task_func(*args, **kwargs)
                self._async_tasks[task_id]['status'] = 'success'
                self._async_tasks[task_id]['result'] = result
            except Exception as e:
                self._async_tasks[task_id]['status'] = 'failed'
                self._async_tasks[task_id]['error'] = str(e)
                self.logger.error(f"异步任务执行失败: {str(e)}")
            finally:
                # 任务完成1小时后自动清理
                import threading
                def cleanup():
                    import time
                    time.sleep(3600)
                    self._async_tasks.pop(task_id, None)
                threading.Thread(target=cleanup, daemon=True).start()

        import threading
        threading.Thread(target=task_wrapper, daemon=True).start()
        return task_id

    def get_async_task_status(self, task_id: str) -> Dict:
        """查询异步任务状态"""
        return self._async_tasks.get(task_id, {'status': 'not_found'})
    
    # 通用工具方法的辅助方法：JSON 自动检测
    @staticmethod
    def _try_parse_json_value(value):
        """尝试将字符串解析为 JSON 值，失败则返回原字符串"""
        if not isinstance(value, str) or value.strip() == '':
            return value
        trimmed = value.strip()
        if trimmed.startswith('{') or trimmed.startswith('['):
            try:
                return json.loads(trimmed)
            except (json.JSONDecodeError, ValueError):
                pass
        return value
    
    # 通用工具方法
    def validate_params(self, params_config):
        """
        参数校验方法：合并多来源参数，支持类型转换、数组元素类型、默认值
        """
        # 1. 合并所有来源的普通参数（优先级：JSON > Form > URL查询参数）
        data = {}
        # 先加载URL查询参数（最低优先级）★ 增强：自动检测JSON化参数
        for key, value in request.args.to_dict(flat=False).items():
            if len(value) == 1:
                # 单值：尝试 JSON 解析
                data[key] = self._try_parse_json_value(value[0])
            else:
                # 多值：直接作为数组
                data[key] = [self._try_parse_json_value(v) for v in value]
    
        # 再加载Form表单参数（覆盖URL参数）
        if request.form:
            for key, value in request.form.to_dict(flat=False).items():
                if len(value) == 1:
                    data[key] = self._try_parse_json_value(value[0])
                else:
                    data[key] = [self._try_parse_json_value(v) for v in value]
    
        # 最后加载JSON请求体（最高优先级）
        if request.is_json:
            try:
                json_data = request.get_json()
                if isinstance(json_data, dict):
                    data.update(json_data)
            except:
                pass
    
        errors = []
        validated_data = {}
    
        for param in params_config:
            param_name = param['name']
            param_type = param.get('type', 'string')
            required = param.get('required', True)
            # 新增：默认值支持
            default_value = param.get('default', None)
            # 数组元素类型配置，默认字符串
            element_type = param.get('element_type', 'string')
    
            # 优先从files中获取参数（支持文件类型）
            if param_type == 'file':
                if param_name.endswith('[]'):
                    value = request.files.getlist(param_name)
                    if required and len(value) == 0:
                        errors.append(f"缺少必填参数: {param_name}")
                        continue
                    validated_data[param_name] = value
                else:
                    value = request.files.get(param_name)
                    if required and value is None:
                        errors.append(f"缺少必填参数: {param_name}")
                        continue
                    validated_data[param_name] = value
            else:
                # 普通参数从合并后的字典获取
                value = data.get(param_name)
    
                # ★ 新增：如果值为None且配置了默认值，使用默认值
                if value is None and default_value is not None:
                    value = default_value
    
                if required and value is None:
                    # 兼容前端数组参数后缀[]的情况
                    value = data.get(f"{param_name}[]")
                    if value is None:
                        errors.append(f"缺少必填参数: {param_name}")
                        continue
    
                if value is not None:
                    try:
                        if param_type == 'number':
                            validated_data[param_name] = float(value)
                        elif param_type == 'int':
                            validated_data[param_name] = int(value)
                        elif param_type == 'boolean':
                            validated_data[param_name] = str(value).lower() in ['true', '1', 'yes']
                        elif param_type == 'array':
                            # 情况1：JSON提交的原生数组
                            if isinstance(value, list):
                                arr = value
                            # 情况2：Form/URL提交的逗号分隔字符串
                            elif isinstance(value, str):
                                arr = [item.strip() for item in value.split(',') if item.strip()]
                            # 情况3：Form提交的多值参数
                            elif hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                                arr = list(value)
                            else:
                                raise ValueError(f"无法转换为数组类型")
    
                            # 数组元素类型转换
                            converted_arr = []
                            for item in arr:
                                if element_type == 'number':
                                    converted_arr.append(float(item))
                                elif element_type == 'int':
                                    converted_arr.append(int(item))
                                elif element_type == 'boolean':
                                    converted_arr.append(str(item).lower() in ['true', '1', 'yes'])
                                else:
                                    converted_arr.append(str(item))
                            validated_data[param_name] = converted_arr
                        else:
                            validated_data[param_name] = str(value)
                    except ValueError:
                        errors.append(f"参数 {param_name} 类型错误，应为 {param_type}")
    
        return validated_data, errors

    def success_response(self, data=None, message="操作成功"):
        return jsonify({"code": 200, "message": message, "msg": message, "status": "success", "data": data})

    def error_response(self, message="操作失败", code=400):
        # 统一设置 HTTP 状态码（阶段三 Step5：此前 body 带 code 但 HTTP 恒 200）
        # 前端请求封装以 body.code 判断业务结果，HTTP 状态码用于网关/监控/调试语义对齐。
        return jsonify({"code": code, "message": message, "msg": message, "status": "failed", "data": None}), code

    def render_plugin_page(self):
        api_info = []
        for route in self.routes:
            api_info.append({
                'name': route['name'],
                'path': f'/api/{self.name}{route["path"]}',
                'methods': route.get('methods', ['GET']),
                'params': route.get('params', [])
                # params 中的每个字典现在支持以下字段：
                #   name        - 参数名
                #   type        - 类型：string/number/int/boolean/array/object/file
                #   required    - 是否必填（默认 True）
                #   default     - 默认值（新增）
                #   description - 描述
                #   element_type - 数组元素类型（仅 array 类型使用）
            })
        return render_template(
            'plugin_default.html',
            plugin_name=self.name,
            plugin_description=self.description,
            plugin_version=self.version,
            plugin_category=self.category,
            apis=api_info
        )
        
    # 初始化完成钩子（在插件加载完成后执行初始化逻辑）
    def on_load(self):
        """插件加载完成后的回调，此时logger已注入，可以安全使用"""
        pass
        
    # 插件停止前回调钩子
    def on_shutdown(self):
        """
        服务停止前回调，可在此处实现资源清理、数据保存等逻辑
        重载此方法即可自定义停止前操作
        """
        pass

    # 插件卸载前回调钩子（与开发文档声明对齐，框架默认空实现，插件可重载）
    def on_unload(self):
        """
        插件卸载前回调，可在此处实现清理资源、保存状态、取消定时任务等逻辑
        框架默认空实现，重载此方法即可自定义卸载前操作
        """
        pass

    # 插件卸载删除前回调钩子（与开发文档声明对齐，框架默认空实现，插件可重载）
    def on_uninstall(self):
        """
        插件删除前回调，可在此处实现最终清理逻辑
        框架默认空实现，重载此方法即可自定义卸载前操作
        """
        pass