# -*- coding: utf-8 -*-
"""build_echo_plugin.py — 构建 echo_upload.zip 测试插件。

用法：python test_server/fixtures/build_echo_plugin.py
产物：test_server/fixtures/echo_upload.zip（zip 结构：plugin.json + echo_upload.py）

安装：框架后台「插件管理」上传安装（或 API /api/admin/plugins/upload 带 preview=1 能力确认后 confirm=1）。
卸载：后台卸载 + 清理（purge-data），删除 plugins/data/echo_upload/。
"""
import os
import shutil
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'echo_upload')
OUT = os.path.join(HERE, 'echo_upload.zip')


def main():
    # 注意：zipfile 'w' 模式直接覆盖旧文件，无需先删除（避免触发安全策略）
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
        for fn in ('plugin.json', 'echo_upload.py'):
            z.write(os.path.join(SRC, fn), arcname=fn)
    print('已生成 %s（%d 字节）' % (OUT, os.path.getsize(OUT)))
    # 展示 zip 内容确认结构
    with zipfile.ZipFile(OUT) as z:
        print('zip 内容：%s' % ', '.join(z.namelist()))


if __name__ == '__main__':
    main()
