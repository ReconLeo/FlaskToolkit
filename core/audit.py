# -*- coding: utf-8 -*-
"""审计日志：记录管理后台敏感操作（谁、何时、做了什么、结果）

- 落盘位置：<BASE_DIR>/data/audit.log（JSONL 追加）
- 设计定位：审计是运维追溯层，Factory Reset 各 scope 均不清除审计日志
  （stats_logs 仅清 data/stats.json 与 logs/），保证敏感操作痕迹可追溯。
- 操作者：优先取当前请求已鉴权用户（request.user.username，由鉴权中间件注入）；
  非请求上下文或匿名时回退为「匿名」/「系统」。
"""
import json
import os
import time

import global_var


def current_actor() -> str:
    """从当前请求解析操作者；无请求上下文返回「系统」，未登录返回「匿名」。
    v4.4.0 修复：getattr 访问须在 try 内——无请求上下文时 werkzeug LocalProxy
    抛 RuntimeError（非 AttributeError），后台线程（审计 flush/scheduler）调用
    此前会崩溃。"""
    try:
        from flask import request
        user = getattr(request, 'user', None)
        if user:
            return user.get('username', str(user.get('id', '未知用户')))
        return '匿名'
    except Exception:
        return '系统'


def current_ip() -> str:
    try:
        from flask import request
        return request.remote_addr or '-'
    except Exception:
        return '-'


def _audit_path() -> str:
    return os.path.join(global_var.BASE_DIR, 'data', 'audit.log')


def log_audit(action: str, target: str = '', result: str = 'ok', detail: str = '') -> dict:
    """写入一条审计记录。失败不阻断业务（审计尽力而为）。"""
    record = {
        "time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "actor": current_actor(),
        "ip": current_ip(),
        "action": action,
        "target": target,
        "result": result,
        "detail": detail,
    }
    path = _audit_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception as e:
        # 审计写入失败（如运行环境禁止写盘）不阻断业务
        logger_error = f"审计日志写入失败: {e}"
        try:
            import logging
            logging.getLogger('flask.app').warning(logger_error, extra={'plugin': 'system'})
        except Exception:
            pass
    return record


def get_audit_logs(lines: int = 50) -> list:
    """读取最近 N 条审计记录（倒序，最新在前）"""
    path = _audit_path()
    if not os.path.exists(path):
        return []
    records = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception:
        return []
    return records[-lines:][::-1]
