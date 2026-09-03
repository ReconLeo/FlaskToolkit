from .base_plugin import BasePlugin, permission as permission_required  # 类内 permission 属性会遮蔽同名装饰器，故用别名
import os
import json
import time
import uuid
import hashlib
import hmac
import secrets
from flask import request
from typing import List, Dict, Optional
import global_var

class AuthPlugin(BasePlugin):
    name = "auth"
    title = "系统鉴权"
    description = "可选系统鉴权插件"
    version = "1.1.0"
    author = "System"
    category = "系统管理"
    permission = "admin"
    dependencies = []

    # 配置默认值
    default_config = {
        "SESSION_EXPIRE": 7 * 24 * 60 * 60,  # 默认7天有效期
        "users": []
    }
    
    def __init__(self):
        super().__init__()
        # 仅做基础初始化，不读取config，避免扫描阶段报错
        self.sessions = {}  # 运行时会话缓存 {token: {user_info}}
        self.SESSION_EXPIRE = None
        # 登录失败计数（防暴力破解）：{key: {'count': int, 'first_ts': float, 'locked_until': float}}
        # key 维度由 global_var.LOGIN_LOCK_MODE 决定：username / ip_username
        self._login_attempts = {}

    def on_load(self):
        """插件加载完成后的回调，此时config已完成初始化"""
        # 初始化配置
        if not self.config:
            self.config = self.default_config.copy()
            self.save_config()
        else:
            # 补全缺失的配置项（兼容旧版本配置）
            for key, default_value in self.default_config.items():
                if key not in self.config:
                    self.config[key] = default_value
            self.save_config()
        
        # 加载配置到实例变量
        self.SESSION_EXPIRE = self.config["SESSION_EXPIRE"]
        
        # 加载持久化会话
        self._load_sessions()
        
        # 初始化默认管理员账户
        if not self.config["users"]:
            self.config["users"] = [
                {
                    "id": 1,
                    "username": "admin",
                    "password": self._hash_password("admin123"),
                    "role": "admin",
                    "nickname": "超级管理员",
                    "create_time": int(time.time())
                }
            ]
        
        # 兼容旧版用户数据：自动补全缺失字段
        max_id = 0
        for user in self.config["users"]:
            if "id" not in user:
                max_id += 1
                user["id"] = max_id
            else:
                max_id = max(max_id, user["id"])
            if "nickname" not in user:
                user["nickname"] = user["username"]
            if "create_time" not in user:
                user["create_time"] = int(time.time())
        
        self.save_config()
        self.logger.info("鉴权插件加载完成，默认账户：admin/admin123")


    # ------------------------------
    # 会话持久化核心方法
    # ------------------------------
    def _get_session_file_path(self) -> str:
        """获取会话持久化文件路径（v4.5.0 起位于插件自属数据目录，纳入 capabilities 隐式豁免）"""
        return self.get_data_path("sessions.json")

    def _load_sessions(self):
        """加载持久化的会话数据，自动清理过期会话"""
        # v4.5.0 兼容：旧版会话文件 plugins/data/sessions.json 迁移至自属目录
        session_file = self._get_session_file_path()
        legacy_file = os.path.join(os.path.dirname(__file__), 'data', 'sessions.json')
        if not os.path.exists(session_file) and os.path.exists(legacy_file):
            try:
                os.replace(legacy_file, session_file)
                self.logger.info("已迁移旧版会话文件至插件自属数据目录")
            except Exception as e:
                self.logger.warning(f"旧版会话文件迁移失败: {e}")
        if not os.path.exists(session_file):
            self.sessions = {}
            return
        
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                loaded_sessions = json.load(f)
            
            current_time = time.time()
            # 过滤掉过期会话
            self.sessions = {
                token: session
                for token, session in loaded_sessions.items()
                if session["expire_at"] > current_time
            }
            
            # 清理后重新保存
            self._save_sessions()
            self.logger.info(f"已加载 {len(self.sessions)} 个有效会话")
        except Exception as e:
            self.logger.error(f"会话文件加载失败: {str(e)}")
            self.sessions = {}

    def _save_sessions(self):
        """持久化当前会话数据（原子写：临时文件 + os.replace，避免并发读端读到空/截断文件）"""
        session_file = self._get_session_file_path()
        tmp_file = f"{session_file}.tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self.sessions, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, session_file)
        except Exception as e:
            self.logger.error(f"会话持久化失败: {str(e)}")


    # ------------------------------
    # 公开方法：对user_manage插件暴露的能力
    # ------------------------------
    def verify_token(self, token: str) -> dict | None:
        """校验token有效性，返回用户信息/None
        规则：绝对过期（expire_at）与空闲超时（last_active_at + SESSION_IDLE_TIMEOUT）
        任一命中即失效；有效请求会刷新 last_active_at（v4.3.0）。"""
        if not token:
            return None
        session = self.sessions.get(token)
        if not session:
            return None
        now = time.time()
        idle_timeout = getattr(global_var, 'SESSION_IDLE_TIMEOUT', 1800)
        if session["expire_at"] < now or now - session.get("last_active_at", now) > idle_timeout:
            self.sessions.pop(token, None)
            self._save_sessions()
            return None
        # 刷新活动时间（仅内存，不落盘，避免高频写盘）
        session["last_active_at"] = now
        return session

    def login(self, username: str, password: str) -> tuple[bool, str, dict]:
        """登录校验，返回(是否成功, token, 用户信息)"""
        for user in self.config["users"]:
            if user["username"] == username:
                if self._verify_password(password, user["password"]):
                    # 惰性迁移：旧版 XOR 密码在登录成功后自动升级为 PBKDF2 哈希
                    if not user["password"].startswith("pbkdf2_sha256$"):
                        user["password"] = self._hash_password(password)
                        self.save_config()
                    token = uuid.uuid4().hex
                    now = time.time()
                    user_info = {
                        "id": user.get("id", 0),
                        "username": username,
                        "nickname": user.get("nickname", username),
                        "role": user.get("role", "user"),
                        "create_time": user.get("create_time", int(time.time())),
                        "expire_at": now + self.SESSION_EXPIRE,
                        "last_active_at": now  # 会话空闲超时基准（v4.3.0）
                    }
                    self.sessions[token] = user_info
                    self._save_sessions()
                    return True, token, user_info
        return False, "", {}

    def get_all_users(self) -> List[Dict]:
        """获取所有用户列表（user_manage调用）"""
        return [
            {k:v for k,v in user.items() if k != "password"} 
            for user in self.config["users"]
        ]

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """根据用户ID查询用户（user_manage调用）"""
        for user in self.config["users"]:
            if user["id"] == user_id:
                return {k:v for k,v in user.items() if k != "password"}
        return None

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """根据用户名查询用户（user_manage调用）"""
        for user in self.config["users"]:
            if user["username"] == username:
                return {k:v for k,v in user.items() if k != "password"}
        return None

    def create_user(self, username: str, password: str, nickname: str = None, role: str = "user") -> Dict:
        """创建新用户（user_manage调用）"""
        max_id = max([user["id"] for user in self.config["users"]], default=0) + 1
        new_user = {
            "id": max_id,
            "username": username,
            "password": self._hash_password(password),
            "nickname": nickname if nickname else username,
            "role": role,
            "create_time": int(time.time())
        }
        self.config["users"].append(new_user)
        self.save_config()
        return {k:v for k,v in new_user.items() if k != "password"}

    def update_user(self, user_id: int, nickname: str = None, role: str = None) -> Optional[Dict]:
        """更新用户信息（user_manage调用）"""
        for user in self.config["users"]:
            if user["id"] == user_id:
                if nickname:
                    user["nickname"] = nickname
                if role:
                    user["role"] = role
                self.save_config()
                return {k:v for k,v in user.items() if k != "password"}
        return None

    def reset_password(self, user_id: int, new_password: str) -> bool:
        """重置用户密码（user_manage调用）"""
        for user in self.config["users"]:
            if user["id"] == user_id:
                user["password"] = self._hash_password(new_password)
                self.save_config()
                # 踢掉该用户的所有登录会话
                expired_tokens = [
                    token for token, session in self.sessions.items()
                    if session["id"] == user_id
                ]
                for token in expired_tokens:
                    self.sessions.pop(token, None)
                self._save_sessions()
                return True
        return False

    def delete_user(self, user_id: int) -> bool:
        """删除用户（user_manage调用）"""
        for index, user in enumerate(self.config["users"]):
            if user["id"] == user_id:
                del self.config["users"][index]
                self.save_config()
                # 踢掉该用户的所有登录会话
                expired_tokens = [
                    token for token, session in self.sessions.items()
                    if session["id"] == user_id
                ]
                for token in expired_tokens:
                    self.sessions.pop(token, None)
                self._save_sessions()
                return True
        return False

    def add_user(self, username: str, password: str, role: str = "user") -> bool:
        """旧版新增用户方法（兼容原有逻辑）"""
        if self.get_user_by_username(username):
            return False
        self.create_user(username, password, role=role)
        return True

    def encrypt_password(self, password: str) -> str:
        """公开的密码加密方法（PBKDF2 哈希）"""
        return self._hash_password(password)


    # ------------------------------
    # 私有方法：内部工具
    # ------------------------------
    # ------------------------------
    # 登录失败锁定（v4.3.0 安全强化）
    # ------------------------------
    def _login_lock_key(self, username: str) -> Optional[str]:
        """计算锁定维度 key；LOGIN_LOCK_MODE=off 时返回 None（禁用锁定）"""
        mode = getattr(global_var, 'LOGIN_LOCK_MODE', 'ip_username')
        if mode == 'off':
            return None
        if mode == 'username':
            return f"u:{username}"
        # ip_username（默认）：IP+用户名双维度，防分布式爆破
        client_ip = request.remote_addr or 'unknown'
        return f"ip:{client_ip}:u:{username}"

    def _check_login_locked(self, username: str) -> tuple:
        """检查是否处于锁定期，返回 (是否锁定, 剩余秒数)"""
        key = self._login_lock_key(username)
        if key is None:
            return False, 0
        record = self._login_attempts.get(key)
        if not record:
            return False, 0
        now = time.time()
        locked_until = record.get("locked_until", 0)
        if locked_until and locked_until > now:
            return True, int(locked_until - now)
        # 锁定已过期：清理记录，下次失败重新计数；locked_until=0 表示从未锁定，保留记录继续累计
        if locked_until:
            self._login_attempts.pop(key, None)
        return False, 0

    def _record_login_failure(self, username: str) -> None:
        """记录一次登录失败；连续失败达阈值触发锁定"""
        key = self._login_lock_key(username)
        if key is None:
            return
        now = time.time()
        max_attempts = getattr(global_var, 'LOGIN_MAX_ATTEMPTS', 5)
        lock_seconds = getattr(global_var, 'LOGIN_LOCK_SECONDS', 900)
        record = self._login_attempts.get(key)
        if not record:
            record = {"count": 0, "first_ts": now, "locked_until": 0}
            self._login_attempts[key] = record
        record["count"] += 1
        if record["count"] >= max_attempts:
            record["locked_until"] = now + lock_seconds
            record["count"] = 0  # 触发锁定后重置计数，锁定到期后重新累计
            self.logger.warning(f"登录失败次数过多，已锁定（{lock_seconds}s）: {key}")

    def _clear_login_attempts(self, username: str) -> None:
        """登录成功后清除该维度的失败计数"""
        key = self._login_lock_key(username)
        if key is not None:
            self._login_attempts.pop(key, None)

    def _hash_password(self, password: str) -> str:
        """PBKDF2-SHA256 密码哈希，返回格式: pbkdf2_sha256$iterations$salt_hex$hash_hex"""
        salt = os.urandom(16)
        iterations = 100_000
        digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
        return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"

    def _verify_password(self, password: str, stored: str) -> bool:
        """校验密码：支持 PBKDF2 新格式；旧 XOR 格式仅作兼容（密钥已移除时不可用）"""
        if stored.startswith("pbkdf2_sha256$"):
            try:
                _, iterations_s, salt_hex, hash_hex = stored.split("$")
                digest = hashlib.pbkdf2_hmac(
                    'sha256', password.encode('utf-8'),
                    bytes.fromhex(salt_hex), int(iterations_s)
                )
                return hmac.compare_digest(digest.hex(), hash_hex)
            except Exception:
                return False
        # 旧版 XOR 格式兼容
        try:
            return self._xor_decrypt(stored) == password
        except Exception:
            return False

    def _xor_encrypt(self, content: str) -> str:
        result = []
        for i, c in enumerate(content):
            key_c = self.XOR_KEY[i % len(self.XOR_KEY)]
            result.append(chr(ord(c) ^ ord(key_c)))
        return ''.join(result).encode('utf-8').hex()

    def _xor_decrypt(self, encrypted: str) -> str:
        try:
            content = bytes.fromhex(encrypted).decode('utf-8')
            result = []
            for i, c in enumerate(content):
                key_c = self.XOR_KEY[i % len(self.XOR_KEY)]
                result.append(chr(ord(c) ^ ord(key_c)))
            return ''.join(result)
        except:
            return ""


    # ------------------------------
    # 接口定义
    # ------------------------------
    @property
    def routes(self):
        return [
            {
                "path": "/login",
                "name": "用户登录",
                "methods": ["POST"],
                "params": [
                    {"name": "username", "type": "string", "required": True},
                    {"name": "password", "type": "string", "required": True}
                ],
                "view_func": self.login_api
            },
            {
                "path": "/logout",
                "name": "用户登出",
                "methods": ["POST", "GET"],
                "view_func": self.logout_api
            },
            {
                "path": "/user/info",
                "name": "获取当前用户信息",
                "methods": ["GET"],
                "view_func": self.get_user_info_api
            },
            {
                "path": "/config",
                "name": "获取插件配置",
                "methods": ["GET"],
                "view_func": self.get_config_api
            },
            {
                "path": "/config",
                "name": "更新插件配置",
                "methods": ["POST"],
                "params": [
                    {"name": "SESSION_EXPIRE", "type": "int", "required": False, "description": "会话有效期(秒)"}
                ],
                "view_func": self.update_config_api
            }
        ]

    @permission_required("public")
    def login_api(self):
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")
        if not username or not password:
            return self.error_response("用户名和密码不能为空", 400)
        # 登录失败锁定检查（v4.3.0）：锁定期间返回通用错误信息，不泄露锁定细节
        locked, _ = self._check_login_locked(username)
        if locked:
            return self.error_response("尝试次数过多，请稍后再试", 429)
        success, token, user = self.login(username, password)
        if success:
            # 登录成功，清除该维度的失败计数
            self._clear_login_attempts(username)
            response = self.success_response(data={
                "token": token,
                "id": user["id"],
                "username": user["username"],
                "nickname": user["nickname"],
                "role": user["role"]
            })
            # 会话 token：HttpOnly Cookie（JS 不可读，防 XSS 窃取）
            response.set_cookie(
                'token',
                token,
                max_age=self.SESSION_EXPIRE,
                path='/',
                httponly=True,
                samesite='Lax',
                secure=global_var.SESSION_COOKIE_SECURE
            )
            # CSRF token：非 HttpOnly Cookie，前端读取后放入 X-CSRF-Token 头（双提交校验）
            csrf_token = secrets.token_hex(16)
            response.set_cookie(
                'csrf_token',
                csrf_token,
                max_age=self.SESSION_EXPIRE,
                path='/',
                httponly=False,
                samesite='Lax',
                secure=global_var.SESSION_COOKIE_SECURE
            )
            return response
        # 登录失败：记录失败计数，连续达阈值触发锁定
        self._record_login_failure(username)
        return self.error_response("用户名或密码错误", 401)
    
    @permission_required("public")
    def logout_api(self):
        # 打印所有请求头和Cookie，排查传递问题
        # self.logger.info(f"请求头: {dict(request.headers)}")
        # self.logger.info(f"Cookie: {request.cookies}")
        # 优先从请求头取，再从Cookie取，最后从POST参数取兜底
        token = (
            request.headers.get("X-Token") 
            or request.cookies.get("token")
            or request.form.get("token")
        )
        
        if token:
            removed_count = self.sessions.pop(token, None)
            self._save_sessions()
            self.logger.info(f"用户登出成功，已销毁token: {token[:8]}...")
        else:
            self.logger.warning("登出请求未携带有效token")
        
        # 构造响应，无论token是否存在都清除客户端Cookie
        response = self.success_response(message="登出成功")
        response.set_cookie('token', '', expires=0, path='/', httponly=True, samesite='Lax')
        response.set_cookie('csrf_token', '', expires=0, path='/', samesite='Lax')
        return response

    @permission_required("user")
    def get_user_info_api(self):
        token = request.headers.get("X-Token") or request.cookies.get("token")
        user = self.verify_token(token)
        if user:
            return self.success_response(data=user)
        return self.error_response("未登录", 401)

    @permission_required("user")
    def get_config_api(self):
        """获取插件配置接口"""
        config = {
            "SESSION_EXPIRE": self.config["SESSION_EXPIRE"]
        }
        return self.success_response(data=config)

    @permission_required("admin")
    def update_config_api(self):
        """更新插件配置接口"""
        update_data = request.validated_data

        if "SESSION_EXPIRE" in update_data:
            self.config["SESSION_EXPIRE"] = update_data["SESSION_EXPIRE"]
            self.SESSION_EXPIRE = update_data["SESSION_EXPIRE"]
        
        self.save_config()
        self.logger.info(f"插件配置已更新: {update_data}")
        return self.success_response(data={
            "SESSION_EXPIRE": self.SESSION_EXPIRE
        }, message="配置更新成功")