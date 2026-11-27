#!/usr/bin/env bash
# 打 AppImage（单文件、免安装、任何发行版双击即用）。
# 前提：先跑 ./linux/build_app.sh 生成 linux/dist/ocrsnip/
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
LINUX="$ROOT/linux"; DIST="$LINUX/dist/ocrsnip"; OUT="$ROOT/releases"
CACHE="$LINUX/.cache"
VER=$(cd "$ROOT" && .venv-build/bin/python -c "import ocrsnip; print(ocrsnip.__version__)" 2>/dev/null || echo 0.0.0)
TOOL="$CACHE/appimagetool-x86_64.AppImage"
[ -x "$DIST/ocrsnip" ] || { echo "没有构建产物（先跑 linux/build_app.sh）" >&2; exit 1; }
mkdir -p "$CACHE" "$OUT"

if [ ! -x "$TOOL" ]; then
  echo "==> 下载 appimagetool"
  curl -fL --retry 3 -o "$TOOL" \
    https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$TOOL"
fi

APPDIR=$(mktemp -d)/ocrsnip.AppDir
mkdir -p "$APPDIR"
cp -a "$DIST/." "$APPDIR/"
install -m 644 "$LINUX/ocrsnip.png" "$APPDIR/ocrsnip.png"
install -m 644 "$LINUX/ocrsnip.png" "$APPDIR/.DirIcon"
sed -e 's|@EXEC@|ocrsnip|g' -e 's|@ICON@|ocrsnip|g' "$LINUX/ocrsnip.desktop" > "$APPDIR/ocrsnip.desktop"
cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/sh
HERE=$(dirname "$(readlink -f "$0")")
# 直接用打包内的解释器，不碰系统的 python
exec "$HERE/ocrsnip" "$@"
RUN
chmod 755 "$APPDIR/AppRun"

echo "==> 生成 AppImage"
ARCH=x86_64 "$TOOL" --appimage-extract-and-run --no-appstream "$APPDIR" \
  "$OUT/ocrsnip-$VER-x86_64.AppImage" >/dev/null
chmod +x "$OUT/ocrsnip-$VER-x86_64.AppImage"
echo "    $(du -h "$OUT/ocrsnip-$VER-x86_64.AppImage" | cut -f1)  $OUT/ocrsnip-$VER-x86_64.AppImage"
