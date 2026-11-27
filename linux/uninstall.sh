#!/usr/bin/env bash
# 卸载 ocrsnip（Linux，无需 root）：停服务、删服务/自启/程序目录，保留配置。
set -uo pipefail
APPDIR="${HOME}/.local/opt/ocrsnip"
BINDIR="${HOME}/.local/bin"
UNIT_DIR="${HOME}/.config/systemd/user"
AUTOSTART_DIR="${HOME}/.config/autostart"

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user disable --now ocrsnip.service 2>/dev/null || true
fi
rm -f "$UNIT_DIR/ocrsnip.service" "$AUTOSTART_DIR/ocrsnip.desktop"
command -v systemctl >/dev/null 2>&1 && systemctl --user daemon-reload
[ -L "$BINDIR/ocrsnip" ] && rm -f "$BINDIR/ocrsnip"
rm -rf "$APPDIR"
echo "已卸载。配置与日志保留在 ~/.config/ocrsnip 和 ~/.local/state/ocrsnip（想彻底清掉可自行删除）。"
