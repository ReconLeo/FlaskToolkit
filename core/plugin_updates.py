# -*- coding: utf-8 -*-
"""插件级更新源（v4.15，第三方插件市场铺路）——复用框架版本检查（update_checker）模式。

- 数据源：插件 plugin.json 可选声明 `update_feed`（http(s) JSON 源），管理员触发批量检查；
- feed 格式：{"latest_version", "published_at", "download_url", "sha256", "changes"[, "signature"]}；
- 缓存：data/cache/plugin_updates.json，TTL = UPDATE_CHECK_INTERVAL 小时（默认 24），force 可跳过；
- 校验：配置 UPDATE_PUBLIC_KEY_PEM 后强制验签（复用 package_sign 的 RSA-SHA256 方案）；
- 版本比较：复用 update_checker.is_newer（tuple 逐位比较，不引第三方依赖）；
- 异步惰性：单插件 3s 超时，失败静默（仅日志），不阻塞批量检查；
- 更新下载后的安装仍走既有门禁（install_from_package：完整性校验 + 静态扫描 + enforce）——
  更新源只提供元数据，不绕过安全链路。
"""
import json
import logging
import os
import time

import global_var
from core.update_checker import is_newer

logger = logging.getLogger('flask.app')

FEED_REQUIRED_FIELDS = ('latest_version', 'published_at', 'download_url')
SIGNED_FIELDS = ('latest_version', 'published_at', 'download_url', 'sha256', 'changes')


def _cache_file() -> str:
    return os.path.join(global_var.BASE_DIR, 'data', 'cache', 'plugin_updates.json')


def _read_cache() -> dict:
    try:
        with open(_cache_file(), encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _write_cache(cache: dict):
    try:
        path = _cache_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("写入插件更新检查缓存失败: %s", e)


def _fetch_feed(feed_url: str, timeout: float = 3.0) -> dict:
    """拉取插件 feed 并做结构校验；失败抛异常（调用方捕获）"""
    import urllib.request
    req = urllib.request.Request(feed_url, headers={'User-Agent': 'FlaskToolkit/plugin-update-checker'})
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
    """feed 签名验证：配置了 UPDATE_PUBLIC_KEY_PEM 时强制验签。
    返回 (ok, message)；未配置公钥且无签名 → 放行（仅 sha256 层）。"""
    pem = global_var.get_user_config().get('UPDATE_PUBLIC_KEY_PEM') or ''
    if not pem:
        return True, '未配置公钥（跳过签名验证）'
    if not os.path.exists(pem):
        return False, f'公钥文件不存在: {pem}'
    manifest = {k: d.get(k) for k in SIGNED_FIELDS if k in d}
    try:
        from core.package_sign import verify_signature
        ok, msg = verify_signature(manifest, pem)
    except Exception as e:
        return False, f'签名验证异常: {e}'
    if not ok:
        return False, msg
    return True, msg


def _current_version(plugin_name) -> str:
    for p in global_var.plugin_catalog:
        if p.get('name') == plugin_name:
            return str(p.get('version') or '')
    return ''


def check_plugin_update(plugin_name: str, force: bool = False) -> dict:
    """检查单个插件更新（缓存 TTL 内直接返回缓存）。
    返回 {'name','current_version','latest_version','available','download_url',
          'sha256','changes','published_at','feed_url','repo','error'}"""
    feed_url, repo = '', ''
    for p in global_var.plugin_catalog:
        if p.get('name') == plugin_name:
            feed_url = str(p.get('update_feed') or '')
            repo = str(p.get('repo') or '')
            break
    cur = _current_version(plugin_name)
    result = {'name': plugin_name, 'current_version': cur, 'latest_version': '',
              'available': False, 'download_url': '', 'sha256': '', 'changes': '',
              'published_at': '', 'feed_url': feed_url, 'repo': repo, 'error': ''}
    if not feed_url:
        return result  # 未声明更新源

    cache = _read_cache()
    entry = cache.get(plugin_name)
    _iv = global_var.get_user_config().get('UPDATE_CHECK_INTERVAL')
    interval_h = int(_iv) if _iv is not None else 24  # 0 表示立即过期
    if (not force and entry and entry.get('checked_at')
            and time.time() - entry['checked_at'] <= interval_h * 3600):
        for k in ('latest_version', 'download_url', 'sha256', 'changes', 'published_at'):
            if k in entry:
                result[k] = entry[k]
        result['available'] = bool(entry.get('latest_version')) and is_newer(entry['latest_version'], cur)
        return result

    try:
        d = _fetch_feed(feed_url)
        ok, msg = _verify_feed_signature(d)
        if not ok:
            result['error'] = msg
            logger.warning("插件 %s 更新源签名验证失败: %s", plugin_name, msg)
            return result
        latest = str(d.get('latest_version') or '')
        entry = {
            'checked_at': time.time(),
            'latest_version': latest,
            'download_url': str(d.get('download_url', '')),
            'sha256': str(d.get('sha256', '')),
            'changes': str(d.get('changes', '')),
            'published_at': str(d.get('published_at', '')),
        }
        cache[plugin_name] = entry
        _write_cache(cache)
        for k in ('latest_version', 'download_url', 'sha256', 'changes', 'published_at'):
            result[k] = entry[k]
        result['available'] = bool(latest) and is_newer(latest, cur)
    except Exception as e:
        result['error'] = str(e)[:200]
        logger.warning("插件 %s 更新源检查失败: %s", plugin_name, e)
    return result


def check_all_plugin_updates(force: bool = False) -> list:
    """批量检查所有声明 update_feed 的插件（逐个独立超时，失败静默）"""
    out = []
    for p in global_var.plugin_catalog:
        if p.get('update_feed'):
            out.append(check_plugin_update(str(p.get('name')), force=force))
    return out
