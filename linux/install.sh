#!/usr/bin/env bash
# ocrsnip 通用安装脚本（Linux，无需 root）：装到 ~/.local/opt/ocrsnip，
# 注册 systemd 用户服务 + 桌面自启。
#
#   ./install.sh              安装/升级
#   ./install.sh --no-service 只装文件，不注册服务
set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
APPDIR="${HOME}/.local/opt/ocrsnip"
BINDIR="${HOME}/.local/bin"
UNIT_DIR="${HOME}/.config/systemd/user"
AUTOSTART_DIR="${HOME}/.config/autostart"
NO_SERVICE=0
for arg in "$@"; do
  case "$arg" in
    --no-service) NO_SERVICE=1 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "未知参数: $arg" >&2; exit 2 ;;
  esac
done

echo "==> 安装到 $APPDIR"
mkdir -p "$APPDIR"
# 覆盖式更新：先停服务，避免"正在运行的旧二进制被替换"
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user stop ocrsnip.service 2>/dev/null || true
fi
cp -a "$HERE/." "$APPDIR/"
chmod +x "$APPDIR/ocrsnip"
mkdir -p "$BINDIR"
ln -sfn "$APPDIR/ocrsnip" "$BINDIR/ocrsnip"
echo "==> 命令行入口: $BINDIR/ocrsnip"

if [ "$NO_SERVICE" = "1" ]; then
  echo "==> 跳过服务注册（--no-service）。手动启动: $APPDIR/ocrsnip daemon --ui qt"
  exit 0
fi

mkdir -p "$UNIT_DIR" "$AUTOSTART_DIR"
sed "s|@EXEC@|$APPDIR/ocrsnip|g" "$HERE/ocrsnip.service" > "$UNIT_DIR/ocrsnip.service"
sed -e "s|@EXEC@|$APPDIR/ocrsnip|g" -e "s|@ICON@|$APPDIR/ocrsnip.png|g" \
  "$HERE/ocrsnip.desktop" > "$AUTOSTART_DIR/ocrsnip.desktop"

systemctl --user daemon-reload
systemctl --user enable --now ocrsnip.service
sleep 1
if systemctl --user is-active --quiet ocrsnip.service; then
  echo "==> 服务已启动（开机自启）"
else
  echo "!! 服务没起来，查看日志: journalctl --user -u ocrsnip -n 50" >&2
  exit 1
fi
cat <<TIP

装好了。用法：按 Ctrl+Alt+Q → 鼠标附近弹出面板 → 拖框 → 文字进剪贴板。
  状态/自检 : ocrsnip doctor
  日志      : journalctl --user -u ocrsnip -f
  配置文件  : ~/.config/ocrsnip/config.toml（ocrsnip config 可生成模板）
  卸载      : $APPDIR/uninstall.sh
TIP
