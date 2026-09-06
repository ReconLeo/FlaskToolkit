# -*- coding: utf-8 -*-
"""tools/desktop_launcher.py — v4.11 Reachability M5：FlaskToolkit 桌面启动器（tkinter 标准库）

面向"有极客精神但不想碰命令行"的普通用户：双击启动、选共享模式、复制访问地址、
打开浏览器进入后台。与框架解耦——用 subprocess 启动 ``python app.py``，不 import
框架核心（避免初始化副作用）；数据准备复用 ``core/network``（纯标准库、只读配置）。

用法：
    python tools/desktop_launcher.py            # 打开图形窗口
    python tools/desktop_launcher.py --smoke    # 无 GUI：打印配置准备与地址（测试用）
    python tools/desktop_launcher.py --shared   # 启动时预选"共享给局域网"
    python tools/desktop_launcher.py --port 5010

说明：
- 共享模式写入 data/user_config.json 的 HOST（0.0.0.0=共享 / 127.0.0.1=仅本机）
- 二维码需可选依赖 qrcode + pillow（缺失仅隐藏二维码区，其余功能不受影响）
- 无图形显示环境（headless）时提示改用命令行；--smoke 可在任意环境运行
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USER_CONFIG_FILE = os.path.join(BASE_DIR, 'data', 'user_config.json')
APP_PY = os.path.join(BASE_DIR, 'app.py')


# ------------------------------ 配置读写（独立实现，不 import global_var 的写路径） ------------------------------

def load_user_config() -> dict:
    try:
        with open(USER_CONFIG_FILE, encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_user_config(data: dict) -> None:
    os.makedirs(os.path.dirname(USER_CONFIG_FILE), exist_ok=True)
    with open(USER_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def prepare_config(shared: bool) -> str:
    """按共享模式写 HOST 配置，返回生效的绑定地址。"""
    data = load_user_config()
    data['HOST'] = '0.0.0.0' if shared else '127.0.0.1'
    save_user_config(data)
    return data['HOST']


# ------------------------------ 地址信息（复用 core/network 的纯逻辑） ------------------------------

def generate_access_info(port, shared=None) -> dict:
    """生成展示用访问信息：{host, port, scheme, urls, lan_addresses, mdns}。

    import core/network 前先加载 user_config（global_var.load_user_config），
    使 get_access_urls 读到刚写入的 HOST。shared=None 时不改写配置。
    """
    sys.path.insert(0, BASE_DIR)
    import global_var
    global_var.load_user_config()
    if shared is not None:
        global_var._user_config['HOST'] = '0.0.0.0' if shared else '127.0.0.1'
    from core import network as net_mod
    if port:
        net_mod.register_effective_port(int(port))
    return {
        'host': net_mod.get_binding_host(),
        'port': net_mod.get_effective_port(),
        'scheme': net_mod.get_scheme(),
        'urls': net_mod.get_access_urls(),
        'lan_addresses': net_mod.get_lan_addresses(),
        'mdns_hostname': net_mod.get_mdns_hostname(),
        'mdns_enabled': net_mod.is_mdns_enabled(),
    }


# ------------------------------ 服务进程管理 ------------------------------

def start_server(port='') -> subprocess.Popen:
    env = dict(os.environ)
    if port and str(port).strip().isdigit():
        env['FLASKTOOLKIT_PORT'] = str(port).strip()
    return subprocess.Popen([sys.executable, APP_PY],
                            cwd=BASE_DIR, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding='utf-8', errors='replace',
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def extract_port_from_output(line: str):
    """从启动输出解析实际端口：'Running on http://127.0.0.1:5011' 或 '服务启动地址: http://...:5011'。"""
    m = re.search(r'http://[^\s:]+:(\d+)', line) or re.search(r'https://[^\s:]+:(\d+)', line)
    return int(m.group(1)) if m else None


def monitor_output(proc: subprocess.Popen, on_line, on_port, on_exit):
    """后台线程读取子进程输出；解析端口、回传行、进程退出回调。"""
    def _run():
        port = None
        try:
            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                on_line(line)
                if port is None:
                    p = extract_port_from_output(line)
                    if p:
                        port = p
                        on_port(p)
        except Exception:
            pass
        finally:
            on_exit(port)
    t = threading.Thread(target=_run, daemon=True, name='launcher-monitor')
    t.start()
    return t


# ------------------------------ GUI（tkinter） ------------------------------

def run_gui(initial_shared=False, initial_port=''):
    import tkinter as tk
    from tkinter import messagebox, ttk

    try:
        import PIL.Image, PIL.ImageTk  # noqa: F401
        import qrcode
        _HAS_QR = True
    except Exception:
        _HAS_QR = False

    root = tk.Tk()
    root.title('FlaskToolkit 启动器')
    root.geometry('460x430')
    root.resizable(False, False)

    proc = {'p': None}
    status_var = tk.StringVar(value='未启动')
    port_var = tk.StringVar(value=initial_port)
    shared_var = tk.BooleanVar(value=initial_shared)
    log_var = tk.StringVar(value='启动后此处显示服务输出')

    # ---- 模式选择 ----
    tk.Label(root, text='访问模式：').pack(anchor='w', padx=14, pady=(14, 2))
    frame_mode = tk.Frame(root)
    frame_mode.pack(anchor='w', padx=24)
    tk.Radiobutton(frame_mode, text='仅本机访问', variable=shared_var, value=False).pack(side='left')
    tk.Radiobutton(frame_mode, text='共享给局域网（同一 Wi-Fi/网线设备可访问）', variable=shared_var, value=True).pack(side='left', padx=10)

    # ---- 端口 ----
    tk.Label(root, text='端口（留空自动选择）：').pack(anchor='w', padx=14, pady=(10, 2))
    tk.Entry(root, textvariable=port_var, width=14).pack(anchor='w', padx=24)

    # ---- 按钮 ----
    btn_frame = tk.Frame(root)
    btn_frame.pack(anchor='w', padx=14, pady=10)
    start_btn = tk.Button(btn_frame, text='启动服务', width=12,
                          command=lambda: on_start(start_btn, stop_btn))
    start_btn.pack(side='left')
    stop_btn = tk.Button(btn_frame, text='停止服务', width=12, state='disabled',
                         command=lambda: on_stop(start_btn, stop_btn))
    stop_btn.pack(side='left', padx=8)

    # ---- 状态 ----
    tk.Label(root, textvariable=status_var, fg='#15803d').pack(anchor='w', padx=14)

    # ---- 地址列表 ----
    tk.Label(root, text='访问地址：').pack(anchor='w', padx=14, pady=(10, 2))
    url_list = tk.Listbox(root, height=4, font=('Consolas', 11))
    url_list.pack(fill='x', padx=14)

    act_frame = tk.Frame(root)
    act_frame.pack(anchor='w', padx=14, pady=8)
    tk.Button(act_frame, text='复制选中地址', command=lambda: copy_selected(url_list)).pack(side='left')
    tk.Button(act_frame, text='打开浏览器', command=lambda: open_browser(url_list)).pack(side='left', padx=8)
    refresh_btn = tk.Button(act_frame, text='刷新地址', command=lambda: refresh_urls(url_list))
    refresh_btn.pack(side='left', padx=8)

    # ---- 日志 ----
    log_lbl = tk.Label(root, textvariable=log_var, fg='#6b7280', wraplength=420, justify='left')
    log_lbl.pack(anchor='w', padx=14, pady=(6, 10))

    def refresh_urls(url_list):
        url_list.delete(0, 'end')
        info = generate_access_info(port_var.get(), shared=None)
        for it in info['urls']:
            url_list.insert('end', it['url'])
        if not info['urls']:
            url_list.insert('end', '（暂无可用地址，请确认共享模式）')

    def copy_selected(url_list):
        sel = url_list.curselection()
        if not sel:
            messagebox.showinfo('提示', '请先在列表中选择一个地址')
            return
        url = url_list.get(sel[0])
        root.clipboard_clear()
        root.clipboard_append(url)
        status_var.set(f'已复制：{url}')

    def open_browser(url_list):
        import webbrowser
        sel = url_list.curselection()
        url = url_list.get(sel[0]) if sel else (url_list.get(0) if url_list.size() else '')
        if url:
            webbrowser.open(url)

    def on_start(start_btn, stop_btn):
        if proc['p'] and proc['p'].poll() is None:
            return
        shared = bool(shared_var.get())
        prepare_config(shared)
        proc['p'] = start_server(port_var.get())
        start_btn.config(state='disabled')
        stop_btn.config(state='normal')
        status_var.set('启动中...')
        log_var.set('正在启动 FlaskToolkit...')
        refresh_urls(url_list)

        def on_line(line):
            log_var.set(line[-100:])

        def on_port(p):
            status_var.set(f'运行中（端口 {p}）')
            refresh_urls(url_list)

        def on_exit(p):
            if proc['p'] and proc['p'].poll() is not None:
                status_var.set('服务已停止')
                log_var.set('服务进程已退出。')
                start_btn.config(state='normal')
                stop_btn.config(state='disabled')

        monitor_output(proc['p'], on_line, on_port, on_exit)

    def on_stop(start_btn, stop_btn):
        if proc['p'] and proc['p'].poll() is None:
            proc['p'].terminate()
            try:
                proc['p'].wait(timeout=5)
            except Exception:
                proc['p'].kill()
            proc['p'] = None
        start_btn.config(state='normal')
        stop_btn.config(state='disabled')
        status_var.set('已停止')
        log_var.set('服务已停止，可重新启动。')

    # 初始刷新
    refresh_urls(url_list)
    root.mainloop()


# ------------------------------ 入口 ------------------------------

def main():
    ap = argparse.ArgumentParser(description='FlaskToolkit 桌面启动器（v4.11 Reachability）')
    ap.add_argument('--smoke', action='store_true', help='无 GUI：打印配置准备与地址信息（测试用）')
    ap.add_argument('--shared', action='store_true', help='启动时预选"共享给局域网"')
    ap.add_argument('--port', default='', help='指定端口（留空自动选择）')
    args = ap.parse_args()

    if args.smoke:
        binding = prepare_config(args.shared)
        info = generate_access_info(args.port, shared=None)
        print(f'[smoke] 绑定地址: {binding}（{"共享局域网" if args.shared else "仅本机"}）')
        print(f'[smoke] 端口: {info["port"]}  协议: {info["scheme"]}')
        print(f'[smoke] 局域网 IP: {", ".join(info["lan_addresses"]) or "(无)"}')
        print(f'[smoke] 访问地址:')
        for it in info['urls']:
            print(f'  - {it["url"]}  ({it["label"]})')
        print(f'[smoke] mDNS: {"开启 (" + info["mdns_hostname"] + ".local)" if info["mdns_enabled"] else "关闭"}')
        return 0

    # GUI
    try:
        run_gui(initial_shared=args.shared, initial_port=args.port)
    except Exception as e:
        if 'display' in str(e).lower() or 'TclError' in type(e).__name__:
            print(f'无法打开图形窗口（当前环境可能无显示）：{e}')
            print('请改用命令行启动：python app.py（或 python tools/desktop_launcher.py --smoke 查看地址）')
            return 1
        raise
    return 0


if __name__ == '__main__':
    sys.exit(main())
