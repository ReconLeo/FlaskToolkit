# -*- coding: utf-8 -*-
"""M6 插件脚手架 + 手动安装工具回归（tools/scaffold.py + tools/install_plugin.py，v4.10）

覆盖：
A. scaffold backend：骨架文件生成（plugin.json / 主 .py / 可选 templates/static）、JSON 合法、py 语法、元信息正确
B. scaffold frontend：config.json / 入口 html / static 生成
C. scaffold 参数校验：非法插件名拒绝、非法 permission 拒绝
D. 安装闭环：package.py pack → install_plugin.py backend 安装到隔离框架根（落盘 + installed_files）
E. 同名与版本控制：重复安装拒绝 / 平级 --update 允许 / 降级拒绝
F. pip 依赖缺失提示
G. install_plugin.py frontend 安装 + frontend_tools.json 注册
H. install_plugin.py list 输出

运行：python tests/test_scaffold_tools.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_TESTS_DIR)
TOOLS_DIR = os.path.join(_PROJECT_ROOT, 'tools')
PY = sys.executable

results = []


def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


def run_cli(script, *args, expect_code=0):
    """运行 tools 下 CLI，返回 (code, stdout)。编码容错防 Windows gbk 解码崩溃。"""
    p = subprocess.run([PY, os.path.join(TOOLS_DIR, script), *args],
                       capture_output=True, text=True,
                       encoding='utf-8', errors='replace', cwd=_PROJECT_ROOT)
    ok = (p.returncode == expect_code)
    return ok, p.returncode, (p.stdout or '') + (p.stderr or '')


def make_fake_framework_root(root):
    """构造最小框架根：plugins/ + app.py + templates/ + data/（满足 resolve_base 校验）"""
    os.makedirs(os.path.join(root, 'plugins'))
    os.makedirs(os.path.join(root, 'templates'))
    os.makedirs(os.path.join(root, 'data'))
    with open(os.path.join(root, 'app.py'), 'w', encoding='utf-8') as f:
        f.write('# fake framework root for install tests\n')


def py_syntax_ok(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            src = f.read()
        compile(src, path, 'exec')
        return True
    except SyntaxError:
        return False


def main():
    work = tempfile.mkdtemp(prefix='ftk_scaffold_')
    base = os.path.join(work, 'framework')
    make_fake_framework_root(base)

    # ================= A. scaffold backend =================
    skel = os.path.join(work, 'skels')
    ok, code, out = run_cli('scaffold.py', 'backend', 'demo_tool',
                            '--output', skel, '--with-templates', '--with-static',
                            '--title', '演示插件', '--author', 'Tester')
    check("A1 scaffold backend 退出码 0", ok, f"code={code}")
    d = os.path.join(skel, 'demo_tool')
    check("A2 plugin.json 生成", os.path.isfile(os.path.join(d, 'plugin.json')))
    check("A3 主 .py 生成", os.path.isfile(os.path.join(d, 'demo_tool.py')))
    check("A4 templates 骨架生成",
          os.path.isfile(os.path.join(d, 'templates', 'demo_tool', 'index.html')))
    check("A5 static 骨架生成", os.path.isfile(os.path.join(d, 'static', 'style.css')))
    pj_ok = False
    if os.path.isfile(os.path.join(d, 'plugin.json')):
        try:
            meta = json.load(open(os.path.join(d, 'plugin.json'), encoding='utf-8'))
            pj_ok = (meta['name'] == 'demo_tool' and meta['version'] == '1.0.0'
                     and meta['permission'] == 'user' and meta['title'] == '演示插件')
        except Exception:
            meta = None
    check("A6 plugin.json 元信息正确", pj_ok, f"meta={meta if 'meta' in dir() else None}")
    check("A7 主 .py 语法合法", py_syntax_ok(os.path.join(d, 'demo_tool.py')))
    check("A8 提示含安装指引", 'install_plugin.py' in out)

    # ================= B. scaffold frontend =================
    ok, code, out = run_cli('scaffold.py', 'frontend', 'my_tool',
                            '--output', skel, '--with-static')
    check("B1 scaffold frontend 退出码 0", ok, f"code={code}")
    d = os.path.join(skel, 'my_tool')
    check("B2 config.json 生成", os.path.isfile(os.path.join(d, 'config.json')))
    check("B3 入口 html 生成", os.path.isfile(os.path.join(d, 'my_tool.html')))
    check("B4 static 生成", os.path.isfile(os.path.join(d, 'static', 'style.css')))
    cfg_ok = False
    if os.path.isfile(os.path.join(d, 'config.json')):
        try:
            cfg = json.load(open(os.path.join(d, 'config.json'), encoding='utf-8'))
            cfg_ok = (cfg['name'] == 'my_tool' and cfg['permission'] == 'user')
        except Exception:
            pass
    check("B5 config.json 元信息正确", cfg_ok)

    # ================= C. 参数校验 =================
    ok, code, out = run_cli('scaffold.py', 'backend', 'Bad Name!', '--output', skel, expect_code=1)
    check("C1 非法插件名拒绝", ok, f"code={code}")
    ok, code, out = run_cli('scaffold.py', 'backend', 'ok_name', '--permission', 'root',
                            '--output', skel, expect_code=1)
    check("C2 非法 permission 拒绝", ok, f"code={code}")

    # ================= D. 打包 + 安装闭环 =================
    ok, code, out = run_cli('package.py', 'pack', os.path.join(skel, 'demo_tool'),
                            '-o', os.path.join(work, 'demo_tool.zip'), '--type', 'backend')
    check("D1 package pack 成功", ok, f"code={code}")

    ok, code, out = run_cli('install_plugin.py', 'backend', os.path.join(work, 'demo_tool.zip'),
                            '--base', base)
    check("D2 install backend 成功", ok, f"code={code}")
    check("D3 主 py 落盘", os.path.isfile(os.path.join(base, 'plugins', 'demo_tool', 'demo_tool.py')))
    check("D4 描述文件落盘", os.path.isfile(os.path.join(base, 'plugins', 'demo_tool', 'demo_tool.json')))
    check("D5 模板落盘", os.path.isfile(os.path.join(base, 'templates', 'plugins', 'demo_tool', 'index.html')))
    check("D6 静态落盘",
          os.path.isfile(os.path.join(base, 'templates', 'plugins', 'static', 'demo_tool', 'style.css')))
    installed_ok = False
    meta_path = os.path.join(base, 'plugins', 'demo_tool', 'demo_tool.json')
    if os.path.isfile(meta_path):
        try:
            meta = json.load(open(meta_path, encoding='utf-8'))
            installed_ok = ('installed_files' in meta
                            and 'plugins/demo_tool/demo_tool.py' in meta['installed_files'])
        except Exception:
            pass
    check("D7 installed_files 清单写入", installed_ok)
    check("D8 输出含加载提示", '启动框架后自动加载' in out)

    # ================= E. 同名与版本控制 =================
    ok, code, out = run_cli('install_plugin.py', 'backend', os.path.join(work, 'demo_tool.zip'),
                            '--base', base, expect_code=1)
    check("E1 重复安装拒绝", ok, f"code={code}")
    ok, code, out = run_cli('install_plugin.py', 'backend', os.path.join(work, 'demo_tool.zip'),
                            '--update', '--base', base)
    check("E2 平级 --update 允许", ok, f"code={code}")

    # 构造 1.1.0 升级包（同步改 plugin.json 与类属性 version，通过框架一致性校验）
    v2 = os.path.join(work, 'demo_tool_v110')
    shutil.copytree(os.path.join(skel, 'demo_tool'), v2)
    for fname in ('plugin.json', 'demo_tool.py'):
        p = os.path.join(v2, fname)
        src = open(p, encoding='utf-8').read()
        src = src.replace('"1.0.0"', '"1.1.0"').replace('= "1.0.0"', '= "1.1.0"')
        open(p, 'w', encoding='utf-8').write(src)
    # 加 pip 依赖声明（用于 F 组）
    pj = os.path.join(v2, 'plugin.json')
    meta = json.load(open(pj, encoding='utf-8'))
    meta['pip_dependencies'] = ['nonexistent_pkg_ftk_xyz']
    json.dump(meta, open(pj, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    ok, code, out = run_cli('package.py', 'pack', v2, '-o', os.path.join(work, 'demo_tool_v110.zip'),
                            '--type', 'backend')
    check("E3 升级包打包成功", ok, f"code={code}")
    ok, code, out = run_cli('install_plugin.py', 'backend', os.path.join(work, 'demo_tool_v110.zip'),
                            '--update', '--base', base)
    check("E4 升级 --update 成功", ok, f"code={code}")
    ok, code, out = run_cli('install_plugin.py', 'backend', os.path.join(work, 'demo_tool.zip'),
                            '--update', '--base', base, expect_code=1)
    check("E5 降级拒绝", ok, f"code={code}")

    # ================= F. pip 依赖缺失提示 =================
    # 重新执行升级安装（平级幂等），校验输出包含缺失 pip 依赖提示与安装命令
    ok, code, fout = run_cli('install_plugin.py', 'backend', os.path.join(work, 'demo_tool_v110.zip'),
                             '--update', '--base', base)
    check("F0 升级安装（F 组前置）成功", ok, f"code={code}")
    check("F1 缺失 pip 依赖提示", 'pip install nonexistent_pkg_ftk_xyz' in fout,
          'install 输出包含缺失包名与 pip 命令')
    # v4.23.5：pip 缺失改为警告级别醒目提示（此前是 [提示]，容易淹没在输出里），并给出缺失原因
    check("F2 缺失 pip 依赖以 [警告] 输出", '[警告] 缺失 pip 依赖' in fout, fout[-200:])
    check("F3 提示插件将被跳过加载", '跳过加载' in fout and '未加载' in fout, '')

    # ================= G. frontend 安装 =================
    ok, code, out = run_cli('package.py', 'pack', os.path.join(skel, 'my_tool'),
                            '-o', os.path.join(work, 'my_tool.zip'), '--type', 'frontend')
    check("G1 frontend 打包成功", ok, f"code={code}")
    ok, code, out = run_cli('install_plugin.py', 'frontend', os.path.join(work, 'my_tool.zip'),
                            '--base', base)
    check("G2 install frontend 成功", ok, f"code={code}")
    check("G3 入口 html 落盘",
          os.path.isfile(os.path.join(base, 'templates', 'frontend_tools', 'my_tool.html')))
    check("G4 静态资源落盘",
          os.path.isfile(os.path.join(base, 'templates', 'frontend_tools', 'static', 'my_tool', 'style.css')))
    reg_ok = False
    cfg_file = os.path.join(base, 'data', 'frontend_tools.json')
    if os.path.isfile(cfg_file):
        try:
            tools = json.load(open(cfg_file, encoding='utf-8'))
            reg_ok = any(t['name'] == 'my_tool' and t['version'] == '1.0.0' and t['type'] == 'frontend'
                         for t in tools)
        except Exception:
            pass
    check("G5 frontend_tools.json 注册", reg_ok)
    ok, code, out = run_cli('install_plugin.py', 'frontend', os.path.join(work, 'my_tool.zip'),
                            '--base', base, expect_code=1)
    check("G6 frontend 重复安装拒绝", ok, f"code={code}")

    # ================= H. list =================
    ok, code, out = run_cli('install_plugin.py', 'list', '--base', base)
    check("H1 list 退出码 0", ok, f"code={code}")
    check("H2 list 含后端插件", 'demo_tool' in out)
    check("H3 list 含前端工具", 'my_tool' in out)

    # ================= I. uninstall（M6-Extra 离线卸载 + 单插件空间清理） =================
    # 准备数据目录与 filesystem:write 声明（模拟带自定义写目录的插件）
    os.makedirs(os.path.join(base, 'plugins', 'data', 'demo_tool'))
    os.makedirs(os.path.join(base, 'plugins', 'temp', 'demo_tool'))
    os.makedirs(os.path.join(base, 'uploads'))
    open(os.path.join(base, 'plugins', 'data', 'demo_tool', 'f.json'), 'w').write('{}')
    open(os.path.join(base, 'plugins', 'temp', 'demo_tool', 't'), 'w').write('x')
    open(os.path.join(base, 'uploads', 'a.txt'), 'w').write('x')
    meta = json.load(open(os.path.join(base, 'plugins', 'demo_tool', 'demo_tool.json'), encoding='utf-8'))
    meta['capabilities'] = ['filesystem:write:uploads/**']
    json.dump(meta, open(os.path.join(base, 'plugins', 'demo_tool', 'demo_tool.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    ok, code, out = run_cli('install_plugin.py', 'uninstall', 'backend', 'auth', '--base', base,
                            expect_code=1)
    check("I1 内置插件卸载保护", ok, f"code={code}")
    ok, code, out = run_cli('install_plugin.py', 'uninstall', 'backend', 'demo_tool', '--base', base)
    check("I2 uninstall backend 成功", ok, f"code={code}")
    check("I3 默认卸载删除主文件", not os.path.exists(os.path.join(base, 'plugins', 'demo_tool', 'demo_tool.py')), '')
    check("I4 默认卸载保留数据目录",
          os.path.isdir(os.path.join(base, 'plugins', 'data', 'demo_tool')), '')
    check("I5 默认卸载保留 write 声明目录", os.path.isdir(os.path.join(base, 'uploads')), '')

    # 重新安装后测 --purge-data 完整清理
    ok, code, out = run_cli('install_plugin.py', 'backend', os.path.join(work, 'demo_tool_v110.zip'),
                            '--base', base)
    check("I6 重装（供 purge 测试）成功", ok, f"code={code}")
    os.makedirs(os.path.join(base, 'plugins', 'data', 'demo_tool'), exist_ok=True)
    os.makedirs(os.path.join(base, 'plugins', 'temp', 'demo_tool'), exist_ok=True)
    os.makedirs(os.path.join(base, 'uploads'), exist_ok=True)
    open(os.path.join(base, 'plugins', 'data', 'demo_tool', 'f.json'), 'w').write('{}')
    open(os.path.join(base, 'plugins', 'temp', 'demo_tool', 't'), 'w').write('x')
    open(os.path.join(base, 'uploads', 'a.txt'), 'w').write('x')
    meta = json.load(open(os.path.join(base, 'plugins', 'demo_tool', 'demo_tool.json'), encoding='utf-8'))
    meta['capabilities'] = ['filesystem:write:uploads/**']
    json.dump(meta, open(os.path.join(base, 'plugins', 'demo_tool', 'demo_tool.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    ok, code, out = run_cli('install_plugin.py', 'uninstall', 'backend', 'demo_tool', '--purge-data',
                            '--base', base)
    check("I7 uninstall --purge-data 成功", ok, f"code={code}")
    check("I8 purge 清理数据目录", not os.path.exists(os.path.join(base, 'plugins', 'data', 'demo_tool')), '')
    check("I9 purge 清理临时目录", not os.path.exists(os.path.join(base, 'plugins', 'temp', 'demo_tool')), '')
    check("I10 purge 清理 write 声明目录", not os.path.exists(os.path.join(base, 'uploads')), '')

    # frontend 卸载
    ok, code, out = run_cli('install_plugin.py', 'uninstall', 'frontend', 'my_tool', '--base', base)
    check("I11 uninstall frontend 成功", ok, f"code={code}")
    check("I12 前端入口 html 删除",
          not os.path.exists(os.path.join(base, 'templates', 'frontend_tools', 'my_tool.html')), '')
    tools_after = json.load(open(os.path.join(base, 'data', 'frontend_tools.json'), encoding='utf-8'))
    check("I13 前端注册清单移除", all(t['name'] != 'my_tool' for t in tools_after), '')
    ok, code, out = run_cli('install_plugin.py', 'uninstall', 'frontend', 'my_tool', '--base', base,
                            expect_code=1)
    check("I14 二次卸载报错", ok, f"code={code}")

    # ================= J. v4.23.5：输出目录自动创建 + --scan-mode 显式模式 =================
    # J1 输出目录不存在时 pack 自动创建（FTK-XI-02：此前直接抛 FileNotFoundError traceback）
    _newout = os.path.join(work, 'dist_new', 'nested', 'demo_tool.zip')
    ok, code, out = run_cli('package.py', 'pack', os.path.join(skel, 'demo_tool'),
                            '-o', _newout, '--type', 'backend', '-y')
    check("J1 pack 自动创建输出目录", ok and os.path.isfile(_newout), f"code={code}")

    # J2-J6 --scan-mode（FTK-XI-03：--base 不影响扫描模式，显式覆盖 + 打印来源）
    risky = os.path.join(skel, 'risky_tool')
    ok, code, out = run_cli('scaffold.py', 'backend', 'risky_tool', '--output', skel)
    risky_main = os.path.join(risky, 'risky_tool.py')
    if os.path.isfile(risky_main):
        src = open(risky_main, encoding='utf-8').read()
        src = src.replace('from plugins.base_plugin import',
                          'import subprocess\nfrom plugins.base_plugin import', 1)
        src += ('\n\ndef run_external():\n'
                '    return subprocess.run(["ffmpeg", "-version"])\n')
        open(risky_main, 'w', encoding='utf-8').write(src)
    ok, code, out = run_cli('package.py', 'pack', risky,
                            '-o', os.path.join(work, 'risky.zip'), '--type', 'backend', '-y')
    check("J2 高风险插件包打包成功", ok, f"code={code}")
    ok, code, out = run_cli('install_plugin.py', 'backend', os.path.join(work, 'risky.zip'),
                            '--base', base, '--scan-mode', 'enforce', expect_code=1)
    check("J3 --scan-mode enforce 拒绝高风险包", ok, f"code={code}")
    check("J4 拒绝输出含可操作原因与 ignore 指引",
          '拒绝原因' in out and 'scan:ignore' in out, out[-260:])
    ok, code, out = run_cli('install_plugin.py', 'backend', os.path.join(work, 'risky.zip'),
                            '--base', base, '--scan-mode', 'report')
    check("J5 --scan-mode report 放行并提示 enforce 将拒绝",
          ok and 'report 模式下放行' in out, f"code={code} out={out[-160:]}")
    check("J6 输出打印生效模式与来源",
          '模式=report' in out and '--scan-mode 显式指定' in out, out[:160])

    print(f'\n==== M6 脚手架 + 手动安装工具回归：共 {len(results)} 项，'
          f'通过 {sum(1 for _, c, _ in results if c)}，'
          f'失败 {sum(1 for _, c, _ in results if not c)} ====')
    try:
        shutil.rmtree(work, ignore_errors=True)
    except Exception:
        pass
    ok_all = all(c for _, c, _ in results)
    sys.exit(0 if ok_all else 1)


if __name__ == '__main__':
    main()
