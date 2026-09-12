# -*- coding: utf-8 -*-
"""core/framework_manifest.py — 框架目录/文件统一清单（单一事实来源）

设计动机：升级框架（tools/update.py）、启动自检（core/selfcheck.py）、备份（tools/backup.py）、
Factory Reset（core/factory_reset.py）、Root 权限域判定（core/capabilities.py）等，都需判断
"哪些是框架核心文件、哪些是用户数据"。过去各处各自硬编码，每次新增功能都要在多处同步修改，
极易遗漏/漂移。本模块把这两类判定收敛到一处，供 core/ 与 tools/ 统一读取。

分类语义（互不重叠）：
- CORE_FILES / CORE_DIRS：框架核心内容，缺失 = 框架无法正常工作（自检致命）。
- USER_DATA_PATHS：用户数据路径（相对项目根），升级/备份时跳过保留（.gitignore 语义）。
- ROOT_RUNTIME_FILES：散落在项目根/plugins 的运行时用户文件（与 .gitignore 对齐）。
- is_framework_core_path：Root(framework:core) 域管辖范围判定（含插件内容目录豁免）。

本模块为纯常量 + 纯函数，模块级不 import global_var（避免其模块副作用）；
BASE_DIR 用 os.path 自推导，与 global_var.BASE_DIR 一致（项目根）。
"""

import os


# 项目根（与 global_var.BASE_DIR 一致；本文件位于 core/ 下）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ============================ 框架核心文件 ============================
# 相对 BASE_DIR；缺失视为致命，阻止启动（原 core/selfcheck.py CORE_FILES）
CORE_FILES = [
    'app.py', 'global_var.py',
    # v4.5.0: 前端工具注册清单默认路径迁移至 data/frontend_tools.json（运行时配置不入库，
    # 缺失不致命：load_frontend_tools 容错为空列表，旧版根目录文件由 migrate_legacy_config 自动迁移）
    'routes/__init__.py', 'routes/admin.py', 'routes/frontend.py',
    'routes/public.py', 'routes/interceptor.py', 'routes/plugin.py',
    'routes/security.py',
    'core/utils.py', 'core/plugin_loader.py', 'core/plugin_pack.py',
    'core/factory_reset.py', 'core/audit.py', 'core/package_sign.py',
    'core/permission.py', 'core/stats.py', 'core/logging_setup.py',
    'core/frontend_tools.py', 'core/watcher.py', 'core/selfcheck.py',
    # v4.3.x-v4.4.0 安全强化新增模块
    'core/plugin_scanner.py', 'core/capabilities.py', 'core/audit_hook.py',
    'core/plugin_cache.py', 'core/plugin_status.py',
    # v4.9.0 i18n + v4.9.1 配额声明
    'core/i18n.py', 'core/quota.py',
    # v4.15.0 Root 权限域 + 插件级更新源（routes/admin 顶层引用，缺失则 admin 路由 import 崩）
    'core/plugin_admin.py', 'core/plugin_updates.py',
    # v4.15.1 框架目录清单统一（被 selfcheck/capabilities/update 等引用，缺失即 import 崩）
    'core/framework_manifest.py',
    # v4.16 事件总线 + 插件真依赖解析（plugin_loader/base_plugin/routes 引用，缺失即 import 崩）
    'core/events.py', 'core/plugin_deps.py',
    # v4.17 设备检测 + 移动端模板分发（app/routes/BasePlugin 引用，缺失即 import 崩）
    'core/device.py',
    # v4.19 界面主题能力（app inject_i18n / routes public 引用 get_theme，缺失即 import 崩）
    'core/theme.py',
    'plugins/__init__.py', 'plugins/base_plugin.py',
    'plugins/auth.py', 'plugins/user_manage.py',
]


# ============================ 框架核心目录 ============================
# 缺失视为致命（原 core/selfcheck.py CORE_DIRS）
# 说明：documents/ 仅为开发文档（开发规范/交接文档/设计文档），不在精简运行包内（RUNTIME_TOP 不含），
#       缺失不影响框架运行——故不属于框架核心目录，不列入本清单（v4.15.1 小修）。
CORE_DIRS = ['routes', 'core', 'plugins', 'templates', 'tools', 'themes']  # themes: v4.19.2 可扩展主题目录


# ============================ 用户数据路径 ============================
# 相对项目根，与 .gitignore 语义对齐；升级（archive 后端）解压时显式跳过，备份时保留。
# 说明：locales/ 整体为框架内置 i18n 语言包（v4.9.0），不入本清单——更新/发布时随框架正常覆盖携带；
#       users/ 为 AI 助手本地数据（.gitignore 已忽略，非项目内容），发布包与框架备份均不携带。
# （原 tools/update.py USER_DATA_PATHS）
USER_DATA_PATHS = [
    'data',
    'plugins/configs',
    'plugins/data',
    'plugins/temp',
    'logs',
    '.plugin_cache',
    'workspace',
    'temp',
    'backups',
    'users',
]


# ============================ 根级散落的运行时用户文件 ============================
# 相对项目根，与 .gitignore 对齐；升级/备份时视为用户数据跳过保留
# （原 tools/update.py path_is_user_data 内联判断）
ROOT_RUNTIME_FILES = [
    'frontend_tools.json',
    '.version',
    'plugins/status.json',
]


# ============================ Root 域豁免规则（is_framework_core_path 用） ============================
# templates 下插件/前端工具内容目录（插件资产，Root 域豁免）
TEMPLATE_CONTENT_EXCLUDE = ('templates/plugins/', 'templates/frontend_tools/')
# plugins 下插件自属豁免目录（隐式豁免，Root 域豁免）
PLUGIN_DATA_EXCLUDE_PREFIXES = ('plugins/data/', 'plugins/temp/', 'plugins/configs/')
# 项目根级框架核心文件（Root 域管辖）
FRAMEWORK_ROOT_FILES = (
    'app.py', 'global_var.py', 'requirements.txt', 'changelog.json',
    'README.md', 'README.zh-CN.md', 'SECURITY.md',
)
# Root 域管辖的精确文件（相对项目根，不在 CORE_DIRS 顶层目录下）
FRAMEWORK_CORE_PATHS = ('data/user_config.json', 'data/frontend_tools.json', 'plugins/status.json')


# ============================ 备份范围（从用户数据清单派生） ============================
# 备份工具（tools/backup.py）的备份项：从 USER_DATA_PATHS 派生，排除纯临时/工作目录；
# 另加 plugins/status.json（插件启用状态，关键运行数据）。原 tools/backup.py BACKUP_ITEMS 硬编码迁移至此。
# 排除的纯临时/派生目录（备份无意义）：
_BACKUP_EXCLUDE = {'.plugin_cache', 'workspace', 'temp', 'backups', 'users', 'plugins/temp'}
# 需要额外备份的根级/plugins 散落运行文件（plugins/status.json；data/ 下已含 frontend_tools.json）
_BACKUP_EXTRA_FILES = ('plugins/status.json',)


def _build_backup_items():
    items = [(ud, ud) for ud in USER_DATA_PATHS if ud not in _BACKUP_EXCLUDE]
    for rf in _BACKUP_EXTRA_FILES:
        if (rf, rf) not in items:
            items.append((rf, rf))
    return items


# (源相对项目根, 备份内相对路径)
BACKUP_ITEMS = _build_backup_items()


# ============================ Factory Reset 目标路径（用户数据） ============================
# 重置工具（core/factory_reset.py）各 scope 的目标文件/目录（相对 BASE_DIR）。
# 均为用户数据路径（命中 USER_DATA_PATHS 语义），原 factory_reset 硬编码迁移至此。
RESET_STATS_FILE = 'data/stats.json'
RESET_SESSIONS_FILE = 'plugins/data/auth/sessions.json'
RESET_LEGACY_SESSIONS_FILE = 'plugins/data/sessions.json'  # v4.5.0 前的旧会话路径
RESET_AUTH_CONFIG_FILE = 'plugins/configs/auth.json'  # 内置插件配置（auth 恢复默认）
RESET_TEMP_DIRS = ['.plugin_cache', 'temp']  # 临时清理目标（相对 BASE_DIR，与既有重置行为一致）


# ============================ 判定函数 ============================

def _norm_path(p):
    """归一化路径：normcase（Windows 小写+统一分隔符）→ normpath → 正斜杠"""
    return os.path.normpath(os.path.normcase(str(p))).replace('\\', '/')


def _rel_to_base(path, base_dir=None):
    """绝对路径若位于 base_dir 下则转为相对（便于与相对声明比较）"""
    b = _norm_path(base_dir or BASE_DIR)
    p = _norm_path(path)
    if p.startswith(b + '/'):
        return p[len(b) + 1:]
    return p


def is_user_data_path(rel: str) -> bool:
    """判断包内相对路径是否属于用户数据路径（升级/备份时应跳过保留）。

    兼容 tools/update.py 的 path_is_user_data 语义：命中 USER_DATA_PATHS 或
    ROOT_RUNTIME_FILES（根级散落运行时用户文件）。"""
    rel = _norm_path(rel).strip('/')
    if not rel:
        return False
    for ud in USER_DATA_PATHS:
        if rel == ud or rel.startswith(ud + '/'):
            return True
    if rel in ROOT_RUNTIME_FILES:
        return True
    return False


# 向后兼容别名（原 tools/update.py 导出名）
path_is_user_data = is_user_data_path


def is_core_file(rel: str) -> bool:
    """判断相对项目根路径是否属于框架核心文件/目录（缺失致命）。

    命中 CORE_FILES 单个文件，或位于 CORE_DIRS 顶层目录下。"""
    rel = _norm_path(rel).strip('/')
    if not rel:
        return False
    if rel in CORE_FILES:
        return True
    top = rel.split('/')[0]
    return top in CORE_DIRS


def is_framework_core_path(path, base_dir=None) -> bool:
    """路径是否命中框架核心（framework:core Root 域管辖范围）：框架代码/模板/静态/配置。

    插件自属目录（plugins/data|temp|configs）与插件内容目录
    （templates/plugins/、templates/frontend_tools/）不在此列（分别为隐式豁免与插件资产）。
    相对/绝对路径均可判定（绝对路径先归一到 BASE_DIR 相对）。
    本函数原为 core/capabilities.py 私有逻辑，v4.15.1 迁移至统一清单供其复用。"""
    p = _rel_to_base(path, base_dir or BASE_DIR)
    if not p or p == '.':
        return False
    p = _norm_path(p).strip('/')
    top = p.split('/')[0]
    if p in FRAMEWORK_ROOT_FILES:
        return True
    if top in ('core', 'routes', 'static'):
        return True
    if top == 'templates':
        # 框架模板为 Root 管辖；插件/前端工具内容目录豁免
        return not (p.startswith(TEMPLATE_CONTENT_EXCLUDE[0])
                    or p.startswith(TEMPLATE_CONTENT_EXCLUDE[1]))
    if p in FRAMEWORK_CORE_PATHS:
        return True
    if p == 'plugins' or p.startswith('plugins/'):
        # plugins/ 下除自属豁免目录外均为受管核心（内置基类/鉴权 + 各插件主文件与描述文件）
        if any(p.startswith(prefix) for prefix in PLUGIN_DATA_EXCLUDE_PREFIXES):
            return False
        return True
    return False
