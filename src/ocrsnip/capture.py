"""整屏抓取（X11 / GTK），并支持零拷贝裁剪出选区。

抓取发生在窗口显示**之前**，所以选区内容里不会混进我们自己的遮罩层。
"""

from __future__ import annotations

from dataclasses import dataclass

from . import gi_setup  # noqa: F401  (必须先于其它 gi 导入)
import numpy as np
from gi.repository import Gdk, GdkPixbuf


def screen_geometry() -> tuple[int, int]:
    """虚拟屏尺寸（多显示器时是并集）。"""
    root = Gdk.get_default_root_window()
    return root.get_width(), root.get_height()


def monitors() -> list[tuple[int, int, int, int]]:
    """各显示器在虚拟屏中的矩形，用于提示与调试。"""
    display = Gdk.Display.get_default()
    out = []
    for index in range(display.get_n_monitors()):
        geo = display.get_monitor(index).get_geometry()
        out.append((geo.x, geo.y, geo.width, geo.height))
    return out


@dataclass
class ScreenShot:
    pixbuf: GdkPixbuf.Pixbuf
    width: int
    height: int
    origin_x: int = 0   # 这张图左上角在屏幕上的位置
    origin_y: int = 0

    def bgr(self, x: int, y: int, w: int, h: int) -> np.ndarray:
        """裁出选区并转成 rapidocr 需要的 BGR ndarray。"""
        x = max(0, min(x, self.width - 1))
        y = max(0, min(y, self.height - 1))
        w = max(1, min(w, self.width - x))
        h = max(1, min(h, self.height - y))

        channels = self.pixbuf.get_n_channels()
        rowstride = self.pixbuf.get_rowstride()
        data = self.pixbuf.get_pixels()
        buf = np.frombuffer(data, dtype=np.uint8).reshape(self.height, rowstride)
        view = buf[y : y + h, x * channels : (x + w) * channels]
        if channels >= 3:
            rgb = view.reshape(h, w, channels)[:, :, :3]
            return np.ascontiguousarray(rgb[:, :, ::-1])  # RGB -> BGR
        gray = view.reshape(h, w)
        return np.ascontiguousarray(np.repeat(gray[:, :, None], 3, axis=2))


def grab() -> ScreenShot:
    """整个虚拟屏。"""
    root = Gdk.get_default_root_window()
    width, height = root.get_width(), root.get_height()
    return _grab(0, 0, width, height)


def grab_region(x: int, y: int, width: int, height: int) -> ScreenShot:
    """只抓一小块（面板模式用），比抓全屏快好几倍。"""
    return _grab(x, y, width, height)


def _grab(x: int, y: int, width: int, height: int) -> ScreenShot:
    root = Gdk.get_default_root_window()
    width = max(1, min(width, root.get_width() - max(0, x)))
    height = max(1, min(height, root.get_height() - max(0, y)))
    pixbuf = Gdk.pixbuf_get_from_window(root, max(0, x), max(0, y), width, height)
    if pixbuf is None:
        raise RuntimeError("抓屏失败：Gdk.pixbuf_get_from_window 返回 None")
    return ScreenShot(
        pixbuf=pixbuf, width=width, height=height, origin_x=max(0, x), origin_y=max(0, y)
    )


def pointer_position() -> tuple[int, int]:
    """当前鼠标位置（屏幕坐标）。"""
    display = Gdk.Display.get_default()
    seat = display.get_default_seat()
    _screen, x, y = seat.get_pointer().get_position()
    return int(x), int(y)


def monitor_at(x: int, y: int) -> tuple[int, int, int, int]:
    """鼠标所在的显示器矩形。"""
    display = Gdk.Display.get_default()
    monitor = display.get_monitor_at_point(x, y) or display.get_primary_monitor()
    geo = monitor.get_geometry()
    return geo.x, geo.y, geo.width, geo.height
