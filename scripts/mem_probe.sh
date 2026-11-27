#!/usr/bin/env bash
# 常驻内存探针：反复"截屏→框选→取消/识别"，看 RSS 会不会爬。
#
#   scripts/mem_probe.sh            # GTK 后端，小选区
#   scripts/mem_probe.sh qt         # Qt 后端（Windows 用的那套）
#   scripts/mem_probe.sh qt --big   # 大选区（最容易把内存顶上去的情况）
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/ocrsnip"
BACKEND="${1:-gtk}"
SIZE="${2:-small}"
DISP=$([[ "$BACKEND" == qt ]] && echo ":94" || echo ":93")

TMP="$(mktemp -d)"
XVFB=""; DAEMON=""; WIN=""
cleanup() {
  set +e
  "$PY" --config "$TMP/c.toml" stop >/dev/null 2>&1
  [ -n "$DAEMON" ] && kill "$DAEMON" 2>/dev/null
  [ -n "$WIN" ] && kill "$WIN" 2>/dev/null
  [ -n "$XVFB" ] && kill "$XVFB" 2>/dev/null
  rm -rf "$TMP"
}
trap cleanup EXIT

Xvfb "$DISP" -screen 0 1920x1080x24 -nolisten tcp >/dev/null 2>&1 & XVFB=$!
sleep 1.2
export DISPLAY="$DISP"
printf 'log_level = "info"\n' >"$TMP/c.toml"

LANG=C.UTF-8 "$ROOT/.venv/bin/python" "$ROOT/scripts/show_text.py" \
  "内存探针 OCR 1234 内存探针" 100 150 700 300 >/dev/null 2>&1 & WIN=$!

"$PY" --config "$TMP/c.toml" --ui "$BACKEND" daemon >"$TMP/d.log" 2>&1 & DAEMON=$!
for _ in $(seq 1 100); do
  "$PY" --config "$TMP/c.toml" status >/dev/null 2>&1 && break
  sleep 0.2
done
sleep 1.5

PID=$("$PY" --config "$TMP/c.toml" status 2>/dev/null | sed -n 's/.*"pid": \([0-9]*\).*/\1/p' | head -1)
if [ -z "$PID" ]; then echo "拿不到 daemon pid"; tail -5 "$TMP/d.log"; exit 1; fi

rss() { awk '/VmRSS/{print int($2/1024)}' "/proc/$1/status" 2>/dev/null; }
echo "[$BACKEND/$SIZE] 起始 RSS=$(rss "$PID") MB (pid=$PID)"

# 选区：小=框住文字，大=接近面板满幅
if [ "$SIZE" = "--big" ]; then SX=40; SY=40; EX=920; EY=520; else SX=120; SY=170; EX=700; EY=300; fi

for i in $(seq 1 "${N:-8}"); do
  xdotool mousemove 500 400
  "$PY" --config "$TMP/c.toml" capture >/dev/null 2>&1
  sleep 0.5
  if xdotool search --name ocrsnip-overlay >/dev/null 2>&1; then
    xdotool mousemove "$SX" "$SY"
    xdotool mousedown 1
    xdotool mousemove "$EX" "$EY"
    xdotool mouseup 1
  fi
  sleep 0.9
  echo "[$BACKEND/$SIZE] 第 $i 次后 RSS=$(rss "$PID") MB"
done

echo "--- 最后几次识别耗时 ---"
grep -oE "已复制 [0-9]+ 字（[0-9]+ 行，[0-9]+ ms）" "$TMP/d.log" | tail -3
