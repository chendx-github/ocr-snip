# ocrsnip

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey.svg)](#安装linux)
[![build-windows](https://github.com/chendx/ocr-snip/actions/workflows/build-windows.yml/badge.svg)](https://github.com/chendx/ocr-snip/actions/workflows/build-windows.yml)

按下热键 → 框选一块屏幕 → 选区里的文字直接进剪贴板。**为延迟而做，不为功能而做。**

- 热键到面板可交互：**~19–25 ms**（只抓面板那一小块，6 ms）
- 松手到剪贴板就绪：**~60–130 ms**（688×200 选区，26 个字，8 线程 CPU）
- 常驻内存：**~120 MB**（systemd 统计 122 MB；模型常驻，所以每次截屏只花"抓屏 + 推理"的时间）
- 磁盘：venv 约 380 MB（含 onnxruntime 与自带模型），模型不用下载

## Windows

有独立的 Windows 版（Qt 后端 + 托盘 + 安装包），见 **[windows/README-Windows.md](windows/README-Windows.md)**：

```bat
windows\install.bat        :: 已有 Python 3.10+：一键装好并启动
windows\build.bat         :: 打包出绿色版 + ocrsnip-setup.exe（需 Inno Setup 6）
```

## 安装（Linux）

```bash
git clone https://github.com/chendx/ocr-snip.git && cd ocr-snip
./scripts/install.sh            # venv + 依赖 + systemd 用户服务，并立即启动
./scripts/install.sh --cinnamon-shortcut   # 另在 Cinnamon 绑 Super+Shift+S -> ocrsnip capture
```

依赖（Linux Mint / Ubuntu 系）：

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 xclip xdotool
```

## 用法

按热键 → **以鼠标为中心弹出冻结画面面板**（约 1/4 屏，只抓这一小块，比抓全屏快）→ 在面板里拖框 →
框里的文字进剪贴板。平台差异只在实现细节（Linux 用 GTK，Windows 用 Qt），交互一致。

> 曾经的「无遮罩 4 条边框」选区（`strips`）已于 2026-11-25 移除：面板方案在两端都稳定，
> strips 需要低层钩子/override-redirect 窗口，维护成本和不确定性都更高。
> 见 `.wiki/decisions/panel-only-after-removing-strips.md`。

| 操作 | 说明 |
| --- | --- |
| `Ctrl+Alt+Q` | 默认热键（可在配置里改）；面板出现在鼠标周围 |
| 拖动 | 框选区域；松手即识别并复制 |
| `Esc` / 右键 | 取消 |
| `ocrsnip capture` | 手动触发一次（也能绑到桌面快捷键 / 其它窗口管理器） |
| `ocrsnip status` | daemon 状态、上次耗时、内存占用 |
| `ocrsnip doctor` | 自检：热键能否抓取、抓屏耗时、OCR 预热耗时 |
| `ocrsnip stop` | 停一下（服务会自动重启）；要真停用 `systemctl --user stop ocrsnip` |

识别成功后左下角会弹一个"已复制 N 字 · X ms"的提示条，不抢焦点。

## 配置

`ocrsnip config --init` 会写入 `~/.config/ocrsnip/config.toml`：

```toml
hotkey = "ctrl+alt+q"     # 支持 ctrl/alt/shift/super + 单键；改完 systemctl --user restart ocrsnip
[ocr]
det_limit_side_len = 1024 # 选区最长边超过它才缩小；这是最重要的性能开关
threads = 8
rec_batch_num = 16
use_cls = false           # 角度分类器，截图基本是正向文本，关掉省时间
min_score = 0.5
[post]
mode = "smart"            # lines | smart | paragraph
strip_cjk_spaces = true
[clipboard]
also_primary = false
auto_paste = false        # true 则复制后自动 Ctrl+V
copy_image = false        # true 则剪贴板只放图片（默认同时提供文字与 image/png 两个 target）
[ui]
fullscreen = false        # true = 面板占满鼠标所在显示器（整屏冻结画面）
panel_width = 0           # 显式面板宽（像素）；0 = 按 panel_scale
panel_height = 0          # 显式面板高（像素）；0 = 按 panel_scale
panel_scale = 0.5         # 面板占所在显示器边长比例
panel_min_w = 360         # 面板最小尺寸
panel_min_h = 260
overlay_timeout_sec = 45  # 兜底：忘了取消也不会卡住屏幕
```

`post.mode` 决定换行怎么处理：

- `lines`：每个识别行都保留（代码、菜单、表格）
- `smart`（默认）：只把明显是自动换行的长行接回去，短行/列表/编号保持换行
- `paragraph`：全部拼成一段

## 为什么用 RapidOCR 而不是本机已装的 PaddleOCR

同机上 `.venv-ocr` 里的 PaddleOCR（PP-OCRv5 server + paddle CPU）单页要 **4.6 s**、峰值内存 **2.1 GB**；rapidocr（PP-OCRv6 small，ONNX Runtime）在 620×150 的选区上 **~90 ms**、常驻 200 MB。热键工具靠的是"手感"，这一项差距是 50 倍。

一个重要细节：rapidocr 默认 `Det.limit_type=min, limit_side_len=736`，会把小选区**放大**到短边 736（620×150 → 3033×736），单次检测就 560 ms。改成 `max/1024` 后同样的图 **83 ms**。这是本项目最关键的一行配置，改动前请先看 `tests/test_ocr.py::test_small_crop_stays_fast`。

## 测试

```bash
.venv/bin/python -m pytest -q          # 20 个用例，约 1 秒
./scripts/e2e.sh                       # 端到端：Xvfb 里造文本 → 热键 → 拖选 → 校验剪贴板
./scripts/e2e.sh --live                # 同上，但在当前桌面上跑（会占用屏幕 1-2 秒）
./scripts/bench.sh                     # 量热键→浮层、松手→剪贴板的延迟
```

## 已知限制

- 只支持 **X11**（内置全局热键用 XGrabKey）。Wayland 下请用桌面自定义快捷键调用 `ocrsnip capture`，或改用 `grim`+`slurp` 方案。
- 同一组合键在同一 X 会话里只能被一个程序抓取；冲突时 `ocrsnip doctor` 会报出来。
- 选区超过 `det_limit_side_len` 会被等比缩小，太小的字可能识别不到；把该值调大会变慢。
- 剪贴板优先写 `xclip`（fork 后继续托管选区）。没有 xclip 时退回 GTK，daemon 退出后内容会丢。

## 卸载

```bash
systemctl --user disable --now ocrsnip
rm -f ~/.config/systemd/user/ocrsnip.service
rm -rf .venv ~/.config/ocrsnip
```
