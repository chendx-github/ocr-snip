#!/usr/bin/env bash
# 量一量"按下热键 → 浮层出现"和"松手 → 剪贴板就绪"的端到端延迟。
# 全程在 Xvfb 里跑，不动当前桌面。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/ocrsnip"
TMP="$(mktemp -d)"
trap 'set +e; "$PY" --config "$TMP/c.toml" stop >/dev/null 2>&1; kill "${XVFB_PID:-0}" "${WIN_PID:-0}" 2>/dev/null; rm -rf "$TMP"' EXIT

Xvfb :97 -screen 0 1920x1080x24 -nolisten tcp >"$TMP/xvfb.log" 2>&1 & XVFB_PID=$!
export DISPLAY=:97
for _ in $(seq 1 40); do xdpyinfo >/dev/null 2>&1 && break; sleep 0.1; done

cat >"$TMP/c.toml" <<'CFG'
log_level = "info"
[ui]
toast_ms = 200
CFG

LANG=C.UTF-8 "$ROOT/.venv/bin/python" "$ROOT/scripts/show_text.py" \
  "快捷截屏 OCR 识别测试 E2E-OCR-7788" 100 150 660 200 >/dev/null 2>&1 & WIN_PID=$!
"$PY" --config "$TMP/c.toml" daemon >"$TMP/d.log" 2>&1 &
for _ in $(seq 1 60); do grep -q 预热完成 "$TMP/d.log" && break; sleep 0.25; done
sleep 1

measure() {
  local t0 t1 key_press=$1
  xdotool mousemove 450 300
  t0=$(date +%s%N)
  xdotool key --clearmodifiers ctrl+alt+q
  for _ in $(seq 1 400); do
    if xdotool search --name ocrsnip-overlay >/dev/null 2>&1; then break; fi
    sleep 0.005
  done
  t1=$(date +%s%N)
  echo "  热键 → 浮层可交互: $(( (t1 - t0) / 1000000 )) ms"

  printf 'reset-%s' "$RANDOM" | xclip -selection clipboard -i   # 清空上一次结果，避免误判
  t0=$(date +%s%N)
  xdotool mousemove 102 145
  xdotool mousedown 1
  xdotool mousemove 790 345
  xdotool mouseup 1
  for _ in $(seq 1 600); do
    if xclip -o -selection clipboard 2>/dev/null | grep -q "$key_press"; then break; fi
    sleep 0.005
  done
  t1=$(date +%s%N)
  echo "  松手 → 剪贴板就绪: $(( (t1 - t0) / 1000000 )) ms"
}

echo "== 冷/热各测 3 次"
for i in 1 2 3; do
  echo "-- 第 $i 次"
  measure "E2E-OCR-7788"
  sleep 0.4
done
echo
grep -o "已复制.*" "$TMP/d.log" | tail -3
