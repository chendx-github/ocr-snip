"""ScreenShot.bgr 的裁剪/通道顺序测试（用 GdkPixbuf，不需要真实显示器）。"""

import numpy as np
import pytest

gi = pytest.importorskip("gi")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GLib, GdkPixbuf  # noqa: E402

from ocrsnip.capture import ScreenShot  # noqa: E402


def _pixbuf(width: int, height: int, rgb: tuple[int, int, int]) -> GdkPixbuf.Pixbuf:
    # 必须用 new_from_bytes：new_from_data 会保留裸指针，临时 bytes 被回收后会踩内存
    pixels = bytes(rgb) * (width * height)
    return GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(pixels),
        GdkPixbuf.Colorspace.RGB,
        False,
        8,
        width,
        height,
        width * 3,
    )


def test_bgr_converts_rgb_and_crops():
    pixbuf = _pixbuf(8, 6, (10, 20, 30))
    shot = ScreenShot(pixbuf=pixbuf, width=8, height=6)
    crop = shot.bgr(2, 1, 3, 2)
    assert crop.shape == (2, 3, 3)
    assert tuple(crop[0, 0]) == (30, 20, 10)  # R,G,B -> B,G,R


def test_bgr_clamps_out_of_range_rect():
    pixbuf = _pixbuf(10, 10, (1, 2, 3))
    shot = ScreenShot(pixbuf=pixbuf, width=10, height=10)
    crop = shot.bgr(8, 8, 100, 100)
    assert crop.shape == (2, 2, 3)

    crop = shot.bgr(-5, -5, 4, 4)
    assert crop.shape[0] >= 1 and crop.shape[1] >= 1
