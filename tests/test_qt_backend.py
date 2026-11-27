"""Qt 后端中与平台无关的纯逻辑：坐标换算 + QImage→BGR。"""

import numpy as np
import pytest

from ocrsnip.geometry import panel_physical

QtGui = pytest.importorskip("PySide6.QtGui")
QImage = QtGui.QImage
QColor = QtGui.QColor


def test_panel_physical_at_dpr_1():
    assert panel_physical((100, 200, 300, 400), (0, 0), 1.0) == (100, 200, 300, 400)


def test_panel_physical_scales_by_dpr():
    # 150% 缩放：逻辑 320x270 的选区 → 物理 480x405
    assert panel_physical((0, 0, 320, 270), (0, 0), 1.5) == (0, 0, 480, 405)


def test_panel_physical_subtracts_screen_origin():
    # 第二块屏（逻辑原点 1920,0）上的面板
    assert panel_physical((2400, 100, 960, 540), (1920, 0), 1.0) == (480, 100, 960, 540)
    assert panel_physical((2400, 100, 480, 270), (1920, 0), 2.0) == (960, 200, 960, 540)


def test_panel_physical_never_returns_zero_size():
    _, _, w, h = panel_physical((0, 0, 1, 1), (0, 0), 0.5)
    assert w >= 1 and h >= 1


def test_qimage_to_bgr_keeps_channel_order():
    """内存里 Format_RGB32 是小端 BGRA，取前三通道就是 BGR —— rapidocr 要的顺序。"""
    from ocrsnip.qt_app import qimage_to_bgr

    image = QImage(2, 1, QImage.Format.Format_RGB32)
    image.setPixelColor(0, 0, QColor(10, 20, 30))  # R=10 G=20 B=30
    image.setPixelColor(1, 0, QColor(200, 100, 50))
    bgr = qimage_to_bgr(image)

    assert bgr.shape == (1, 2, 3)
    assert tuple(int(v) for v in bgr[0, 0]) == (30, 20, 10)
    assert tuple(int(v) for v in bgr[0, 1]) == (50, 100, 200)
    assert bgr.flags["C_CONTIGUOUS"]


def test_qimage_to_bgr_handles_row_padding():
    """宽度不是 4 的倍数时，bytesPerLine 会带 padding，不能被读进图像。"""
    from ocrsnip.qt_app import qimage_to_bgr

    image = QImage(3, 2, QImage.Format.Format_RGB32)
    image.fill(QColor(1, 2, 3))
    bgr = qimage_to_bgr(image)
    assert bgr.shape == (2, 3, 3)
    assert np.all(bgr[:, :, 0] == 3)  # B 通道
