#!/usr/bin/env bash
# 构建 PyInstaller onedir 产物（在仓库根目录跑）
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
if [ ! -x .venv-build/bin/pyinstaller ]; then
  echo "==> 创建构建环境 .venv-build"
  uv venv .venv-build --python 3.12 -q
  uv pip install --python .venv-build/bin/python -q -e ".[gui]" pyinstaller
fi
.venv-build/bin/pyinstaller linux/ocrsnip.spec --noconfirm \
  --distpath linux/dist --workpath linux/build
echo "==> 产物：linux/dist/ocrsnip/ocrsnip"
