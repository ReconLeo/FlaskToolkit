# -*- coding: utf-8 -*-
"""
版本检查推送（v4.8.0，F1）：只读检查新版本，不负责更新（更新见 tools/update.py）

- 数据源：默认 GitHub raw changelog.json（只存最新版本变化），可配 UPDATE_FEED_URL 指向内网镜像。
- 异步惰性：app 启动后由调用方在后台线程触发；网络 3s 超时，失败静默（仅日志），不阻塞启动。
- 缓存：data/cache/update_check.json，TTL = UPDATE_CHECK_INTERVAL 小时（默认 24），force 可跳过。
- 校验：sha256 字段必检（若存在）；配置 UPDATE_PUBLIC_KEY_PEM 后强制验签 changelog signature
  （复用 core/package_sign.verify_signature 的 RSA-SHA256 方案）。
- 版本比较：tuple 化逐位比较（如 4.8.0 > 4.7.0），不引第三方依赖。
"""
import json
import logging
import os
import time
from typing import Optional

import global_var

logger = logging.getLogger('flask.app')

# changelog.json 的默认字段（release.py 生成时与之对齐）
FEED_REQUIRED_FIELDS = ('latest_version', 'published_at', 'changes')
# 签名覆盖的数据字段（与 tools/release.py --sign 对齐；不含 signature 本身）
SIGNED_FIELDS = ('latest_version', 'published_at', 'download_url', 'sha256', 'changes')


class UpdateInfo:
    """一次版本检查的结果"""
    def __init__(self, latest_version: str, published_at: str = '', download_url: str = '',
                 sha256: str = '', changes=None, checked_at: float = None, feed_url: str = ''):
        self.latest_version = latest_version
        self.published_at = published_at
        self.download_url = download_url
        self.sha256 = sha256
        self.changes = changes or []
        self.checked_at = checked_at if checked_at is not None else time.time()
        self.feed_url = feed_url

    def to_dict(self) -> dict:
        return {
            'latest_version': self.latest_version,
            'published_at': self.published_at,
            'download_url': self.download_url,
            'sha256': self.sha256,
            'changes': self.changes,
            'checked_at': self.checked_at,
            'feed_url': self.feed_url,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'UpdateInfo':
        return cls(
            latest_version=d.get('latest_version', ''),
            published_at=d.get('published_at', ''),
            download_url=d.get('download_url', ''),
            sha256=d.get('sha256', ''),
            changes=d.get('changes') or [],
            checked_at=d.get('checked_at'),
            feed_url=d.get('feed_url', ''),
        )


def parse_version(version: str) -> tuple:
    """版本号转可比较 tuple：'4.8.0' -> (4, 8, 0)；非法段按 0 处理"""
    parts = []
    for seg in str(version or '').strip().lstrip('vV').split('.'):
        try:
            parts.append(int(seg))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def is_newer(latest: str, current: str) -> bool:
    """latest > current 返回 True（tuple 逐位比较）"""
    return parse_version(latest) > parse_version(current)


def _cache_file() -> str:
    return os.path.join(global_var.BASE_DIR, 'data', 'cache', 'update_check.json')


def _read_cache() -> Optional[dict]:
    try:
        with open(_cache_file(), encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def _write_cache(info: UpdateInfo):
    try:
        path = _cache_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(info.to_dict(), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("写入版本检查缓存失败: %s", e)


def _cache_fresh(force: bool = False) -> Optional[UpdateInfo]:
    """返回未过期的缓存；force=True 或缓存缺失/过期返回 None"""
    if force:
        return None
    d = _read_cache()
    if not d or not d.get('latest_version'):
        return None
    _iv = global_var.get_user_config().get('UPDATE_CHECK_INTERVAL')
    interval_h = int(_iv) if _iv is not None else 24  # 0 表示立即过期（不因 or 吞掉）
    checked_at = d.get('checked_at') or 0
    if time.time() - checked_at > interval_h * 3600:
        return None
    return UpdateInfo.from_dict(d)


def _fetch_feed(feed_url: str, timeout: float = 3.0) -> dict:
    """拉取 changelog.json 并做结构校验；失败抛异常（调用方捕获）"""
    import urllib.request
    req = urllib.request.Request(feed_url, headers={'User-Agent': 'FlaskToolkit/update-checker'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode('utf-8')
    d = json.loads(raw)
    if not isinstance(d, dict):
        raise ValueError('数据源格式错误：应为 JSON 对象')
    for field in FEED_REQUIRED_FIELDS:
        if field not in d:
            raise ValueError(f'数据源缺少字段: {field}')
    return d


def _verify_feed_signature(d: dict) -> tuple:
    """changelog 签名验证：配置了 UPDATE_PUBLIC_KEY_PEM 时强制验签。
    返回 (ok, message)；未配置公钥且无签名 → 放行（仅 sha256 层）。"""
    pem = global_var.get_user_config().get('UPDATE_PUBLIC_KEY_PEM') or ''
    if not pem:
        return True, '未配置公钥（跳过签名验证）'
    if not os.path.exists(pem):
        return False, f'公钥文件不存在: {pem}'
    # 构造仅含签名覆盖字段的 manifest 副本（对齐 SIGNED_FIELDS），复用 package_sign 验签
    manifest = {k: d.get(k) for k in SIGNED_FIELDS if k in d}
    try:
        from core.package_sign import verify_signature
        ok, msg = verify_signature(manifest, pem)
    except Exception as e:
        return False, f'签名验证异常: {e}'
    if not ok:
        return False, msg
    return True, msg


def check_for_update(force: bool = False, feed_url: str = None) -> Optional[UpdateInfo]:
    """版本检查主入口：缓存优先；force 强制拉取。失败静默返回缓存（有则）或 None。"""
    # 缓存优先
    cached = _cache_fresh(force)
    if cached is not None:
        return cached

    url = feed_url or global_var.get_user_config().get('UPDATE_FEED_URL') or ''
    if not url:
        logger.warning("未配置 UPDATE_FEED_URL，跳过版本检查")
        return None
    try:
        d = _fetch_feed(url)
        ok, msg = _verify_feed_signature(d)
        if not ok:
            logger.warning("版本检查签名验证失败: %s", msg)
            # 签名强制失败：不写入缓存、不返回该数据（避免展示未验签内容）
            return None
        info = UpdateInfo(
            latest_version=str(d['latest_version']),
            published_at=str(d.get('published_at', '')),
            download_url=str(d.get('download_url', '')),
            sha256=str(d.get('sha256', '')),
            changes=d.get('changes') or [],
            feed_url=url,
        )
        _write_cache(info)
        return info
    except Exception as e:
        # 网络/解析失败：静默（有旧缓存则返回旧缓存，保证启动不报错）
        logger.debug("版本检查失败: %s", e)
        old = _read_cache()
        return UpdateInfo.from_dict(old) if old and old.get('latest_version') else None


def background_check():
    """后台线程入口：检查后仅日志（结果由下次启动横幅/后台 API 读取缓存）"""
    try:
        info = check_for_update()
        if info is None:
            return
        current = global_var.FRAMEWORK_VERSION
        if is_newer(info.latest_version, current):
            logger.info("发现新版本 v%s（当前 v%s，变更 %d 条，详见 tools/update.py --help）",
                        info.latest_version, current, len(info.changes))
        else:
            logger.info("版本检查完成：已是最新版本 v%s", current)
    except Exception:
        logger.debug("后台版本检查异常", exc_info=True)
