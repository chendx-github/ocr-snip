"""不依赖 ocrsnip 的复用示例：拿到 (冻结帧, 选区) 后自己裁剪。

python examples/select_region_demo.py            # 框选后打印尺寸并存 out.png

只需把 src/ocrsnip/x11_rect.py 拷走（依赖 python-xlib + numpy，可选 PIL 存图）。
"""

from __future__ import annotations

import sys

from ocrsnip.x11_rect import select_region

picked = select_region(color="#0A84FF", thickness=2, timeout=45)
if picked is None:
    print("已取消")
    sys.exit(0)

frame, (x0, y0, x1, y1) = picked
print(f"选区 {x1 - x0}x{y1 - y0} @ ({x0},{y0})，冻结帧 {frame.width}x{frame.height} bpp={frame.bpp}")

bgr = frame.crop_bgr(x0, y0, x1, y1)
print("BGR ndarray:", bgr.shape, bgr.dtype)   # 直接喂 rapidocr / cv2

image = frame.to_pil(x0, y0, x1, y1)          # 或 PIL.Image
image.save("out.png")
print("已保存 out.png")
