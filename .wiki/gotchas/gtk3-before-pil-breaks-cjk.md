# 先 import Gdk 3.0 再 import PIL → PIL 中文渲染静默坏掉

日期：2026-11-19，Pillow（rapidocr 依赖的版本）+ GTK3 3.24，Linux Mint 22.3。

## 现象

同一个进程里：

- 先 `from PIL import ...` 再 import `gi`/`Gdk`：中文正常（一行 24px 文本约 1795 个暗像素）。
- 先 `import gi; gi.require_version("Gdk","3.0"); from gi.repository import Gdk` 再 import PIL：
  `ImageDraw.text()` 只画出零碎笔画（同样一行只有 190 个暗像素）。
- 同时会出现莫名其妙的 `DecompressionBombWarning: Image size (116550408 pixels)`。

## 影响面

- **只影响 PIL 画字**，不影响本项目运行时代码（ocrsnip 从不用 PIL 渲染文字）。
- 受影响的是测试：`tests/test_ocr.py` 原本用 PIL 现场渲染中文样例，pytest 收集测试模块时
  `test_capture.py` 先 import 了 Gdk，于是 `test_ocr.py` 渲染出空白图，OCR 自然识别不到。

## 处理

测试样例改成**预渲染 PNG**（`tests/fixtures/sample_zh.png`），测试只 `Image.open` 不画字。
没有在代码里做 import 顺序 hack —— 因为生产路径不依赖它，而顺序 hack 会变成隐式约束。
