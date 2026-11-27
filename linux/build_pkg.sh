#!/usr/bin/env bash
# 把 PyInstaller 产物打成可分发的 Linux 包：
#   1) ocrsnip-<ver>-linux-x64.tar.gz   通用绿色版（任何发行版，无需 root）
#   2) ocrsnip_<ver>_amd64.deb          Debian/Ubuntu/Mint 等
#
# 前提：已经跑过 pyinstaller linux/ocrsnip.spec（见 build_app.sh）
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
LINUX="$ROOT/linux"
DIST="$LINUX/dist/ocrsnip"
OUT="$ROOT/releases"
VER=$(cd "$ROOT" && .venv-build/bin/python -c "import ocrsnip; print(ocrsnip.__version__)" 2>/dev/null || echo 0.0.0)
NAME="ocrsnip-$VER-linux-x64"

[ -x "$DIST/ocrsnip" ] || { echo "没有构建产物：$DIST/ocrsnip（先跑 linux/build_app.sh）" >&2; exit 1; }
mkdir -p "$OUT"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# ---------- 1) 通用绿色版 ----------
echo "==> 通用绿色版 $NAME.tar.gz"
STAGE="$WORK/$NAME"
mkdir -p "$STAGE"
cp -a "$DIST/." "$STAGE/"
install -m 755 "$LINUX/install.sh" "$LINUX/uninstall.sh" "$STAGE/"
install -m 644 "$LINUX/ocrsnip.service" "$LINUX/ocrsnip.desktop" "$LINUX/ocrsnip.png" \
               "$LINUX/README-Linux.md" "$STAGE/"
tar -C "$WORK" -czf "$OUT/$NAME.tar.gz" "$NAME"
echo "    $(du -h "$OUT/$NAME.tar.gz" | cut -f1)  $OUT/$NAME.tar.gz"

# ---------- 2) deb ----------
echo "==> deb 包"
PKG="$WORK/pkg"
mkdir -p "$PKG/DEBIAN" "$PKG/opt/ocrsnip" "$PKG/usr/bin" \
         "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/256x256/apps"
cp -a "$DIST/." "$PKG/opt/ocrsnip/"
install -m 755 "$LINUX/uninstall.sh" "$PKG/opt/ocrsnip/uninstall.sh"
cat > "$PKG/usr/bin/ocrsnip" <<'WRAP'
#!/bin/sh
exec /opt/ocrsnip/ocrsnip "$@"
WRAP
chmod 755 "$PKG/usr/bin/ocrsnip"
install -m 644 "$LINUX/ocrsnip.png" "$PKG/usr/share/icons/hicolor/256x256/apps/ocrsnip.png"
sed -e 's|@EXEC@|/usr/bin/ocrsnip|g' -e 's|@ICON@|ocrsnip|g' "$LINUX/ocrsnip.desktop" \
  > "$PKG/usr/share/applications/ocrsnip.desktop"
sed -e 's|@EXEC@|/opt/ocrsnip/ocrsnip|g' "$LINUX/ocrsnip.service" \
  > "$PKG/opt/ocrsnip/ocrsnip.service"
# 用户级服务需要用户自己 enable（deb 的 postinst 不该动用户会话）
cat > "$PKG/opt/ocrsnip/enable-autostart.sh" <<'SH'
#!/bin/sh
# 注册当前用户的 systemd 用户服务 + 桌面自启
set -e
UNIT="$HOME/.config/systemd/user"; AUTO="$HOME/.config/autostart"
mkdir -p "$UNIT" "$AUTO"
sed "s|@EXEC@|/opt/ocrsnip/ocrsnip|g" /opt/ocrsnip/ocrsnip.service > "$UNIT/ocrsnip.service"
sed -e "s|@EXEC@|/opt/ocrsnip/ocrsnip|g" -e "s|@ICON@|ocrsnip|g" \
  /usr/share/applications/ocrsnip.desktop > "$AUTO/ocrsnip.desktop"
systemctl --user daemon-reload
systemctl --user enable --now ocrsnip.service
echo "已启用 ocrsnip 用户服务：systemctl --user status ocrsnip"
SH
chmod 755 "$PKG/opt/ocrsnip/enable-autostart.sh"

SIZE=$(du -sk "$PKG" | cut -f1)
cat > "$PKG/DEBIAN/control" <<CTRL
Package: ocrsnip
Version: $VER
Section: utils
Priority: optional
Architecture: amd64
Installed-Size: $SIZE
Maintainer: chendx <chendx@localhost>
Depends: libc6, libgl1, libegl1, libglvnd0, libglx0, libxcb1
Recommends: libxcb-cursor0, xclip, xdotool
Homepage: https://github.com/chendx/ocr-snip
Description: Hotkey screenshot OCR to clipboard
 Press Ctrl+Alt+Q, drag a box, the text inside goes straight to the clipboard.
 Self-contained (Python + Qt bundled), no system GTK/PyGObject required.
 .
 按 Ctrl+Alt+Q 框选屏幕，框内文字直接进剪贴板。
 自带 Python 与 Qt 运行时，不依赖系统 GTK/PyGObject。
CTRL
cat > "$PKG/DEBIAN/postinst" <<'POST'
#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
  cat <<'MSG'

ocrsnip 已安装到 /opt/ocrsnip，命令为 /usr/bin/ocrsnip。
要让热键在登录后自动生效，请运行一次（仅影响当前用户）：
    /opt/ocrsnip/enable-autostart.sh

自检：ocrsnip doctor
MSG
fi
exit 0
POST
chmod 755 "$PKG/DEBIAN/postinst"
fakeroot dpkg-deb --build --root-owner-group "$PKG" "$OUT/ocrsnip_${VER}_amd64.deb" >/dev/null
echo "    $(du -h "$OUT/ocrsnip_${VER}_amd64.deb" | cut -f1)  $OUT/ocrsnip_${VER}_amd64.deb"
