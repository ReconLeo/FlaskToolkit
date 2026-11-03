#!/usr/bin/env bash
# pack_plugin.sh —— FlaskToolkit 插件打包封装
# ==============================================
# 用干净解释器 + 清空 PYTHONHOME/PYTHONPATH 调用框架 tools/package.py pack，
# 规避解释器环境注入的审计钩子/搜索路径干扰（见 subproject-rules.md §3）。
#
# 用法：
#   pack_plugin.sh <framework_root> <src_dir> -o <out.zip> [pack 其余参数]
#     framework_root : 框架根目录（含 tools/package.py），不硬编码
#     src_dir        : 插件源目录（backend: 含 plugin.json；frontend: 含 config.json）
#     -o <out.zip>   : 输出 .zip 路径（透传给 pack）
#     其余参数        : 如 --type backend / --sign private.pem / --src-layout 等
#
# 环境变量：
#   SYSTEM_PYTHON  干净 Python 解释器路径（缺省按 PATH 依次尝试 python3 / python，不写死路径）
#   也可改用 export FTK_FRAMEWORK_PATH 后只传 src_dir；优先取命令行第 1 参。
set -euo pipefail

if [ "$#" -lt 2 ]; then
    echo "用法: $0 <framework_root> <src_dir> -o <out.zip> [pack 参数...]" >&2
    exit 2
fi

FRAMEWORK_ROOT="$1"
SRC_DIR="$2"
shift 2

# 源目录先转绝对路径（后续会 cd 到框架根，避免相对路径失效）
SRC_DIR="$(cd "$SRC_DIR" && pwd)"

# 把 -o/--output 后面的输出路径也转绝对路径，使产物落在调用者目录
args=()
prev=""
for a in "$@"; do
  if [ "$prev" = "-o" ] || [ "$prev" = "--output" ]; then
    if [[ "$a" != /* ]]; then
      a="$(cd "$(dirname "$a")" && pwd)/$(basename "$a")"
    fi
  fi
  args+=("$a")
  prev="$a"
done
set -- "${args[@]}"

if [ ! -d "$FRAMEWORK_ROOT" ]; then
    echo "[错误] 框架根不存在: $FRAMEWORK_ROOT" >&2
    exit 1
fi
if [ ! -f "$FRAMEWORK_ROOT/tools/package.py" ]; then
    echo "[错误] 框架根缺少 tools/package.py，请确认传入了正确的框架根" >&2
    exit 1
fi

PY="${SYSTEM_PYTHON:-}"
if [ -z "$PY" ]; then
    PY="$(command -v python3 || true)"
fi
if [ -z "$PY" ]; then
    PY="$(command -v python || true)"
fi
if [ -z "$PY" ]; then
    echo "[错误] 未找到可用 Python（可设置 SYSTEM_PYTHON 指定解释器路径）" >&2
    exit 1
fi

echo "[pack] Python: $PY"
echo "[pack] 框架根: $FRAMEWORK_ROOT"
echo "[pack] 源目录: $SRC_DIR"
cd "$FRAMEWORK_ROOT"
# 清空 PYTHONHOME/PYTHONPATH 规避审计钩子；不写死任何绝对路径
env -u PYTHONHOME -u PYTHONPATH "$PY" tools/package.py pack "$SRC_DIR" "$@"
