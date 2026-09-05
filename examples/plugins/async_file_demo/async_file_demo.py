# -*- coding: utf-8 -*-
"""
示例插件：异步任务与文件上传（async_file_demo）
================================================
展示框架的文件处理与异步任务能力：

1. 文件上传：allowed_upload_types / max_upload_size（MB，本示例 20MB）限制 + save_uploaded_file 保存（保存前统一预检）。
2. 异步任务：run_async_task 在后台线程处理大文件（不阻塞请求），
   get_async_task_status 轮询进度/结果。
3. 结果下载：send_file_response 返回处理结果文件。

安装后访问：
- 页面  /plugin/async_file_demo
- API   POST /api/async_file_demo/upload            （上传并启动异步处理，user 权限）
- API   GET  /api/async_file_demo/status/<task_id>  （查询任务状态，user 权限）
- API   GET  /api/async_file_demo/result/<task_id>  （下载处理结果，user 权限）

流程：上传 .txt/.log/.csv/.json → 立即返回 task_id → 后台统计
行数/单词数/字符数 → 前端轮询 status 直到 success → 下载 result。
"""
import json
import os
import time
from typing import List, Dict

from plugins.base_plugin import BasePlugin, permission as permission_required

# 异步处理结果目录（v4.5.0：位于插件自属数据目录 plugins/data/async_file_demo/results/，隐式豁免）


class AsyncFileDemoPlugin(BasePlugin):
    name = "async_file_demo"
    title = "示例：异步任务与文件上传"
    description = "文件处理示例：上传文本文件（类型/大小限制）→ 异步任务处理（统计行数/词数/字符数）→ 轮询任务状态 → 下载处理结果，展示 save_uploaded_file / run_async_task / send_file_response。"
    version = "1.1.0"
    author = "FlaskToolkit Examples"
    category = "示例"
    permission = "user"
    require_framework_version = "4.3.2"  # get_data_path 为 v4.3.2 能力

    # 允许上传的文件类型（空列表 = 不限；框架在 save_uploaded_file 中自动校验）
    @property
    def allowed_upload_types(self) -> List[str]:
        return ['.txt', '.log', '.csv', '.json', '.md']

    # 插件级上传上限（MB，v4.2.2 统一机制）：save_uploaded_file 保存前自动预检；
    # 不声明则回退全局默认 MAX_UPLOAD_SIZE_MB（100MB）
    @property
    def max_upload_size(self):
        return 20  # 20MB

    # ---------------- 路由 ----------------
    @property
    def routes(self) -> List[Dict]:
        return [
            {
                "path": "/upload",
                "name": "上传文件并启动异步处理",
                "methods": ["POST"],
                "params": [
                    {"name": "file", "type": "file", "required": True, "description": "文本文件（.txt/.log/.csv/.json/.md）"}
                ],
                "view_func": self.upload_and_process,
            },
            {
                "path": "/quota",
                "name": "查询存储配额状态",
                "methods": ["GET"],
                "params": [],
                "view_func": self.get_quota,
            },
            {
                "path": "/status/<task_id>",
                "name": "查询异步任务状态",
                "methods": ["GET"],
                "params": [],
                "view_func": self.get_status,
            },
            {
                "path": "/result/<task_id>",
                "name": "下载处理结果",
                "methods": ["GET"],
                "params": [],
                "view_func": self.get_result,
            },
        ]

    @permission_required("user")
    def upload_and_process(self):
        """上传文件并启动异步处理，立即返回 task_id"""
        from flask import request
        try:
            # 1. 配额预检（v4.9.1）：现有用量 + 新文件大小 <= 插件配额（storage:limit 声明）
            up = request.files.get("file")
            if up is None:
                return self.error_response("未收到文件字段 file", code=400)
            up.stream.seek(0, 2)
            fsize = up.stream.tell()
            up.stream.seek(0)
            qc = self.check_upload(fsize)
            if not qc["ok"]:
                return self.error_response(
                    f"存储配额不足：已用 {qc['usage_mb']:.1f}MB / 限额 "
                    f"{qc['limit_mb']:.0f}MB（剩余 {qc['remaining_mb']:.1f}MB），请清理后重试",
                    code=413)
            # 2. 保存上传文件（自动校验 allowed_upload_types）
            temp_path, original_name = self.save_uploaded_file("file")
        except ValueError as e:
            return self.error_response(str(e), code=400)
        except Exception as e:
            self.logger.error(f"上传文件失败: {e}", exc_info=True)
            return self.error_response(f"上传失败: {e}", code=400)

        # 2. 启动异步任务：在后台线程统计文件，不阻塞请求
        task_id = self.run_async_task(
            self._process_file, temp_path, original_name
        )
        return self.success_response(
            data={
                "task_id": task_id,
                "filename": original_name,
                "message": "已提交异步处理，请轮询 /api/async_file_demo/status/<task_id>",
            },
            message="上传成功，任务已启动",
        )

    @permission_required("user")
    def get_quota(self):
        """查询存储配额状态（v4.9.1）：限额/已用/剩余（MB），0 限额=无限制"""
        qi = self.quota_info()
        return self.success_response(data=qi)

    @permission_required("user")
    def get_status(self, task_id: str):
        """查询异步任务状态（running/success/failed/not_found）"""
        status = self.get_async_task_status(task_id)
        # 若任务完成，附带结果摘要
        if status.get("status") == "success":
            result = status.get("result") or {}
            status["summary"] = {
                "filename": result.get("filename"),
                "lines": result.get("lines"),
                "words": result.get("words"),
                "chars": result.get("chars"),
                "result_file": result.get("result_file"),
            }
        return self.success_response(data=status, message="任务状态查询成功")

    @permission_required("user")
    def get_result(self, task_id: str):
        """下载处理结果文件"""
        status = self.get_async_task_status(task_id)
        if status.get("status") != "success":
            return self.error_response(
                "任务未完成或不存在，请先轮询状态", code=400
            )
        result = status.get("result") or {}
        result_file = result.get("result_file")
        if not result_file or not os.path.exists(result_file):
            return self.error_response("结果文件不存在", code=404)
        return self.send_file_response(
            result_file,
            download_name=result.get("result_name", "result.json"),
            mimetype="application/json",
        )

    # ---------------- 异步处理函数 ----------------
    def _process_file(self, temp_path: str, original_name: str) -> Dict:
        """后台线程执行的文件统计任务，返回处理结果"""
        # 模拟耗时处理（展示异步必要性），真实场景可处理更大文件
        time.sleep(2)

        lines = words = chars = 0
        try:
            with open(temp_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    lines += 1
                    words += len(line.split())
                    chars += len(line)
        except Exception as e:
            raise RuntimeError(f"读取文件失败: {e}")

        # 生成结果文件
        result_dir = self.get_data_path('results')
        os.makedirs(result_dir, exist_ok=True)
        result_file = os.path.join(result_dir, f"result_{int(time.time())}.json")
        result = {
            "filename": original_name,
            "lines": lines,
            "words": words,
            "chars": chars,
            "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        result["result_file"] = result_file
        result["result_name"] = f"stat_{original_name.replace('.', '_')}.json"
        return result

    # ---------------- 页面 ----------------
    def page(self):
        return self.render("async_file_demo.html", allowed=self.allowed_upload_types)
