# -*- coding: utf-8 -*-
"""FlaskToolkit 全量回归脚本（运维手动运行）

遍历 tests/test_*.py 逐个执行（串行），汇总通过/失败/超时/耗时，
退出码可被 CI 或脚本捕获（全部通过 0，任一失败/超时返回 1）。

用法：
  python tools/run_all_tests.py                     # 全量回归（默认串行，日志到 temp/regress/）
  python tools/run_all_tests.py -p theme            # 只跑文件名含 theme 的测试
  python tools/run_all_tests.py -t 300              # 单测试超时秒数（默认 600，0 表示不限）
  python tools/run_all_tests.py --log-dir /tmp/reg  # 指定日志目录
  python tools/run_all_tests.py -v                  # 失败时打印该测试完整日志
  python tools/run_all_tests.py --keep              # 保留历史日志（默认每次清理）
  python tools/run_all_tests.py --list              # 仅列出待跑测试，不执行
  python tools/run_all_tests.py --no-cleanup         # 每个测试后不跑 tests/ci_cleanup.py 清理

说明：
- 测试脚本均为自包含（隔离目录），直接以当前 Python 解释器运行。
- 子进程注入 PYTHONIOENCODING=utf-8，避免 Windows 控制台乱码。
- 串行执行以规避测试间共享端口/资源的相互干扰。
"""
import argparse
import os
import re
import subprocess
import sys
import time

# 项目根：脚本位于 <root>/tools/run_all_tests.py
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TESTS_DIR = os.path.join(_PROJECT_ROOT, "tests")
_DEFAULT_LOG_DIR = os.path.join(_PROJECT_ROOT, "temp", "regress")

# 输出编码：Windows 控制台默认可能非 UTF-8，这里统一按 UTF-8 容错输出
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _run_env():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"   # 子进程测试输出统一 UTF-8
    env["PYTHONUNBUFFERED"] = "1"        # 实时落盘，便于卡死时查看进度
    return env


def run_frontend_jsdom(log_dir, verbose):
    """运行 tests/frontend_jsdom/ 下全部 .js（node + jsdom 前端验证）。返回 (passed, failed)。"""
    jsdir = os.path.join(_TESTS_DIR, "frontend_jsdom")
    scripts = sorted(f for f in os.listdir(jsdir) if f.endswith(".js"))
    passed, failed = [], []
    for idx, s in enumerate(scripts, 1):
        log_path = os.path.join(log_dir, "frontend_" + s.replace(".js", ".log"))
        start = time.time()
        with open(log_path, "w", encoding="utf-8") as fp:
            try:
                p = subprocess.run(["node", os.path.join(jsdir, s)],
                                   cwd=_PROJECT_ROOT, stdout=fp, stderr=subprocess.STDOUT,
                                   timeout=120)
                rc = p.returncode
            except subprocess.TimeoutExpired:
                rc = "TIMEOUT"
            except Exception as exc:  # pragma: no cover
                rc = "ERROR"
                fp.write("\n[run_all_tests] 前端验证异常: %s\n" % exc)
        dur = time.time() - start
        status = "PASS" if rc == 0 else ("TIMEOUT" if rc == "TIMEOUT" else ("ERROR" if rc == "ERROR" else "FAIL"))
        print("[fe %2d] %-8s %-32s %6.1fs" % (idx, status, s, dur))
        if status == "PASS":
            passed.append(s)
        else:
            failed.append(s)
            if verbose:
                print("  ---- %s 日志 ----" % s)
                with open(log_path, encoding="utf-8", errors="replace") as f:
                    print(f.read()[:3000])
                print("  ---- 结束 ----")
    return passed, failed


def collect_tests(pattern):
    tests = sorted(
        f for f in os.listdir(_TESTS_DIR)
        if f.startswith("test_") and f.endswith(".py")
    )
    if pattern:
        rx = re.compile(pattern, re.IGNORECASE)
        tests = [f for f in tests if rx.search(f)]
    return tests


def run_one(test_file, timeout, log_path, do_cleanup=True):
    """运行单个测试，返回 (exit_code, duration)。超时按失败处理。

    do_cleanup=True 时在测试后调用 tests/ci_cleanup.py（测试间清理，防互相污染）；
    ci_cleanup 失败不影响该测试结果（双保险，测试本身用隔离目录）。
    """
    start = time.time()
    log_fp = open(log_path, "w", encoding="utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, os.path.join(_TESTS_DIR, test_file)],
            cwd=_PROJECT_ROOT,
            env=_run_env(),
            stdout=log_fp,
            stderr=subprocess.STDOUT,
            timeout=timeout if timeout and timeout > 0 else None,
        )
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        rc = "TIMEOUT"
        log_fp.write("\n[run_all_tests] 超时（>%ss）已终止\n" % timeout)
    except Exception as exc:  # pragma: no cover
        rc = "ERROR"
        log_fp.write("\n[run_all_tests] 运行异常: %s\n" % exc)
    finally:
        if do_cleanup:
            try:
                log_fp.write("\n[run_all_tests] ci_cleanup\n")
                subprocess.run(
                    [sys.executable, os.path.join(_TESTS_DIR, "ci_cleanup.py")],
                    cwd=_PROJECT_ROOT,
                    env=_run_env(),
                    stdout=log_fp,
                    stderr=subprocess.STDOUT,
                    timeout=60,
                )
            except Exception:  # 清理失败不阻断回归
                pass
        log_fp.close()
    return rc, time.time() - start


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tools/run_all_tests.py", description=__doc__)
    parser.add_argument("-p", "--pattern", default=None,
                        help="按正则过滤测试文件名（如 'theme|user'）")
    parser.add_argument("-t", "--timeout", type=int, default=600,
                        help="单测试超时秒数（默认 600；0 表示不限）")
    parser.add_argument("--log-dir", default=_DEFAULT_LOG_DIR,
                        help="日志输出目录（默认 %(default)s）")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="失败/超时后打印该测试完整日志")
    parser.add_argument("--keep", action="store_true",
                        help="保留历史日志（默认每次运行前清理目标日志目录）")
    parser.add_argument("--list", action="store_true",
                        help="仅列出待跑测试，不执行")
    parser.add_argument("--no-cleanup", action="store_true",
                        help="每个测试后不运行 tests/ci_cleanup.py 测试间清理")
    parser.add_argument("--with-frontend", action="store_true",
                        help="额外运行 tests/frontend_jsdom/ 的 node 前端验证（需 node + jsdom）")
    args = parser.parse_args(argv)

    tests = collect_tests(args.pattern)
    if not tests:
        print("未匹配到任何测试（tests/test_*.py）。")
        return 2

    if args.list:
        print("待跑 %d 个测试：" % len(tests))
        for t in tests:
            print("  - %s" % t)
        return 0

    # 准备日志目录
    os.makedirs(args.log_dir, exist_ok=True)
    if not args.keep:
        for old in os.listdir(args.log_dir):
            if old.endswith(".log"):
                try:
                    os.remove(os.path.join(args.log_dir, old))
                except OSError:
                    pass

    total = len(tests)
    print("=" * 60)
    print("FlaskToolkit 全量回归  共 %d 个测试  超时上限 %ss" % (total, args.timeout or "无"))
    print("日志目录: %s" % args.log_dir)
    print("=" * 60)

    passed, failed = [], []
    total_dur = 0.0
    for idx, t in enumerate(tests, 1):
        log_path = os.path.join(args.log_dir, t.replace(".py", ".log"))
        rc, dur = run_one(t, args.timeout, log_path, do_cleanup=not args.no_cleanup)
        total_dur += dur
        status = "PASS" if rc == 0 else ("TIMEOUT" if rc == "TIMEOUT" else ("ERROR" if rc == "ERROR" else "FAIL"))
        line = "[%3d/%d] %-8s %-32s %6.1fs" % (idx, total, status, t, dur)
        print(line)
        if status == "PASS":
            passed.append(t)
        else:
            failed.append((t, status, log_path))
            if args.verbose:
                print("  ---- %s 日志 ----" % t)
                with open(log_path, encoding="utf-8", errors="replace") as f:
                    body = f.read()
                print(body[:4000] + ("\n  ...（日志已截断，完整见 %s）" % log_path if len(body) > 4000 else ""))
                print("  ---- 结束 ----")

    front_failed = []
    if args.with_frontend:
        print("\n---- 前端 jsdom 验证（--with-frontend）----")
        _fp, front_failed = run_frontend_jsdom(args.log_dir, args.verbose)
        print("---- 前端验证：通过 %d / %d ----" % (len(_fp), len(_fp) + len(front_failed)))

    print("=" * 60)
    print("回归完成：通过 %d / %d，失败 %d，耗时 %.1fs"
          % (len(passed), total, len(failed), total_dur))
    if front_failed:
        print("前端验证失败：%s" % ", ".join(front_failed))
    if failed or front_failed:
        print("失败/异常/超时清单：")
        for t, status, lp in failed:
            print("  [%s] %s  ->  %s" % (status, t, lp))
        print("日志保留于: %s" % args.log_dir)
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
