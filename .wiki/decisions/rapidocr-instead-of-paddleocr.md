# 为什么用 RapidOCR + ONNX Runtime，而不是本机已有的 PaddleOCR

日期：2026-11-19。当时 ocrsnip 版本 0.1.0（初始提交），无更早历史。

## 背景

同机上 `~/code/py/project/PaddleOCR/.venv-ocr` 已经有可用的 PaddleOCR（paddlepaddle 3.2.0 CPU 版、paddlex 3.6.1、PP-OCRv5 server det+rec 已缓存 176 MB），
而 `~/code/py/project/PaddleOCR` 本身是完整仓库。

## 实测对比（同一台机器，2026-11-19，16 核，CPU 推理）

| 方案 | 单页文档耗时 | 峰值内存 | 小选区 620×150 |
| --- | --- | --- | --- |
| PaddleOCR + paddlepaddle 3.2.0 CPU，PP-OCRv5 **server** | 4.55–4.81 s/页（72 行文本） | 2.1 GB | 未测（同量级） |
| rapidocr 3.10 + onnxruntime，PP-OCRv6 **small**，默认参数 | — | ~200 MB 常驻 | 780 ms |
| 同上，`Det.limit_type=max, limit_side_len=1024` | — | ~200 MB 常驻 | **83 ms** |

结论：热键工具的手感由"松手到剪贴板"决定，50 倍差距不可接受，选 rapidocr。
代价：PaddleOCR 的 server 模型精度更高（尤其小字、复杂版面），需要时可以在配置里换模型，但目前没有必要。

## 那个决定性的配置

rapidocr 默认 `Det.limit_type = "min"`、`limit_side_len = 736`：**短边不足 736 就放大**。
屏幕选区的字本来就已经是原生分辨率，放大不但没用，还把 620×150 变成 3033×736 的检测输入 —— 单次检测 560 ms。

改成 `limit_type = "max"` 后只在大选区上缩小，620×150 原样送入，检测降到 ~60 ms。

防线：`tests/test_ocr.py::test_small_crop_stays_fast` 会在小图上跑 3 次并要求平均 < 400 ms。
如果有人把它改回 `min`，这个测试会立刻红。

## 线程数

同一测试条件下：1 线程 1453 ms / 4 线程 525 ms / 8 线程 447 ms / 16 线程 678 ms（1200×520 图）。
超线程开太多反而更慢，默认取 8。
