#!/usr/bin/env bash
# 端到端自测：在屏幕上放一段已知文本 → 触发热键 → 拖选 → 核对剪贴板。
#
# 用法:
#   scripts/e2e.sh                 # GTK 后端，在独立 Xvfb 虚拟屏里跑，不打扰当前桌面
#   scripts/e2e.sh --live          # GTK 后端，在当前桌面上跑（占用屏幕 1-2 秒）
#   scripts/e2e.sh --qt            # Qt 后端（Windows 用的那套）
#   scripts/e2e.sh --qt --live     # Qt 后端 + 当前桌面
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/ocrsnip"
MODE="xvfb"
BACKEND="gtk"
for arg in "$@"; do
  case "$arg" in
    --live) MODE="live" ;;
    --qt) BACKEND="qt" ;;
    --gtk) BACKEND="gtk" ;;
    *) echo "未知参数: $arg"; exit 2 ;;
  esac
done

TMP="$(mktemp -d)"
EXPECT="E2E-OCR-7788"
CONF="$TMP/config.toml"
LOG="$TMP/daemon.log"
XVFB_PID=""
WIN_PID=""

cleanup() {
  set +e
  "$PY" --config "$CONF" stop >/dev/null 2>&1
  [ -n "$WIN_PID" ] && kill "$WIN_PID" 2>/dev/null
  [ -n "${DAEMON_PID:-}" ] && kill "$DAEMON_PID" 2>/dev/null
  [ -n "$XVFB_PID" ] && kill "$XVFB_PID" 2>/dev/null
  rm -rf "$TMP"
}
trap cleanup EXIT

if [[ "$MODE" == "xvfb" ]]; then
  command -v Xvfb >/dev/null || { echo "没有 Xvfb，改用 --live"; exit 2; }
  DISPLAY_NUM=":99"
  Xvfb "$DISPLAY_NUM" -screen 0 1920x1080x24 -nolisten tcp >"$TMP/xvfb.log" 2>&1 &
  XVFB_PID=$!
  export DISPLAY="$DISPLAY_NUM"
  for _ in $(seq 1 40); do xdpyinfo >/dev/null 2>&1 && break; sleep 0.1; done
  echo "== 0. backend=$BACKEND 使用 Xvfb $DISPLAY (1920x1080)"
else
  echo "== 0. backend=$BACKEND 使用当前桌面 $DISPLAY"
fi

cat >"$CONF" <<EOF
hotkey = "ctrl+alt+q"
log_level = "info"

[ui]
overlay_timeout_sec = 10.0
toast_ms = 400

[ocr]
threads = 8
EOF

echo "== 1. 启动 daemon"
"$PY" --config "$CONF" --ui "$BACKEND" daemon >"$LOG" 2>&1 &
DAEMON_PID=$!
STATUS_OK=0
for _ in $(seq 1 80); do
  if "$PY" --config "$CONF" status >/dev/null 2>&1; then STATUS_OK=1; break; fi
  sleep 0.25
done
[ "$STATUS_OK" = 1 ] || { echo "daemon 的 status 不通（IPC 有问题）"; tail -20 "$LOG"; exit 1; }
for _ in $(seq 1 80); do
  grep -q "热键已注册" "$LOG" && break
  sleep 0.25
done
grep -q "热键已注册" "$LOG" || { echo "热键注册失败"; tail -20 "$LOG"; exit 1; }
for _ in $(seq 1 80); do
  grep -q "预热完成" "$LOG" && break
  sleep 0.25
done
echo "   $(grep -o '热键已注册.*' "$LOG")"
echo "   $(grep -o 'OCR 引擎预热完成.*' "$LOG" || echo '预热未完成（第一次识别会慢）')"

echo "== 2. 屏幕上放一段已知文本 ($EXPECT)"
LANG=C.UTF-8 LC_ALL=C.UTF-8 "$ROOT/.venv/bin/python" "$ROOT/scripts/show_text.py" \
  "快捷截屏 OCR 识别测试 $EXPECT" 100 150 660 120 >/dev/null 2>&1 &
WIN_PID=$!
sleep 1.8
WIN_ID=$(xdotool search --name show_text.py | head -1 || true)
[ -n "$WIN_ID" ] || echo "   (没有窗口标题可查，按固定坐标框选)"
sleep 0.3

echo "== 3. 触发热键并框选"
xdotool mousemove 450 300
sleep 0.2
xdotool key --clearmodifiers ctrl+alt+q
sleep 0.6
xdotool mousemove 102 145
xdotool mousedown 1
xdotool mousemove 790 345
sleep 0.2
xdotool mouseup 1
sleep 1.5

echo "== 4. 校验剪贴板"
TEXT="$(xclip -o -selection clipboard 2>/dev/null || true)"
printf '   剪贴板内容: %s\n' "${TEXT:-<空>}"
case "$TEXT" in
  *"$EXPECT"*) echo "PASS: 剪贴板里出现了 $EXPECT" ;;
  *) echo "FAIL: 剪贴板内容不符合预期"; tail -20 "$LOG"; exit 1 ;;
esac

echo "== 5. 取消后必须还能再次触发（回归：Esc 曾经把 daemon 卡成 busy）"
xdotool mousemove 450 300
sleep 0.2
xdotool key --clearmodifiers ctrl+alt+q
sleep 0.6
xdotool key Escape
sleep 0.6
xdotool key --clearmodifiers ctrl+alt+q
sleep 0.8
if "$PY" --config "$CONF" status | grep -q '"busy": true'; then
  echo "   PASS: 取消后仍可再次唤出面板"
else
  echo "   FAIL: 取消后再按热键没有反应"
  tail -10 "$LOG"
  exit 1
fi
xdotool key Escape
sleep 0.5

echo "== 6. daemon 统计"
"$PY" --config "$CONF" status | grep -A8 '"last"'
