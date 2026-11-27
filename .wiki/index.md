# ocrsnip wiki

项目内操作知识库。所有结论都带日期；涉及代码的，注明当时的版本/提交。

## Decisions
- [decisions/panel-only-after-removing-strips.md](decisions/panel-only-after-removing-strips.md) — 2026-11-25：移除 strips，只保留面板选区
- [decisions/windows-no-overlay-winrect.md](decisions/windows-no-overlay-winrect.md) — 2026-11-24：Windows 无遮罩选区（低层钩子 + 4 条边框），为何不用 layered 全屏窗
- [decisions/no-overlay-strips-selection.md](decisions/no-overlay-strips-selection.md) — 2026-11-21：X11 改为「无遮罩 + 4 条边框窗口」选区（本机无合成器）
- [decisions/rapidocr-instead-of-paddleocr.md](decisions/rapidocr-instead-of-paddleocr.md) — 为什么用 RapidOCR+ONNX 而不是本机已有的 PaddleOCR；以及那个决定 5 倍延迟的 `Det.limit_type` 开关
- [decisions/panel-around-cursor.md](decisions/panel-around-cursor.md) — 2026-11-19：从"整屏浮层"改成"以鼠标为中心的 1/4 屏面板"

## Notes
- [notes/windows-build-2026-11-21.md](notes/windows-build-2026-11-21.md) — Windows 实机构建与验证结果、产物与耗时
- [notes/autostart.md](notes/autostart.md) — 自启动：default.target + XDG autostart + 自身找 DISPLAY（2026-11-19 验证）
- [notes/latency-budget.md](notes/latency-budget.md) — 实测延迟分解与各项优化收益（2026-11-19）
- [notes/environment.md](notes/environment.md) — 本机环境事实：X11/Cinnamon、显示器、可用工具

## Gotchas
- [gotchas/powershell-51-needs-utf8-bom.md](gotchas/powershell-51-needs-utf8-bom.md) — PS5.1 读无 BOM 的 UTF-8 .ps1 会乱码报错
- [gotchas/windows-ssh-quirks.md](gotchas/windows-ssh-quirks.md) — SSH 驱动 Windows：子进程被回收、GUI 看不见、编码坑、winget/Inno
- [gotchas/xdotool-escape-hits-focused-window.md](gotchas/xdotool-escape-hits-focused-window.md) — xdotool 发 Esc 会打断正在跑的 pi 终端
- [gotchas/cancel-left-daemon-busy.md](gotchas/cancel-left-daemon-busy.md) — Esc 取消没有通知 daemon，busy 卡死导致热键静默失效
- [gotchas/gtk3-set-resizable-blocks-resize.md](gotchas/gtk3-set-resizable-blocks-resize.md) — `set_resizable(False)` 让 resize 失效，浮层只剩左上角 200×200
- [gotchas/gtk3-before-pil-breaks-cjk.md](gotchas/gtk3-before-pil-breaks-cjk.md) — 先 import Gdk 3.0 再 import PIL，PIL 中文渲染会坏
- [gotchas/gi-version-pinning.md](gotchas/gi-version-pinning.md) — 本机同时装 GTK3/GTK4，必须显式 require_version
- [gotchas/pkill-matches-own-shell.md](gotchas/pkill-matches-own-shell.md) — `pkill -f "ocrsnip --config ..."` 会杀掉自己那条 bash
