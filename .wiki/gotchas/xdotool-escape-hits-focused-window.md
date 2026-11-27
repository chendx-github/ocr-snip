# 用 xdotool 发 Esc 会把正在跑的 pi 终端打断

日期：2026-11-19，踩了两次（两次都表现为整条命令 "Command aborted"）。

## 原因

`xdotool key Escape` 是 XTEST 合成事件，走正常事件分发：如果屏幕上**没有**我们的浮层
（因此没有 seat grab），Esc 就落到当前焦点窗口 —— 通常是跑着 pi 的终端，于是 pi 收到 Esc，
把正在执行的工具调用打断。

## 做法

只在**确认浮层已经出现**之后再发 Esc：

```bash
W=$(xdotool search --name ocrsnip-overlay 2>/dev/null | head -1)
if [ -n "$W" ]; then xdotool key Escape; fi
```

因为浮层出现时会 `Gdk.Seat.grab()`，此时 Esc 一定进浮层，不会漏到终端。
更稳的替代：`ocrsnip stop` 后重启服务（不涉及按键）。
