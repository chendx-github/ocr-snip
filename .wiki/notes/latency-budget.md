# 延迟预算与实测（2026-11-19，Xvfb 1920×1080，16 核）

ocrsnip 0.1.0。`scripts/bench.sh` 的原始输出：

```
热键 → 浮层可交互: 42 ms / 42 ms / 42 ms
松手 → 剪贴板就绪: 177 ms / 87 ms / 103 ms   (688×200 选区，26 字，单行)
daemon 记录的 OCR 耗时: 153 ms / 60 ms / 78 ms
```

## 分解

| 阶段 | 耗时 | 说明 |
| --- | --- | --- |
| 抓全屏（Gdk root window → pixbuf） | 12–25 ms | 1920×1080，8 MB 拷贝 |
| 建窗 + 首次 draw + present | ~15 ms | 窗口不透明，直接画抓到的 pixbuf |
| 模型推理（小选区） | 60–110 ms | det 约 40–60 ms，rec 约 20–50 ms |
| 写剪贴板（xclip） | 5–10 ms | fork 后由 xclip 托管选区 |
| Toast 显示 | 不计入关键路径 | 失败也不影响剪贴板 |

## 已经做过的优化

1. `Det.limit_type=max`（避免小选区被放大）→ 检测 560 ms → 60 ms。
   见 decisions/rapidocr-instead-of-paddleocr.md。
2. 关掉角度分类器（`use_cls=false`）→ 省 10–20 ms。
3. 模型常驻：daemon 启动后 560 ms 预热一次，之后每次截屏不再加载。
4. 拖动时只重绘脏矩形（`queue_draw_area`），全屏 pixbuf 不会每帧重画。
5. 剪贴板走 xclip 而不是 GTK：不受 daemon 生命周期影响，也免了 GTK 主循环往返。

## 还没做的

- 浮层可以预先创建（隐藏）再 show，理论上再省 10 ms 左右，但会让"冻结画面"的抓屏时机变复杂。
- 选区内文字极多（数百行）时 rec 会分多个 batch，延迟会涨到 300 ms+；`rec_batch_num=16` 已覆盖常见段落。
