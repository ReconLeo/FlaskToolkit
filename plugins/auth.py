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
        "ALLOW_REGISTER": False,             # v4.10 M5 自助注册开关（默认关；开启后无邀请码需审核）
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
            if "status" not in user:
                user["status"] = "active"  # v4.10 M5：active/pending（老数据默认 active）
        
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
        """登录校验，返回(是否成功, token, 用户信息)；pending（待审核）用户禁止登录（v4.10 M5）"""
        for user in self.config["users"]:
            if user["username"] == username:
                if self._verify_password(password, user["password"]):
                    if user.get("status", "active") == "pending":
                        return False, "", {}
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
            "status": "active",  # v4.10 M5：管理员创建的用户直接可用
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

    def change_password(self, user_id: int, old_password: str, new_password: str,
                        keep_token: str = None):
        """自助修改密码（v4.10）：校验旧密码 → 更新哈希 → 踢掉该用户其他会话。

        返回 (ok, message)。keep_token 指定保留的会话（当前登录 token 不踢）。
        """
        if not new_password or len(new_password) < 6:
            return False, "新密码长度至少 6 位"
        for user in self.config["users"]:
            if user["id"] == user_id:
                if not self._verify_password(old_password, user["password"]):
                    return False, "原密码不正确"
                user["password"] = self._hash_password(new_password)
                self.save_config()
                # 踢掉该用户除 keep_token 外的全部登录会话
                expired = [
                    token for token, session in self.sessions.items()
                    if session["id"] == user_id and token != keep_token
                ]
                for token in expired:
                    self.sessions.pop(token, None)
                self._save_sessions()
                return True, "密码修改成功"
        return False, "用户不存在"

    def change_password_api(self):
        """自助修改密码接口（v4.10）：POST {old_password, new_password}，需登录"""
        data = request.get_json(silent=True) or {}
        old_pwd = data.get("old_password") or ""
        new_pwd = data.get("new_password") or ""
        user = getattr(request, 'user', None)
        if not user:
            return self.error_response("未登录", 401)
        cur_token = (request.headers.get("X-Token")
                     or request.cookies.get("token"))
        ok, msg = self.change_password(user["id"], old_pwd, new_pwd, keep_token=cur_token)
        if not ok:
            return self.error_response(msg, 400)
        return self.success_response(data={"message": msg})

    # ------------------------------
    # 邀请码自助注册（v4.10 M5）
    # ------------------------------
    def _invite_codes_file(self) -> str:
        """邀请码存储文件：插件自属数据目录 plugins/data/auth/invite_codes.json"""
        return self.get_data_path("invite_codes.json")

    def _load_invite_codes(self) -> dict:
        try:
            if os.path.exists(self._invite_codes_file()):
                with open(self._invite_codes_file(), encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    def _save_invite_codes(self, codes: dict) -> None:
        try:
            path = self._invite_codes_file()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(codes, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception as e:
            self.logger.error(f"邀请码保存失败: {str(e)}")

    def create_invite_code(self, note: str = '') -> dict:
        """生成一次性邀请码（FTK-XXXX-XXXX），供管理员发给受邀用户。"""
        codes = self._load_invite_codes()
        while True:
            code = 'FTK-' + secrets.token_hex(4).upper() + '-' + secrets.token_hex(2).upper()[:4]
            if code not in codes:
                break
        codes[code] = {"created_at": int(time.time()), "used_by": None, "note": note}
        self._save_invite_codes(codes)
        return {"code": code, "created_at": codes[code]["created_at"], "used_by": None, "note": note}

    def list_invite_codes(self) -> List[Dict]:
        """邀请码列表（含使用状态）"""
        codes = self._load_invite_codes()
        return [
            {"code": k, "created_at": v.get("created_at", 0), "used_by": v.get("used_by"),
             "note": v.get("note", "")}
            for k, v in codes.items()
        ]

    def revoke_invite_code(self, code: str) -> bool:
        """撤销（删除）邀请码"""
        codes = self._load_invite_codes()
        if code in codes:
            del codes[code]
            self._save_invite_codes(codes)
            return True
        return False

    def _consume_invite_code(self, code: str, username: str) -> bool:
        """校验并消费邀请码（一次性）：有效且未使用时标记 used_by 返回 True。"""
        codes = self._load_invite_codes()
        entry = codes.get(code)
        if entry is None or entry.get("used_by"):
            return False
        entry["used_by"] = username
        self._save_invite_codes(codes)
        return True

    # ------------------------------
    # 用户审核（v4.10 M5）：status pending/active
    # ------------------------------
    def is_pending(self, username: str) -> bool:
        """账号是否处于待审核状态（缺省视为 active）"""
        for user in self.config["users"]:
            if user["username"] == username:
                return user.get("status", "active") == "pending"
        return False

    def pending_users(self) -> List[Dict]:
        """待审核用户列表（剥离密码）"""
        return [
            {k: v for k, v in user.items() if k != "password"}
            for user in self.config["users"]
            if user.get("status", "active") == "pending"
        ]

    def approve_user(self, user_id: int) -> bool:
        """审核通过：pending → active"""
        for user in self.config["users"]:
            if user["id"] == user_id:
                if user.get("status", "active") == "active":
                    return False
                user["status"] = "active"
                self.save_config()
                return True
        return False

    def reject_user(self, user_id: int) -> bool:
        """拒绝注册申请：删除 pending 用户（仅允许拒绝待审核账号）"""
        for index, user in enumerate(self.config["users"]):
            if user["id"] == user_id:
                if user.get("status", "active") != "pending":
                    return False
                del self.config["users"][index]
                self.save_config()
                return True
        return False

    def register(self, username: str, password: str, nickname: str = None,
                 invite_code: str = None) -> tuple:
        """自助注册（v4.10 M5）：开关关闭直接拒绝；提供有效邀请码免审核 active，
        否则进入 pending 待管理员审核。返回 (ok, message, user)。"""
        if not self.config.get("ALLOW_REGISTER"):
            return False, "未开放自助注册", None
        if not username or not password:
            return False, "用户名和密码不能为空", None
        if len(password) < 6:
            return False, "密码长度至少 6 位", None
        for user in self.config["users"]:
            if user["username"] == username:
                return False, "用户名已存在", None
        status = "pending"
        if invite_code:
            if not self._consume_invite_code(invite_code, username):
                return False, "邀请码无效或已被使用", None
            status = "active"
        max_id = max([u["id"] for u in self.config["users"]], default=0) + 1
        new_user = {
            "id": max_id,
            "username": username,
            "password": self._hash_password(password),
            "nickname": nickname if nickname else username,
            "role": "user",
            "status": status,
            "create_time": int(time.time())
        }
        self.config["users"].append(new_user)
        self.save_config()
        msg = "注册成功" if status == "active" else "注册成功，等待管理员审核"
        return True, msg, {k: v for k, v in new_user.items() if k != "password"}

    @permission_required("public")
    def register_api(self):
        """自助注册接口（v4.10 M5）：POST {username, password, nickname?, invite_code?}"""
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or '').strip()
        password = data.get("password") or ''
        nickname = (data.get("nickname") or '').strip() or None
        invite_code = (data.get("invite_code") or '').strip() or None
        ok, msg, user = self.register(username, password, nickname, invite_code)
        if not ok:
            code = 403 if msg == "未开放自助注册" else 400
            return self.error_response(msg, code)
        return self.success_response(data={"user": user}, message=msg)

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

    # ------------------------------
    # 手动解封（user_manage 后台管理，v4.5.0）
    # ------------------------------
    def _login_lock_records(self, username: str) -> List[str]:
        """返回该用户名在 _login_attempts 中所有维度的锁定 key（username / ip_username 双维度兼容）"""
        mode = getattr(global_var, 'LOGIN_LOCK_MODE', 'ip_username')
        if mode == 'off':
            return []
        matches = []
        if mode == 'username':
            k = f"u:{username}"
            if k in self._login_attempts:
                matches.append(k)
        else:  # ip_username：清除该用户名对应的全部 IP 维度记录
            suffix = f":u:{username}"
            for k in self._login_attempts:
                if k.endswith(suffix):
                    matches.append(k)
        return matches

    def is_user_locked(self, username: str) -> bool:
        """查询该用户名当前是否处于锁定期（供后台展示锁定状态）"""
        if not self._login_attempts:
            return False
        now = time.time()
        for k in self._login_lock_records(username):
            rec = self._login_attempts.get(k)
            if rec and rec.get("locked_until", 0) > now:
                return True
        return False

    def unlock_user(self, username: str) -> bool:
        """手动解除该用户名所有维度的登录锁定（后台解封）；返回是否清除过记录"""
        keys = self._login_lock_records(username)
        removed = False
        for k in keys:
            self._login_attempts.pop(k, None)
            removed = True
        if removed:
            self.logger.info(f"后台解封用户: {username}（清除 {len(keys)} 条锁定记录）")
        return removed

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
                "path": "/register",
                "name": "用户注册",
                "methods": ["POST"],
                "params": [
                    {"name": "username", "type": "string", "required": True, "description": "用户名"},
                    {"name": "password", "type": "string", "required": True, "description": "密码（至少 6 位）"},
                    {"name": "nickname", "type": "string", "required": False, "description": "昵称"},
                    {"name": "invite_code", "type": "string", "required": False, "description": "邀请码（有码免审核）"}
                ],
                "view_func": self.register_api
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
                "path": "/change-password",
                "name": "修改我的密码",
                "methods": ["POST"],
                "params": [
                    {"name": "old_password", "type": "string", "required": True, "description": "原密码"},
                    {"name": "new_password", "type": "string", "required": True, "description": "新密码（至少 6 位）"}
                ],
                "view_func": self.change_password_api
            },
            {
                "path": "/config",
                "name": "更新插件配置",
                "methods": ["POST"],
                "params": [
                    {"name": "SESSION_EXPIRE", "type": "int", "required": False, "description": "会话有效期(秒)"},
                    {"name": "ALLOW_REGISTER", "type": "boolean", "required": False, "description": "开放自助注册（默认关）"}
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
        # v4.10 M5：待审核账号友好提示（pending 用户禁止登录）
        if self.is_pending(username or ''):
            return self.error_response("账号待管理员审核，请稍后再试", 403)
        # 登录失败锁定检查（v4.3.0）：锁定期间返回通用错误信息，不泄露锁定细节
        locked, _ = self._check_login_locked(username)
        if locked:
            return self.error_response("尝试次数过多，请稍后再试", 429)
        success, token, user = self.login(username, password)
        if success:
            # 登录成功，清除该维度的失败计数
            self._clear_login_attempts(username)
            # v4.10 强制改密：密码仍为默认 admin123 时置 true（前端登录后台弹改密窗）
            # login() 返回的 user_info 不含 password（安全剥离），按 id 反查 config 中的哈希
            _pwd_hash = ''
            for _u in self.config.get("users", []):
                if _u.get("id") == user["id"]:
                    _pwd_hash = _u.get("password", '')
                    break
            response = self.success_response(data={
                "token": token,
                "id": user["id"],
                "username": user["username"],
                "nickname": user["nickname"],
                "role": user["role"],
                "must_change_pwd": bool(_pwd_hash) and self._verify_password("admin123", _pwd_hash)
            })
            # 会话 token：HttpOnly Cookie（JS 不可读，防 XSS 窃取）
            # v4.12：Secure 属性自动——HTTPS 直连 / 反代外部 https 时开启，纯 HTTP 局域网关闭
            from core import network as _net
            _secure = _net.is_secure_cookie_mode()
            response.set_cookie(
                'token',
                token,
                max_age=self.SESSION_EXPIRE,
                path='/',
                httponly=True,
                samesite='Lax',
                secure=_secure
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
                secure=_secure
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
            "SESSION_EXPIRE": self.config["SESSION_EXPIRE"],
            "ALLOW_REGISTER": self.config.get("ALLOW_REGISTER", False)
        }
        return self.success_response(data=config)

    @permission_required("admin")
    def update_config_api(self):
        """更新插件配置接口"""
        update_data = request.validated_data

        if "SESSION_EXPIRE" in update_data:
            self.config["SESSION_EXPIRE"] = update_data["SESSION_EXPIRE"]
            self.SESSION_EXPIRE = update_data["SESSION_EXPIRE"]

        if "ALLOW_REGISTER" in update_data:
            self.config["ALLOW_REGISTER"] = bool(update_data["ALLOW_REGISTER"])

        self.save_config()
        self.logger.info(f"插件配置已更新: {update_data}")
        return self.success_response(data={
            "SESSION_EXPIRE": self.SESSION_EXPIRE,
            "ALLOW_REGISTER": self.config.get("ALLOW_REGISTER", False)
        }, message="配置更新成功")