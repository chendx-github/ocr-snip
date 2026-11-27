# 本机环境事实（采集于 2026-11-19）

| 项 | 值 |
| --- | --- |
| 发行版 | Linux Mint 22.3 (Zena) |
| 会话 | X11，Cinnamon（`XDG_SESSION_TYPE=x11`，`DISPLAY=:0`） |
| CPU / 内存 | 16 核 / 125 GB |
| GPU | NVIDIA RTX 2060 SUPER 8 GB，驱动 580.178.04（CC 7.5） |
| 显示器 | 采集时 `xrandr` 一度显示 DP-0+HDMI-0 拼成 3840×1080，之后只有 HDMI-0 1920×1080。**不要假设分辨率**，代码统一读 root window 几何 |
| 系统 Python | `/usr/bin/python3` 3.12.3，带 `gi`（GTK 3.24、GdkPixbuf 2、PangoCairo） |
| 其它 Python | miniforge 3.13（默认 `python3`，**没有** gi）→ venv 必须用 `--system-site-packages` + `/usr/bin/python3` |
| 可用工具 | xclip、xdotool、scrot、xwd、zenity、xmessage、Xvfb、tesseract（只有 eng+osd）、uv 0.12 |
| 已装的 GTK | GTK3 **和** GTK4 都有 → 见 gotchas/gi-version-pinning.md |

## 对本项目的直接影响

- 只能依赖 X11 路径（XGrabKey）；Wayland 需换方案。
- venv 必须基于 `/usr/bin/python3`，否则拿不到 `gi`。
- E2E 测试用 Xvfb 跑（`:99`），不打扰正在使用桌面的用户；`scripts/e2e.sh --live` 才走真实桌面。
