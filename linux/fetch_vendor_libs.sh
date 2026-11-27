#!/usr/bin/env bash
# 把 Qt xcb 平台插件离不开的 libxcb-cursor.so.0 取到 linux/vendor/lib/。
#
# 为什么需要它：Qt 6.5 起，xcb 平台插件会 dlopen libxcb-cursor.so.0，缺了它
# 面板根本起不来，Qt 只丢一句 "Could not load the Qt platform plugin xcb"。
# Debian/Ubuntu 有 libxcb-cursor0；RHEL/Rocky/Alma 8 的官方仓库没有这个包
# （只有 EPEL 里的 xcb-util-cursor）。
#
# 所以这里不装包，而是把发行版的包解开、只取里面的那个 .so：
#   * 不需要 root，构建机上就能跑
#   * 取到的文件会被 ocrsnip.spec 打进 _internal，跟着产物一起走
#   * 幂等：系统里或 vendor 里已经有了就直接跳过
#
# 用法：
#   ./linux/fetch_vendor_libs.sh        # 独立跑
#   ./linux/build_app.sh                # 构建时会自动调它
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
VENDOR="$ROOT/linux/vendor/lib"
SONAME=libxcb-cursor.so.0

log() { printf '    %s\n' "$*"; }

if [ -e "$VENDOR/$SONAME" ]; then
  log "vendor 里已有 $SONAME（跳过）"
  exit 0
fi
if ldconfig -p 2>/dev/null | grep -q "$SONAME"; then
  log "系统里已有 $SONAME（跳过）"
  exit 0
fi

mkdir -p "$VENDOR"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# 从 rpm 系仓库取（RHEL / Rocky / Alma / Fedora / openSUSE 用 dnf 或 zypper）
extract_rpm() {
  command -v rpm2cpio >/dev/null && command -v cpio >/dev/null || return 1
  local url=""
  if command -v dnf >/dev/null; then
    url=$(dnf -q repoquery --location xcb-util-cursor 2>/dev/null | head -n1) || true
  fi
  if [ -z "$url" ] && command -v zypper >/dev/null; then
    # openSUSE 包名不同，交给 zypper 下载到本地目录
    zypper --non-interactive --pkg-cache-dir "$WORK" download libxcb-cursor0 >/dev/null 2>&1 || true
    url=$(ls "$WORK"/*.rpm 2>/dev/null | head -n1) || true
    [ -n "$url" ] && url="file://$url"
  fi
  [ -n "$url" ] || return 1
  log "下载 $(basename "$url")"
  case "$url" in
    file://*) cp "${url#file://}" "$WORK/pkg.rpm" ;;
    *) curl -fsSL --retry 2 -o "$WORK/pkg.rpm" "$url" || return 1 ;;
  esac
  ( cd "$WORK" && rpm2cpio pkg.rpm | cpio -idm --quiet ) || return 1
  local so
  so=$(find "$WORK" -name "${SONAME}.0.0*" -type f | head -n1) || true
  [ -n "$so" ] || return 1
  cp "$so" "$VENDOR/"
}

# 从 deb 系仓库取（Debian / Ubuntu / Mint）
extract_deb() {
  command -v apt-get >/dev/null && command -v dpkg-deb >/dev/null || return 1
  ( cd "$WORK" && apt-get download libxcb-cursor0 >/dev/null 2>&1 ) || return 1
  local deb
  deb=$(find "$WORK" -maxdepth 1 -name '*.deb' | head -n1) || true
  [ -n "$deb" ] || return 1
  dpkg-deb -x "$deb" "$WORK/x" || return 1
  local so
  so=$(find "$WORK/x" -name "${SONAME}.0.0*" -type f | head -n1) || true
  [ -n "$so" ] || return 1
  cp "$so" "$VENDOR/"
}

if extract_rpm || extract_deb; then
  src=$(ls "$VENDOR"/${SONAME}.0.0* 2>/dev/null | head -n1) || true
  if [ -n "${src:-}" ]; then
    ln -sf "$(basename "$src")" "$VENDOR/$SONAME"
    log "已放入 ${src#"$ROOT/"}"
    exit 0
  fi
fi

cat >&2 <<MSG
! 没能自动取到 $SONAME（离线、或者系统里没有 dnf/apt 系工具）。
  打包版缺它 Qt 后端就起不来。手工装一次再重跑构建即可：
    Debian/Ubuntu : sudo apt install libxcb-cursor0
    RHEL/Rocky 8+ : sudo dnf install --enablerepo=epel xcb-util-cursor
    Arch          : sudo pacman -S xcb-util-cursor
  或者把该 .so 直接放到 $VENDOR/$SONAME。
MSG
exit 1
