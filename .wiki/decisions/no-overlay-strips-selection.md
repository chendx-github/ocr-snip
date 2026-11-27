> **已被取代（2026-11-25）**：strips 选区已移除，只保留面板，见 [panel-only-after-removing-strips.md](panel-only-after-removing-strips.md)。本页仅作历史记录。

# 选区内不加任何遮罩：4 条边框窗口方案（2026-11-21）

## 背景

本机 Cinnamon/Muffin **没有启用合成器**：`xprop -root _NET_WM_CM_S0` →
`no such atom on any window`。ARGB 透明窗口不会被混合，所以"全屏透明窗 + 透明底"
这条常见路线在这台机器上做不出"只有框有颜色、其余全透明"。

方案来自同机 `rectshot` 项目（`~/app/rectshot`，已实测通过），本次接进 ocrsnip 作为
X11 默认选区方式（`ui.selection = "strips"`）。

## 做法

1. 按热键后**不创建任何窗口**，只 grab pointer/keyboard（光标变十字）。
2. 左键按下时 `XGetImage(0,0,W,H,ZPixmap)` 冻结整屏 → 唯一可信图像源。
   python-xlib 的回复里**没有** `bits_per_pixel`，用 `root_depth > 16` 判断 → 4 字节 BGRX。
3. 拖动只创建 **4 个 override-redirect 窄窗**（上/下/左/右），摆在选区**外侧**：
   除这几条像素外屏幕上没有本进程窗口，"其余区域真的不存在"，天然 100% 透明。
   `override_redirect` 必须在 `CreateWindow` 时设置，事后 `XChangeWindowAttributes` 改不了。
4. 松开 → 销毁边框 → 从冻结帧按 root 坐标 1:1 裁剪 → OCR → 剪贴板。
   边框是冻结之后才画的，所以裁剪图绝不含框线。
5. Esc / 右键 / 中键取消；< 3px 视为误触；超时（`ui.overlay_timeout_sec`）自动取消。

## 验收（scripts/accept_strips.sh，2026-11-21 全绿）

| 检查 | 结果 |
| --- | --- |
| 无合成器（`_NET_WM_CM_S0` 不存在）下可用 | PASS |
| 拖动中框内/框外同底色像素逐点一致（≤2/255） | PASS，实测最大通道差 **0** |
| 裁剪图最外圈不含边框色（#0A84FF） | PASS |
| 选区尺寸 = 实际像素（300x200） | PASS |
| 跨屏（x 1800→2100）尺寸 = 实际像素（300x100） | PASS |
| Esc 取消：无残留窗口 + 指针抓取已释放 | PASS |
| 真实桌面拖动中截图（/tmp/live-strips-mid.png）目视 | 只有一圈细蓝框，桌面无变暗 |
| 剪贴板同时提供 text + image/png（10 项验收的第 3.5 项） | PASS，TARGETS 列出 7 个 |
| last.png 固定留存 | PASS（9434 字节） |

## 代价 / 已知

- 热键按下后**没有任何视觉反馈**（只有光标变十字），不像面板模式那样弹出来；
  这是"零遮罩"的固有代价。
- 无合成器 ⇒ 边框只能是实色，做不了半透明边框（开 picom 后可以加 opacity）。
- 仅 X11；Windows 侧走 Qt 的 panel 模式（那边有 DWM，透明不受影响）。

## 2026-11-21 晚：抽成独立包 x11rect + 多格式剪贴板

- 取景逻辑挪到独立包 `../x11rect`（`select_region() → FrozenFrame + rect`），ocrsnip 用
  `[tool.uv.sources]` 的 path 依赖引用，避免两份源码分叉；Windows 侧不依赖它（marker 排除）。
- 剪贴板改为自己当 owner：一个 selection 上同时 advertise
  `TARGETS / TIMESTAMP / UTF8_STRING / text/plain;charset=utf-8 / text/plain / STRING / image/png`，
  粘到编辑器出文字、粘到聊天出图。xclip 一次只能一个 target，做不到这点。
  实现用**独立子进程**（不是 fork：本项目多线程，fork 后易死锁）。
- 每次选区固定留一份 `~/.local/state/ocrsnip/last.png`，不再"3 秒后删临时文件"。
- 修了三个真 bug：`origin=(0,0)` 被当真值判断导致 motion/release 分支失灵；
  bpp=2（16 位色深）时 `to_pil` 按 3 字节错读；TARGETS/TIMESTAMP 必须 format=32
  （写成 format=8 时 xclip 只能读出前三个 target）。
