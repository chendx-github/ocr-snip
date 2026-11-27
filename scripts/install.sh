#!/usr/bin/env bash
# 一键安装：venv + 可编辑安装 + systemd 用户服务（可选：Cinnamon 自定义快捷键）
#
#   ./scripts/install.sh                 # 装好并启动 daemon
#   ./scripts/install.sh --no-start      # 只安装，不启动
#   ./scripts/install.sh --cinnamon-shortcut   # 额外在 Cinnamon 里绑 Super+Shift+S -> ocrsnip capture
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
PY="$VENV/bin/ocrsnip"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT="$UNIT_DIR/ocrsnip.service"
START=1
CINNAMON=0

for arg in "$@"; do
  case "$arg" in
    --no-start) START=0 ;;
    --cinnamon-shortcut) CINNAMON=1 ;;
    *) echo "未知参数: $arg"; exit 2 ;;
  esac
done

echo "== 1. 系统依赖检查"
[[ -x /usr/bin/python3 ]] || { echo "缺少 /usr/bin/python3"; exit 1; }
/usr/bin/python3 -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk" \
  || { echo "缺少 python3-gi / gir1.2-gtk-3.0（apt install python3-gi gir1.2-gtk-3.0）"; exit 1; }
command -v xclip >/dev/null || echo "  ! 建议安装 xclip（apt install xclip）：否则剪贴板在 daemon 退出后会丢"
command -v xdotool >/dev/null || echo "  ! 建议安装 xdotool（auto_paste 需要）"
[[ "${XDG_SESSION_TYPE:-}" == "x11" ]] || echo "  ! 当前不是 X11 会话：内置全局热键不可用，请用桌面快捷键调用 ocrsnip capture"

echo "== 2. Python 环境"
if [[ ! -x "$VENV/bin/python" ]]; then
  command -v uv >/dev/null || { echo "缺少 uv（curl -LsSf https://astral.sh/uv/install.sh | sh）"; exit 1; }
  # --system-site-packages 是为了复用系统自带的 gi（GTK3）
  uv venv --python /usr/bin/python3 --system-site-packages "$VENV"
fi
uv pip install --python "$VENV/bin/python" -e "$ROOT" >/dev/null
"$PY" version

echo "== 3. 配置文件"
"$PY" config --init || true

echo "== 4. systemd 用户服务"
mkdir -p "$UNIT_DIR"
cat >"$UNIT" <<EOF
[Unit]
Description=ocrsnip：热键框选 OCR 到剪贴板
PartOf=graphical-session.target
StartLimitIntervalSec=0

[Service]
Type=simple
ExecStart=$PY daemon
# 托盘程序要"永远在"：意外退出（包括被误发 stop）都自动拉回
# 真正想停就用 systemctl --user stop ocrsnip
Restart=always
RestartSec=2
# 让服务能连上 X11；DISPLAY 由 install.sh 的 import-environment 带进来
PassEnvironment=DISPLAY XAUTHORITY XDG_RUNTIME_DIR XDG_SESSION_TYPE

[Install]
# Cinnamon/X11 不会激活 graphical-session.target，用 default.target 才能真的登录自启
WantedBy=default.target
EOF
# 关机/登录时 DISPLAY 常常还没进 systemd 环境，daemon 自己会找（见 display_env.py）
mkdir -p "$HOME/.config/autostart"
cat >"$HOME/.config/autostart/ocrsnip.desktop" <<EOF2
[Desktop Entry]
Type=Application
Name=ocrsnip 框选 OCR
Comment=热键 Ctrl+Alt+Q：框选屏幕文字并复制到剪贴板
Exec=systemctl --user start ocrsnip.service
Icon=accessories-character-map
Terminal=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF2
echo "   已写入 $HOME/.config/autostart/ocrsnip.desktop（登录时拉起服务）"

systemctl --user daemon-reload
systemd-analyze --user verify "$UNIT" >/dev/null 2>&1 || true
systemctl --user import-environment DISPLAY XAUTHORITY XDG_RUNTIME_DIR XDG_SESSION_TYPE || true
echo "   已写入 $UNIT"

if [[ "$CINNAMON" == 1 ]]; then
  echo "== 5. Cinnamon 快捷键 Super+Shift+S -> ocrsnip capture"
  BASE=/org/cinnamon/desktop/keybindings/custom-keybindings
  IDX=custom9
  gsettings set org.cinnamon.desktop.keybindings.custom-keybinding:$BASE/$IDX/ name 'ocrsnip 框选 OCR'
  gsettings set org.cinnamon.desktop.keybindings.custom-keybinding:$BASE/$IDX/ command "$PY capture"
  gsettings set org.cinnamon.desktop.keybindings.custom-keybinding:$BASE/$IDX/ binding "['<Super><Shift>s']"
  CURRENT="$(gsettings get org.cinnamon.desktop.keybindings custom-list)"
  case "$CURRENT" in
    *"$IDX"*) ;;
    *) gsettings set org.cinnamon.desktop.keybindings custom-list \
         "$(printf '%s' "$CURRENT" | sed "s/']$/','$IDX']/; s/\[\]/['$IDX']/")" ;;
  esac
  echo "   提示：这样会和 daemon 的 X11 热键（默认 ctrl+alt+q）并存，二者互不影响。"
fi

if [[ "$START" == 1 ]]; then
  echo "== 6. 启动"
  systemctl --user enable --now ocrsnip.service
  sleep 2
  systemctl --user --no-pager status ocrsnip.service | head -12
  echo
  "$PY" doctor || true
else
  echo "已安装（未启动）。启动：systemctl --user enable --now ocrsnip.service"
fi
