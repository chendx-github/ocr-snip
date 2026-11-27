# 更新记录

## 0.3.0

- Linux / Windows 双端，统一"面板选区"交互（`Ctrl+Alt+Q` → 冻结画面面板 → 拖框 → 文字进剪贴板）
- OCR 用 rapidocr + ONNX Runtime（PP-OCRv6 small），`det_limit_type=max` 避免小选区被放大导致延迟翻倍
- Linux：X11 全局热键、systemd 用户服务、桌面自启；安装包三种形态（AppImage / tar.gz / deb）
- Windows：Qt 后端、托盘常驻、`RegisterHotKey`、Win32 多格式剪贴板（文本 + `CF_DIB` + `PNG`）、
  PyInstaller onedir + Inno Setup 安装包
- 面板尺寸可配：`fullscreen` / `panel_width`+`panel_height` / `panel_scale`
- 移除早期"无遮罩 4 条边框"选区（`strips`）：维护成本高、真机上不稳定

## 0.2.0

- 面板选区取代全屏遮罩；只抓面板那一小块，热键到可交互从 42 ms 降到 19 ms
- 修复 `set_resizable(False)` 导致浮层只有 200×200、Esc 取消后 daemon 卡 busy

## 0.1.0

- 首个可用版本：X11 热键 → 框选 → OCR → 剪贴板，systemd 用户服务
