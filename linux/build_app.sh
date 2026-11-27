#!/usr/bin/env bash
# 构建 PyInstaller onedir 产物（在仓库根目录跑）
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

# 有些发行版（RHEL/Rocky/Alma 8）仓库里没有 libxcb-cursor，Qt 6.5+ 的 xcb 插件缺它
# 起不来；这里先把它取到 linux/vendor/lib/，spec 会一起打进产物。
# 取不到只警告——不影响不需要它的系统构建。
"$ROOT/linux/fetch_vendor_libs.sh" || \
  echo "  ! 未取得 libxcb-cursor.so.0：目标机器若也没有，Qt 后端会起不来（见 linux/README-Linux.md）"

if [ ! -x .venv-build/bin/pyinstaller ]; then
  echo "==> 创建构建环境 .venv-build"
  uv venv .venv-build --python 3.12 -q
  uv pip install --python .venv-build/bin/python -q -e ".[gui]" pyinstaller
fi
.venv-build/bin/pyinstaller linux/ocrsnip.spec --noconfirm \
  --distpath linux/dist --workpath linux/build
echo "==> 产物：linux/dist/ocrsnip/ocrsnip"
