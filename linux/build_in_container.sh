#!/usr/bin/env bash
# 在 ubuntu:22.04 容器里构建，把 glibc 底线降到 2.35（覆盖 Ubuntu 22.04+/Debian 12+/Mint 21+）
# 依赖：podman 或 docker。用法：./linux/build_in_container.sh
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
ENGINE=$(command -v podman || command -v docker)
[ -n "$ENGINE" ] || { echo "需要 podman 或 docker" >&2; exit 1; }
IMAGE=ubuntu:22.04

"$ENGINE" run --rm -v "$ROOT":/src:Z -w /src "$IMAGE" bash -lc '
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3.11 python3.11-venv python3-pip curl libgl1 libegl1 \
                   libxcb-cursor0 libxkbcommon-x11-0 binutils >/dev/null
curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || true
export PATH="$HOME/.local/bin:$PATH"
uv venv .venv-build --python python3.11 -q
uv pip install --python .venv-build/bin/python -q -e ".[gui]" pyinstaller
.venv-build/bin/pyinstaller linux/ocrsnip.spec --noconfirm \
  --distpath linux/dist --workpath linux/build
.venv-build/bin/python -c "import ocrsnip; print(\"built for\", __import__(\"platform\").libc_ver())"
'
echo "==> 容器内构建完成：linux/dist/ocrsnip/（glibc 2.35）"
echo "    接着跑 ./linux/build_pkg.sh 出包"
